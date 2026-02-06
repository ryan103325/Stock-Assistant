"""
台股新聞情緒分析資料庫模組
Tables: news_articles, ticker_sentiments, reflection_logs
"""

import sqlite3
import os
from datetime import datetime
from contextlib import contextmanager

# 資料庫路徑
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, "src", "data_core", "AlphaVantage_TW_Sentiment", "sentiment_history.db")


class SentimentDB:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or DB_PATH
        # 確保目錄存在
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
    
    def __enter__(self):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.conn.close()
    
    def create_tables(self):
        """建立所有資料表"""
        cursor = self.conn.cursor()
        
        # Table 1: news_articles (新聞主表)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS news_articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                source TEXT NOT NULL,
                publish_time TEXT NOT NULL,
                summary TEXT,
                overall_sentiment_score REAL,
                overall_sentiment_label TEXT,
                analyzed INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Table 2: ticker_sentiments (個股情緒)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ticker_sentiments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                news_id INTEGER NOT NULL,
                ticker TEXT NOT NULL,
                relevance_score REAL,
                sentiment_score REAL,
                sentiment_label TEXT,
                FOREIGN KEY (news_id) REFERENCES news_articles(id)
            )
        ''')
        
        # Table 3: reflection_logs (反省紀錄)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reflection_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                ticker TEXT NOT NULL,
                -- 預測資料
                predicted_label TEXT,
                predicted_score REAL,
                -- K棒原始資料
                open_price REAL,
                high_price REAL,
                low_price REAL,
                close_price REAL,
                volume INTEGER,
                -- 技術分析 - K棒
                price_change_pct REAL,
                volume_change_pct REAL,
                body_ratio REAL,
                upper_shadow_ratio REAL,
                lower_shadow_ratio REAL,
                candle_pattern TEXT,
                pv_pattern TEXT,
                -- 技術分析 - RSI
                rsi_value REAL,
                rsi_zone TEXT,
                rsi_divergence TEXT,
                -- 反省結果
                was_correct INTEGER,
                error_category TEXT,
                reflection_text TEXT,
                lesson_learned TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 建立索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_news_url ON news_articles(url)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_news_publish ON news_articles(publish_time)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ticker_newsid ON ticker_sentiments(news_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ticker_code ON ticker_sentiments(ticker)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_reflect_date ON reflection_logs(date)')
        
        self.conn.commit()
    
    # ========== News Articles ==========
    
    def insert_raw_news(self, url: str, title: str, source: str, publish_time: str, content: str) -> int:
        """插入原始新聞 (FETCH 階段)"""
        cursor = self.conn.cursor()
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO news_articles (url, title, source, publish_time, summary, analyzed)
                VALUES (?, ?, ?, ?, ?, 0)
            ''', (url, title, source, publish_time, content))
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            return 0  # 重複 URL
    
    def get_pending_news(self, limit: int = 100) -> list:
        """取得待分析的新聞"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, url, title, source, publish_time, summary as content
            FROM news_articles
            WHERE analyzed = 0
            ORDER BY publish_time DESC
            LIMIT ?
        ''', (limit,))
        return cursor.fetchall()
    
    def update_analysis(self, news_id: int, summary: str, score: float, label: str):
        """更新新聞分析結果"""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE news_articles
            SET summary = ?, overall_sentiment_score = ?, overall_sentiment_label = ?, analyzed = 1
            WHERE id = ?
        ''', (summary, score, label, news_id))
        self.conn.commit()
    
    def mark_analyzed(self, news_ids: list):
        """標記新聞為已分析"""
        if not news_ids:
            return
        cursor = self.conn.cursor()
        placeholders = ','.join('?' * len(news_ids))
        cursor.execute(f'''
            UPDATE news_articles SET analyzed = 1 WHERE id IN ({placeholders})
        ''', news_ids)
        self.conn.commit()
    
    # ========== Ticker Sentiments ==========
    
    def insert_ticker_sentiment(self, news_id: int, ticker: str, relevance: float, score: float, label: str):
        """插入個股情緒"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO ticker_sentiments (news_id, ticker, relevance_score, sentiment_score, sentiment_label)
            VALUES (?, ?, ?, ?, ?)
        ''', (news_id, ticker, relevance, score, label))
        self.conn.commit()
    
    def get_today_predictions(self, date: str) -> list:
        """取得指定日期的預測 (用於反省)"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT ts.ticker, ts.sentiment_score, ts.sentiment_label, na.title, na.url
            FROM ticker_sentiments ts
            JOIN news_articles na ON ts.news_id = na.id
            WHERE DATE(na.publish_time) = ?
            GROUP BY ts.ticker
        ''', (date,))
        return cursor.fetchall()
    
    # ========== Reflection Logs ==========
    
    def insert_reflection(self, data: dict):
        """插入反省紀錄"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO reflection_logs (
                date, ticker, predicted_label, predicted_score,
                open_price, high_price, low_price, close_price, volume,
                price_change_pct, volume_change_pct, body_ratio, upper_shadow_ratio, lower_shadow_ratio,
                candle_pattern, pv_pattern, rsi_value, rsi_zone, rsi_divergence,
                was_correct, error_category, reflection_text, lesson_learned
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('date'), data.get('ticker'), data.get('predicted_label'), data.get('predicted_score'),
            data.get('open_price'), data.get('high_price'), data.get('low_price'), data.get('close_price'), data.get('volume'),
            data.get('price_change_pct'), data.get('volume_change_pct'), data.get('body_ratio'), 
            data.get('upper_shadow_ratio'), data.get('lower_shadow_ratio'),
            data.get('candle_pattern'), data.get('pv_pattern'), data.get('rsi_value'), 
            data.get('rsi_zone'), data.get('rsi_divergence'),
            data.get('was_correct'), data.get('error_category'), data.get('reflection_text'), data.get('lesson_learned')
        ))
        self.conn.commit()
    
    # ========== Helper ==========
    
    def get_stats(self) -> dict:
        """取得統計資訊"""
        cursor = self.conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM news_articles')
        total_news = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM news_articles WHERE analyzed = 1')
        analyzed_news = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM ticker_sentiments')
        total_sentiments = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM reflection_logs')
        total_reflections = cursor.fetchone()[0]
        
        return {
            'total_news': total_news,
            'analyzed_news': analyzed_news,
            'pending_news': total_news - analyzed_news,
            'total_sentiments': total_sentiments,
            'total_reflections': total_reflections
        }
