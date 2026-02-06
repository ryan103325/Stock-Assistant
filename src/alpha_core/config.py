"""
台股新聞情緒分析 - 設定檔
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ========== API Keys ==========
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

# ========== AI Models ==========
WORKER_MODEL_NAME = "gemini-2.0-flash"  # 快速分析
REFLECTOR_MODEL_NAME = "gemini-2.0-flash"  # 反省模型

# ========== Paths ==========
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "src", "data_core")
DB_PATH = os.path.join(DATA_DIR, "AlphaVantage_TW_Sentiment", "sentiment_history.db")
HISTORY_DIR = os.path.join(DATA_DIR, "history")
TAIEX_PATH = os.path.join(DATA_DIR, "market_meta", "TAIEX.csv")
CMONEY_TAGS_PATH = os.path.join(DATA_DIR, "market_meta", "cmoney_all_tags.csv")

# ========== RSS Feeds ==========
RSS_FEEDS = [
    ("Yahoo 財經", "https://tw.stock.yahoo.com/rss?category=tw-market"),
    ("鉅亨網 台股", "https://news.cnyes.com/news/cat/tw_stock/rss"),
    ("鉅亨網 國際", "https://news.cnyes.com/news/cat/wd_stock/rss"),
    ("工商時報", "https://ctee.com.tw/feed"),
    ("經濟日報 股市", "https://money.udn.com/rssfeed/news/1001/5607"),
    ("經濟日報 產業", "https://money.udn.com/rssfeed/news/1001/5612"),
    ("MoneyDJ", "https://www.moneydj.com/RSS/RSSChannel.aspx?channelID=1"),
    ("TechNews", "https://technews.tw/feed/"),
    ("自由財經", "https://ec.ltn.com.tw/rss/business")
]

# ========== Processing ==========
BATCH_SIZE = 10  # 每批分析的新聞數量
REQUEST_DELAY = 2  # API 請求間隔 (秒)
