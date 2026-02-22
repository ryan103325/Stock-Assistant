"""
新聞情緒分析 - Export Script
從 SQLite 匯出情緒排名 JSON 到 docs/data/news/
"""

import json
import os
import sys
from datetime import datetime, timedelta

# 路徑設定
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(BASE_DIR, "src"))

from alpha_core.database import SentimentDB

OUTPUT_DIR = os.path.join(BASE_DIR, "docs", "data", "news")
RANKING_DAYS = 3       # 取近 N 天的資料
TOP_BULLISH = 20       # 看多前 N 名
TOP_BEARISH = 10       # 看空前 N 名
MAX_NEWS_PER_TICKER = 3  # 每檔股票最多顯示幾則新聞


def export_sentiment_ranking(db_path: str = None):
    """匯出個股情緒排名"""
    db = SentimentDB(db_path)
    
    cutoff = (datetime.now() - timedelta(days=RANKING_DAYS)).isoformat()
    
    with db:
        db.create_tables()
        cursor = db.conn.cursor()
        
        # 1. 個股情緒排名（加權平均：relevance * sentiment）
        cursor.execute('''
            SELECT 
                ts.ticker,
                ROUND(SUM(ts.sentiment_score * ts.relevance_score) / SUM(ts.relevance_score), 4) as weighted_score,
                COUNT(DISTINCT ts.news_id) as news_count,
                ROUND(AVG(ts.relevance_score), 2) as avg_relevance
            FROM ticker_sentiments ts
            JOIN news_articles na ON ts.news_id = na.id
            WHERE na.publish_time >= ?
              AND na.analyzed = 1
            GROUP BY ts.ticker
            HAVING news_count >= 1
            ORDER BY weighted_score DESC
        ''', (cutoff,))
        
        all_tickers = []
        for row in cursor.fetchall():
            ticker = row[0]
            weighted_score = row[1]
            news_count = row[2]
            avg_relevance = row[3]
            
            # 判斷 label
            if weighted_score >= 0.5:
                label = "Bullish"
            elif weighted_score >= 0.2:
                label = "Somewhat-Bullish"
            elif weighted_score >= -0.2:
                label = "Neutral"
            elif weighted_score >= -0.5:
                label = "Somewhat-Bearish"
            else:
                label = "Bearish"
            
            # 取得這檔股票的相關新聞
            cursor.execute('''
                SELECT na.title, na.source, na.url, 
                       ts.sentiment_score, na.confidence, na.summary, na.publish_time
                FROM ticker_sentiments ts
                JOIN news_articles na ON ts.news_id = na.id
                WHERE ts.ticker = ?
                  AND na.publish_time >= ?
                  AND na.analyzed = 1
                ORDER BY ts.relevance_score DESC, na.publish_time DESC
                LIMIT ?
            ''', (ticker, cutoff, MAX_NEWS_PER_TICKER))
            
            latest_news = []
            for news_row in cursor.fetchall():
                latest_news.append({
                    "title": news_row[0],
                    "source": news_row[1],
                    "url": news_row[2],
                    "score": news_row[3],
                    "confidence": news_row[4],
                    "summary": (news_row[5] or "")[:200],
                    "publish_time": news_row[6]
                })
            
            all_tickers.append({
                "ticker": ticker,
                "weighted_score": weighted_score,
                "label": label,
                "news_count": news_count,
                "avg_relevance": avg_relevance,
                "latest_news": latest_news
            })
        
        # 分成看多與看空
        bullish = [t for t in all_tickers if t["weighted_score"] > 0][:TOP_BULLISH]
        bearish = [t for t in reversed(all_tickers) if t["weighted_score"] < 0][:TOP_BEARISH]
        
        # 加排名
        for i, t in enumerate(bullish):
            t["rank"] = i + 1
        for i, t in enumerate(bearish):
            t["rank"] = i + 1
        
        ranking = {
            "updated_at": datetime.now().isoformat(timespec='seconds'),
            "period_days": RANKING_DAYS,
            "bullish": bullish,
            "bearish": bearish,
            "total_tickers": len(all_tickers)
        }
    
    return ranking


def export_market_summary(db_path: str = None):
    """匯出市場情緒統計"""
    db = SentimentDB(db_path)
    
    cutoff = (datetime.now() - timedelta(days=RANKING_DAYS)).isoformat()
    
    with db:
        db.create_tables()
        cursor = db.conn.cursor()
        
        # 總計
        cursor.execute('''
            SELECT COUNT(*) FROM news_articles WHERE publish_time >= ?
        ''', (cutoff,))
        total_news = cursor.fetchone()[0]
        
        cursor.execute('''
            SELECT COUNT(*) FROM news_articles WHERE publish_time >= ? AND analyzed = 1
        ''', (cutoff,))
        analyzed_news = cursor.fetchone()[0]
        
        # 平均情緒
        cursor.execute('''
            SELECT ROUND(AVG(overall_sentiment_score), 4) 
            FROM news_articles 
            WHERE publish_time >= ? AND analyzed = 1
        ''', (cutoff,))
        avg_row = cursor.fetchone()
        avg_sentiment = avg_row[0] if avg_row[0] is not None else 0
        
        # 情緒分佈
        cursor.execute('''
            SELECT overall_sentiment_label, COUNT(*) 
            FROM news_articles 
            WHERE publish_time >= ? AND analyzed = 1
            GROUP BY overall_sentiment_label
        ''', (cutoff,))
        distribution = {}
        for row in cursor.fetchall():
            if row[0]:
                distribution[row[0]] = row[1]
        
        # 來源統計
        cursor.execute('''
            SELECT source, COUNT(*) as cnt 
            FROM news_articles 
            WHERE publish_time >= ?
            GROUP BY source
            ORDER BY cnt DESC
        ''', (cutoff,))
        top_sources = []
        for row in cursor.fetchall():
            top_sources.append({"source": row[0], "count": row[1]})
        
        # 最近分析的新聞（前 30 則）
        cursor.execute('''
            SELECT title, source, url, overall_sentiment_score, 
                   overall_sentiment_label, confidence, summary, publish_time
            FROM news_articles
            WHERE publish_time >= ? AND analyzed = 1
            ORDER BY publish_time DESC
            LIMIT 30
        ''', (cutoff,))
        recent_news = []
        for row in cursor.fetchall():
            recent_news.append({
                "title": row[0],
                "source": row[1],
                "url": row[2],
                "score": row[3],
                "label": row[4],
                "confidence": row[5],
                "summary": (row[6] or "")[:200],
                "publish_time": row[7]
            })
        
        summary = {
            "updated_at": datetime.now().isoformat(timespec='seconds'),
            "period_days": RANKING_DAYS,
            "total_news": total_news,
            "analyzed_news": analyzed_news,
            "avg_sentiment": avg_sentiment,
            "sentiment_distribution": distribution,
            "top_sources": top_sources,
            "recent_news": recent_news
        }
    
    return summary


def export_single_stock(ticker: str, db_path: str = None):
    """匯出單一股票情緒分析"""
    db = SentimentDB(db_path)
    cutoff = (datetime.now() - timedelta(days=30)).isoformat()  # 單股取近30天新聞
    
    with db:
        db.create_tables()
        cursor = db.conn.cursor()
        
        # 個股加權平均情緒
        cursor.execute('''
            SELECT 
                ROUND(SUM(ts.sentiment_score * ts.relevance_score) / SUM(ts.relevance_score), 4) as weighted_score,
                COUNT(DISTINCT ts.news_id) as news_count
            FROM ticker_sentiments ts
            JOIN news_articles na ON ts.news_id = na.id
            WHERE ts.ticker = ?
              AND na.publish_time >= ?
              AND na.analyzed = 1
        ''', (ticker, cutoff))
        
        row = cursor.fetchone()
        weighted_score = row[0] if row[0] is not None else 0
        news_count = row[1] if row[1] is not None else 0
        
        # 取得這檔股票的相關新聞
        cursor.execute('''
            SELECT na.title, na.source, na.url, 
                   ts.sentiment_score, na.confidence, na.summary, na.publish_time,
                   ts.sentiment_label
            FROM ticker_sentiments ts
            JOIN news_articles na ON ts.news_id = na.id
            WHERE ts.ticker = ?
              AND na.publish_time >= ?
              AND na.analyzed = 1
            ORDER BY na.publish_time DESC
            LIMIT 20
        ''', (ticker, cutoff))
        
        news_list = []
        distribution = {
            "Bullish": 0, "Somewhat-Bullish": 0, "Neutral": 0,
            "Somewhat-Bearish": 0, "Bearish": 0
        }
        
        for news_row in cursor.fetchall():
            score = news_row[3]
            label = news_row[7]
            if label in distribution:
                distribution[label] += 1
                
            news_list.append({
                "title": news_row[0],
                "source": news_row[1],
                "url": news_row[2],
                "score": score,
                "confidence": news_row[4],
                "summary": (news_row[5] or "").strip(),
                "publish_time": news_row[6],
                "label": label
            })
            
        summary = {
            "stock_id": ticker,
            "updated_at": datetime.now().isoformat(timespec='seconds'),
            "period_days": 30,
            "news_count": news_count,
            "weighted_score": weighted_score,
            "sentiment_distribution": distribution,
            "news": news_list
        }
    
    return summary


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    if len(sys.argv) > 1:
        # 單股匯出模式
        ticker = sys.argv[1]
        print(f"📊 匯出個股 {ticker} 新聞情緒...")
        summary = export_single_stock(ticker)
        file_path = os.path.join(OUTPUT_DIR, f"{ticker}.json")
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"   ✅ 完成: {file_path} (共 {summary['news_count']} 則新聞)")
    else:
        # 原本的全市場排名模式
        print("📊 匯出新聞情緒排名...")
        ranking = export_sentiment_ranking()
        ranking_path = os.path.join(OUTPUT_DIR, "sentiment_ranking.json")
        with open(ranking_path, 'w', encoding='utf-8') as f:
            json.dump(ranking, f, ensure_ascii=False, indent=2)
        print(f"   ✅ 排名匯出完成: {ranking_path}")
        
        print("\n📈 匯出市場情緒統計...")
        summary = export_market_summary()
        summary_path = os.path.join(OUTPUT_DIR, "market_summary.json")
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"   ✅ 統計匯出完成: {summary_path}")
    
    print("\n🎉 匯出完成！")

if __name__ == "__main__":
    main()
