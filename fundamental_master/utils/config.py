"""
配置管理模組
負責載入環境變數與系統配置
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 載入 .env 檔案
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(env_path)


class Config:
    """系統配置類別"""
    
    # ==================== API Keys ====================
    # OpenAI API (用於 AI 質化分析)
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')  # 預設使用 gpt-4o-mini
    
    # Google Gemini API (備用選項)
    GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
    
    # OpenRouter API (備用選項)
    OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
    
    # FinMind API (可用於補充財務數據)
    FINMIND_TOKEN = os.getenv('FINMIND_TOKEN')
    
    # Telegram Bot
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
    
    # ==================== 資料來源設定 ====================
    # Goodinfo 網址
    GOODINFO_BASE_URL = 'https://goodinfo.tw/tw'
    GOODINFO_STOCK_LIST_URL = 'https://goodinfo.tw/tw/StockList.asp'
    
    # MacroMicro 網址 (台灣 10 年期公債殖利率)
    MACROMICRO_BOND_YIELD_URL = 'https://www.macromicro.me/charts/52383/tai-wan-10-nian-qi-gong-zhai-zhi-li-lyu'
    
    # ==================== 爬蟲設定 ====================
    # User-Agent 列表 (輪替使用避免被封鎖)
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    ]
    
    # 請求間隔 (秒)
    REQUEST_DELAY_MIN = 2
    REQUEST_DELAY_MAX = 5
    
    # 重試設定
    MAX_RETRIES = 3
    RETRY_DELAY = 5
    
    # ==================== 資料儲存路徑 ====================
    BASE_DIR = Path(__file__).parent.parent.parent
    DATA_DIR = BASE_DIR / 'data'
    RAW_DATA_DIR = DATA_DIR / 'raw'
    PROCESSED_DATA_DIR = DATA_DIR / 'processed'
    REPORTS_DIR = DATA_DIR / 'reports'
    
    # ==================== AI 分析設定 ====================
    # GPT-4-mini 參數
    GPT_TEMPERATURE = 0.3  # 較低的溫度以獲得更穩定的輸出
    GPT_MAX_TOKENS = 2000
    
    # ==================== 報告輸出設定 ====================
    # 圖片尺寸 (適合 Telegram 顯示)
    REPORT_IMAGE_WIDTH = 1200
    REPORT_IMAGE_HEIGHT = None  # 自動調整高度
    
    # 圖片品質
    REPORT_IMAGE_QUALITY = 90
    
    # ==================== 評分模型設定 ====================
    # M-Score 閾值
    M_SCORE_THRESHOLD = -1.78
    
    # Z-Score 閾值
    Z_SCORE_SAFE_ZONE = 2.99
    Z_SCORE_GREY_ZONE = 1.81
    
    # F-Score 評級
    F_SCORE_STRONG = 8  # 8-9 分為強勢
    F_SCORE_WEAK = 3    # 0-3 分為惡化
    
    @classmethod
    def validate(cls):
        """驗證必要的配置是否存在"""
        required_keys = [
            ('OPENAI_API_KEY', cls.OPENAI_API_KEY),
            ('TELEGRAM_TOKEN', cls.TELEGRAM_TOKEN),
            ('TELEGRAM_CHAT_ID', cls.TELEGRAM_CHAT_ID),
        ]
        
        missing_keys = []
        for key_name, key_value in required_keys:
            if not key_value:
                missing_keys.append(key_name)
        
        if missing_keys:
            raise ValueError(
                f"缺少必要的環境變數: {', '.join(missing_keys)}\n"
                f"請檢查 .env 檔案是否正確設定"
            )
    
    @classmethod
    def create_directories(cls):
        """建立必要的資料夾"""
        directories = [
            cls.DATA_DIR,
            cls.RAW_DATA_DIR,
            cls.PROCESSED_DATA_DIR,
            cls.REPORTS_DIR,
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
        
        print(f"✅ 資料夾結構已建立於: {cls.BASE_DIR}")


# 初始化時驗證配置
try:
    Config.validate()
    print("✅ 配置驗證通過")
except ValueError as e:
    print(f"⚠️ 配置驗證失敗: {e}")
