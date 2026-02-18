"""
無風險利率爬蟲模組
從 Investing.com 抓取台灣 10 年期公債殖利率
"""
import json
import re
import time
import random
from typing import Optional
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from bs4 import BeautifulSoup

from fundamental_master.utils.config import Config
from fundamental_master.utils.logger import setup_logger
from fundamental_master.utils.exceptions import DataCollectionError

logger = setup_logger('macromicro_scraper')

# 快取檔案路徑
CACHE_FILE = Config.RAW_DATA_DIR / 'risk_free_rate_cache.json'

# Investing.com 台灣 10 年期公債 (歷史數據頁)
INVESTING_URL = 'https://hk.investing.com/rates-bonds/taiwan-10-year-bond-yield-historical-data'


def fetch_risk_free_rate(use_cache: bool = True, cache_hours: int = 24) -> float:
    """
    抓取台灣 10 年期公債殖利率 (無風險利率)

    Args:
        use_cache: 是否使用快取
        cache_hours: 快取有效時間 (小時)

    Returns:
        float: 殖利率 (百分比, 例如 1.6 代表 1.6%)
    """
    # 檢查快取
    if use_cache:
        cached = _load_cache(cache_hours)
        if cached is not None:
            logger.info(f"📦 使用快取的無風險利率: {cached}%")
            return cached

    logger.info("🌐 開始抓取台灣 10 年期公債殖利率...")

    rate = _scrape_from_investing()

    if rate is not None:
        _save_cache(rate)
        logger.info(f"✅ 無風險利率: {rate}%")
        return rate

    # 如果抓取失敗, 嘗試使用過期快取
    expired_cache = _load_cache(cache_hours=None)  # 不限時間
    if expired_cache is not None:
        logger.warning(f"⚠️ 使用過期快取的無風險利率: {expired_cache}%")
        return expired_cache

    # 最後手段: 使用預設值
    default_rate = 1.6
    logger.warning(f"⚠️ 無法取得無風險利率, 使用預設值: {default_rate}%")
    return default_rate


def _scrape_from_investing() -> Optional[float]:
    """從 Investing.com 歷史數據頁面抓取最新殖利率"""
    max_retries = 2
    
    for attempt in range(max_retries):
        options = Options()
        options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')

        ua = random.choice(Config.USER_AGENTS)
        options.add_argument(f'--user-agent={ua}')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option('excludeSwitches', ['enable-automation'])

        driver = None
        try:
            driver = webdriver.Chrome(options=options)
            driver.execute_cdp_cmd(
                'Page.addScriptToEvaluateOnNewDocument',
                {'source': 'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'}
            )

            driver.get(INVESTING_URL)

            # 等待歷史數據表格載入 (增加到 20s)
            try:
                WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'table'))
                )
            except TimeoutException:
                logger.warning(f"⚠️ 表格載入 timeout (嘗試 {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    continue
            
            time.sleep(random.uniform(2, 4))

            page_source = driver.page_source
            soup = BeautifulSoup(page_source, 'lxml')

            # 方法 1: 找歷史數據表格, 取第一行 (最新一天) 的「收市」值
            # Investing.com 歷史表格結構: 日期 | 收市 | 開市 | 高 | 低 | 升跌幅
            tables = soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                if len(rows) < 2:
                    continue
                # 找到有日期和數字的表格
                for row in rows[1:3]:  # 只看前兩行數據
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        # 收市價通常在第二欄
                        close_text = cells[1].get_text(strip=True)
                        val = _parse_float(close_text)
                        if val and 0.3 <= val <= 5.0:
                            logger.info(f"✅ Investing.com 成功: {val}%")
                            return val

            # 方法 2: 用 data-test 屬性找
            for attr in ['instrument-price-last', 'last-price']:
                el = soup.find(attrs={'data-test': attr})
                if el:
                    val = _parse_float(el.get_text(strip=True))
                    if val and 0.3 <= val <= 5.0:
                        logger.info(f"✅ Investing.com 成功 (data-test): {val}%")
                        return val

            # 方法 3: regex fallback
            text = soup.get_text()
            matches = re.findall(r'(\d+\.\d{2,3})', text)
            for match in matches:
                val = float(match)
                if 0.5 <= val <= 3.5:
                    logger.info(f"✅ Investing.com 成功 (regex): {val}%")
                    return val

            logger.warning(f"⚠️ 無法從 Investing.com 提取殖利率 (嘗試 {attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                time.sleep(2)  # 重試前等待
                continue
            
            return None

        except Exception as e:
            logger.error(f"❌ Investing.com 抓取失敗 (嘗試 {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            return None
        finally:
            if driver:
                driver.quit()
    
    return None


def _parse_float(text: str) -> Optional[float]:
    """解析浮點數"""
    if not text:
        return None
    text = text.replace(',', '').replace('%', '').strip()
    try:
        return float(text)
    except ValueError:
        return None


def _load_cache(cache_hours: Optional[int]) -> Optional[float]:
    """載入快取"""
    if not CACHE_FILE.exists():
        return None

    try:
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            cache = json.load(f)

        if cache_hours is not None:
            cached_time = cache.get('timestamp', 0)
            current_time = time.time()
            if current_time - cached_time > cache_hours * 3600:
                return None  # 快取過期

        return cache.get('rate')

    except Exception:
        return None


def _save_cache(rate: float):
    """儲存快取"""
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                'rate': rate,
                'timestamp': time.time(),
                'source': 'Investing.com',
                'description': '台灣 10 年期公債殖利率',
            }, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"快取儲存失敗: {e}")
