"""
Tavily 即時新聞搜尋 - 針對個股搜尋最新新聞並存入 DB
"""

import os
import json
import sys
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(BASE_DIR, "src"))

from alpha_core.database import SentimentDB
from alpha_core.config import DB_PATH


# 從 stock_list.json 取得股票名稱
STOCK_LIST_PATH = os.path.join(BASE_DIR, "docs", "data", "stock_list.json")


def get_stock_name(ticker: str) -> str:
    """從 stock_list.json 取得股票名稱"""
    try:
        with open(STOCK_LIST_PATH, 'r', encoding='utf-8') as f:
            stocks = json.load(f)
        for s in stocks:
            if s['id'] == ticker:
                return s['name']
    except Exception:
        pass
    return ticker


def get_stock_metadata(ticker: str) -> dict:
    """透過 Yahoo Finance API 取得公司英文名稱與產業別"""
    import urllib.request
    import json
    
    def fetch_yf(symbol):
        url = f"https://query2.finance.yahoo.com/v1/finance/search?q={symbol}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        try:
            res = urllib.request.urlopen(req, timeout=5).read()
            data = json.loads(res.decode('utf-8'))
            if 'quotes' in data and len(data['quotes']) > 0:
                quote = data['quotes'][0]
                if quote.get('symbol', '').startswith(ticker):
                    return {
                        'english_name': quote.get('longname', quote.get('shortname', '')),
                        'industry': quote.get('industryDisp', '')
                    }
        except Exception:
            pass
        return None

    meta = fetch_yf(f"{ticker}.TW")
    if not meta:
        meta = fetch_yf(f"{ticker}.TWO")
    
    return meta or {'english_name': '', 'industry': ''}

def get_industry_tags(industry_eng: str) -> str:
    """將英文產業轉換為中文搜尋標籤"""
    if not industry_eng:
        return ""
        
    industry_eng = industry_eng.lower()
    mapping = {
        "semiconductor": "半導體 晶片 先進製程",
        "building": "水泥 建材 綠能",
        "bank": "金融 銀行 升息",
        "electronic": "電子零組件 供應鏈",
        "computer": "電腦 伺服器 AI",
        "auto": "汽車零組件 電動車 車用",
        "marine": "航運 海運 運價",
        "steel": "鋼鐵 報價",
        "software": "軟體 資訊服務 雲端",
        "telecom": "電信 通訊",
        "biotech": "生技 醫療 新藥",
        "chemical": "化學 塑化",
        "textile": "紡織 成衣",
        "food": "食品 內需",
        "machinery": "機械 設備工具",
        "retail": "零售 消費 內需",
    }
    
    tags = []
    for key, val in mapping.items():
        if key in industry_eng:
            tags.append(val)
    
    if tags:
        return " ".join(tags)
    return industry_eng

def search_news(ticker: str, max_results: int = 10) -> list:
    """用 Tavily 搜尋個股新聞"""
    api_key = os.getenv("TAVILY_API_KEY", "")
    if not api_key:
        print("❌ TAVILY_API_KEY 未設定")
        return []

    try:
        from tavily import TavilyClient
    except ImportError:
        print("❌ 請先安裝 tavily-python: pip install tavily-python")
        return []

    client = TavilyClient(api_key=api_key)
    stock_name = get_stock_name(ticker)

    # 取得擴充資訊 (英文名、產業標籤)
    meta = get_stock_metadata(ticker)
    eng_name = meta.get('english_name', '')
    industry_tags = get_industry_tags(meta.get('industry', ''))

    print(f"   ℹ️  股票資訊: {eng_name} | 產業標籤: {industry_tags}")

    # 搜尋策略：用股票名稱 + 英文名稱 + 產業標籤 + 代碼搜尋
    queries = [
        f"{stock_name} {eng_name} {ticker} {industry_tags} 台股 最新消息",
        f"{stock_name} {ticker} {industry_tags} 財報 營收 法人",
    ]

    all_results = []
    seen_urls = set()

    for query in queries:
        try:
            print(f"   🔍 搜尋: {query}")
            response = client.search(
                query=query,
                max_results=max_results,
                search_depth="advanced",
                include_domains=[
                    "cnyes.com", "money.udn.com", "ctee.com.tw",
                    "technews.tw", "moneydj.com", "ltn.com.tw",
                    "tw.stock.yahoo.com", "finance.yahoo.com",
                    "wantrich.chinatimes.com", "wealth.businessweekly.com.tw"
                ]
            )

            for item in response.get("results", []):
                url = item.get("url", "")
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                all_results.append({
                    "url": url,
                    "title": item.get("title", ""),
                    "source": f"Tavily:{_extract_domain(url)}",
                    "publish_time": item.get("published_date", datetime.now().isoformat()),
                    "content": item.get("content", "")[:3000],
                })
        except Exception as e:
            print(f"   ⚠️ 搜尋失敗: {e}")

    return all_results


def _extract_domain(url: str) -> str:
    """從 URL 提取網域名"""
    try:
        from urllib.parse import urlparse
        domain = urlparse(url).netloc
        # 簡化常見來源名稱
        domain_map = {
            "news.cnyes.com": "鉅亨網",
            "www.cnyes.com": "鉅亨網",
            "money.udn.com": "經濟日報",
            "ctee.com.tw": "工商時報",
            "technews.tw": "TechNews",
            "www.moneydj.com": "MoneyDJ",
            "ec.ltn.com.tw": "自由財經",
            "tw.stock.yahoo.com": "Yahoo 財經",
            "wantrich.chinatimes.com": "旺得富",
        }
        return domain_map.get(domain, domain)
    except Exception:
        return "Unknown"


def fetch_and_store(ticker: str, max_results: int = 10, db_path: str = None):
    """搜尋新聞並存入 DB"""
    print(f"\n📡 Tavily 搜尋: {ticker} ({get_stock_name(ticker)})")

    results = search_news(ticker, max_results)
    if not results:
        print("   ❌ 沒有搜到新聞")
        return 0

    print(f"   📰 搜到 {len(results)} 則新聞")

    db = SentimentDB(db_path)
    inserted = 0
    with db:
        db.create_tables()
        deleted = db.delete_old_records(days=30)
        if deleted > 0:
            print(f"   🧹 自動清理了 {deleted} 筆超過 30 天的舊新聞資料")
            
        for item in results:
            result = db.insert_raw_news(
                url=item['url'],
                title=item['title'],
                source=item['source'],
                publish_time=item['publish_time'],
                content=item['content']
            )
            if result:
                inserted += 1

    print(f"   ✅ 新增 {inserted} 則 (重複跳過 {len(results) - inserted} 則)")
    return inserted


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m src.alpha_core.tavily_fetcher <股票代碼>")
        print("Example: python -m src.alpha_core.tavily_fetcher 2330")
        return

    ticker = sys.argv[1]
    max_results = 8
    if len(sys.argv) > 2:
        try:
            max_results = int(sys.argv[2])
        except ValueError:
            pass

    fetch_and_store(ticker, max_results)


if __name__ == "__main__":
    main()
