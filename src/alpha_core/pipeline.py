"""
台股新聞情緒分析 - Pipeline 主流程
"""

import asyncio
import os
from datetime import datetime
from typing import List, Dict

from .config import RSS_FEEDS, BATCH_SIZE, REQUEST_DELAY
from .database import SentimentDB
from .rss_fetcher import fetch_all_feeds
from .llm_client import get_worker_client


class SentimentPipeline:
    def __init__(self):
        self.db = SentimentDB()
        self.llm = get_worker_client()
        self._load_system_prompt()
        self._load_valid_tickers()
    
    def _load_system_prompt(self):
        """載入 Worker System Prompt"""
        prompt_path = os.path.join(os.path.dirname(__file__), "prompts", "worker_system.txt")
        with open(prompt_path, 'r', encoding='utf-8') as f:
            self.system_prompt = f.read()
    
    def _load_valid_tickers(self):
        """載入有效股票清單 (從 history 資料夾)"""
        history_dir = os.path.join(os.path.dirname(__file__), "..", "data_core", "history")
        self.valid_tickers = set()
        if os.path.exists(history_dir):
            for f in os.listdir(history_dir):
                if f.endswith('.csv'):
                    ticker = f.replace('.csv', '')
                    # 只保留 4 位數字的股票代碼
                    if ticker.isdigit() and len(ticker) == 4:
                        self.valid_tickers.add(ticker)
        print(f"📋 有效股票清單: {len(self.valid_tickers)} 檔")
    
    # ========== FETCH ==========
    
    def fetch(self):
        """Step 1: 抓取新聞並存入資料庫"""
        print("=" * 50)
        print("📡 Step 1: FETCH - 抓取新聞")
        print("=" * 50)
        
        # 1. 抓取所有 RSS
        all_news = fetch_all_feeds(RSS_FEEDS)
        
        # 2. 存入資料庫 (去重由 URL UNIQUE 處理)
        with self.db as db:
            db.create_tables()
            inserted = 0
            for item in all_news:
                result = db.insert_raw_news(
                    url=item['url'],
                    title=item['title'],
                    source=item['source'],
                    publish_time=item['publish_time'],
                    content=item['content']
                )
                if result:
                    inserted += 1
            
            stats = db.get_stats()
        
        print(f"\n📊 FETCH 完成:")
        print(f"   新增: {inserted} 則")
        print(f"   總計: {stats['total_news']} 則")
        print(f"   待分析: {stats['pending_news']} 則")
    
    # ========== ANALYZE ==========
    
    async def analyze(self, limit: int = 100):
        """Step 2: AI 情緒分析"""
        print("=" * 50)
        print("🤖 Step 2: ANALYZE - AI 情緒分析")
        print("=" * 50)
        
        with self.db as db:
            db.create_tables()
            pending = db.get_pending_news(limit=limit)
        
        if not pending:
            print("✅ 沒有待分析的新聞")
            return
        
        print(f"📰 找到 {len(pending)} 則待分析新聞")
        
        # 分批處理
        pending_list = [dict(row) for row in pending]
        batches = [pending_list[i:i+BATCH_SIZE] for i in range(0, len(pending_list), BATCH_SIZE)]
        
        total_analyzed = 0
        total_sentiments = 0
        
        for batch_idx, batch in enumerate(batches):
            print(f"\n🔄 Processing batch {batch_idx+1}/{len(batches)} ({len(batch)} items)...")
            
            # 組合 User Prompt
            user_prompt = self._build_user_prompt(batch)
            
            # 呼叫 LLM
            result = await self.llm.generate(self.system_prompt, user_prompt)
            
            if result:
                # 儲存結果
                with self.db as db:
                    for item in result:
                        # 找到對應的原始新聞
                        matching = next((n for n in batch if n['url'] == item.get('url')), None)
                        if matching:
                            news_id = matching['id']
                            
                            # 組合 summary（含 key_facts）
                            summary = item.get('summary', '')
                            key_facts = item.get('key_facts', [])
                            if key_facts:
                                summary += '\n關鍵事實：' + '；'.join(key_facts)
                            
                            # 更新新聞分析
                            db.update_analysis(
                                news_id=news_id,
                                summary=summary,
                                score=item.get('overall_sentiment_score', 0),
                                label=item.get('overall_sentiment_label', 'Neutral'),
                                confidence=item.get('confidence', None)
                            )
                            total_analyzed += 1
                            
                            # 插入個股情緒 (只保留有效股票)
                            for ticker_item in item.get('ticker_sentiment', []):
                                ticker = ticker_item.get('ticker', '')
                                # 過濾：只保留 history 資料夾中有的股票
                                if ticker not in self.valid_tickers:
                                    continue
                                    
                                db.insert_ticker_sentiment(
                                    news_id=news_id,
                                    ticker=ticker,
                                    relevance=ticker_item.get('relevance_score', 0),
                                    score=ticker_item.get('sentiment_score', 0),
                                    label=ticker_item.get('sentiment_label', 'Neutral')
                                )
                                total_sentiments += 1
            
            # 延遲避免 Rate Limit
            if batch_idx < len(batches) - 1:
                await asyncio.sleep(REQUEST_DELAY)
        
        print(f"\n📊 ANALYZE 完成:")
        print(f"   分析: {total_analyzed} 則新聞")
        print(f"   個股情緒: {total_sentiments} 筆")
    
    def _build_user_prompt(self, batch: List[Dict]) -> str:
        """建構 User Prompt"""
        items = []
        for i, news in enumerate(batch):
            items.append(f"""
### 來源{i+1}
- URL: {news['url']}
- Title: {news['title']}
- Source: {news['source']}
- Content: {news['content'][:2000]}
""")
        
        news_list_text = "\n".join(items)
        
        # 載入 user template
        template_path = os.path.join(os.path.dirname(__file__), "prompts", "worker_user_template.txt")
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                template = f.read()
            return template.replace('{news_list_text}', news_list_text)
        except FileNotFoundError:
            # Fallback
            return f"請分析以下新聞（UNTRUSTED）：\n{news_list_text}"
    
    # ========== STATS ==========
    
    def stats(self):
        """顯示統計資訊"""
        with self.db as db:
            db.create_tables()
            stats = db.get_stats()
        
        print("\n📊 資料庫統計:")
        print(f"   新聞總數: {stats['total_news']}")
        print(f"   已分析: {stats['analyzed_news']}")
        print(f"   待分析: {stats['pending_news']}")
        print(f"   個股情緒: {stats['total_sentiments']}")
        print(f"   反省紀錄: {stats['total_reflections']}")


# 便捷函數
def run_fetch():
    pipeline = SentimentPipeline()
    pipeline.fetch()

async def run_analyze(limit: int = 100):
    pipeline = SentimentPipeline()
    await pipeline.analyze(limit)

def run_stats():
    pipeline = SentimentPipeline()
    pipeline.stats()
