"""
Goodinfo 資料爬蟲模組
負責從 Goodinfo 台灣股市資訊網抓取財務報表數據

抓取範圍:
- 個股首頁: 股價、市值、發行股數、Beta、每股淨值
- 資產負債表 (季表): 資產/負債/權益各科目
- 損益表 (季表): 營收/成本/費用/淨利
- 現金流量表 (季表): 營運/投資/籌資現金流
"""
import time
import random
import re
from typing import Optional

import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup

from fundamental_master.utils.config import Config
from fundamental_master.utils.logger import setup_logger
from fundamental_master.utils.exceptions import DataCollectionError

logger = setup_logger('goodinfo_scraper')


class GoodinfoScraper:
    """Goodinfo 資料爬蟲"""

    # URL 模板
    URLS = {
        'stock_detail': f'{Config.GOODINFO_BASE_URL}/StockDetail.asp?STOCK_ID={{stock_id}}',
        # FinDetail 金額版 (垂直表格: 每行=科目, 每列=季度)
        'balance_sheet': f'{Config.GOODINFO_BASE_URL}/StockFinDetail.asp?STOCK_ID={{stock_id}}&RPT_CAT=BS_M_QUAR',
        'income_statement': f'{Config.GOODINFO_BASE_URL}/StockFinDetail.asp?STOCK_ID={{stock_id}}&RPT_CAT=IS_M_QUAR',
        'cashflow': f'{Config.GOODINFO_BASE_URL}/StockFinDetail.asp?STOCK_ID={{stock_id}}&RPT_CAT=CF_M_QUAR',
        # 舊版摘要表 (用於歷史 EPS)
        'income_summary': f'{Config.GOODINFO_BASE_URL}/StockBzPerformance.asp?STOCK_ID={{stock_id}}',
        # 股利政策
        'dividend': f'{Config.GOODINFO_BASE_URL}/StockDividendPolicy.asp?STOCK_ID={{stock_id}}',
    }

    def __init__(self, headless: bool = True):
        """
        初始化爬蟲

        Args:
            headless: 是否使用無頭模式
        """
        self.driver = None
        self.headless = headless
        self._setup_driver()

    def _setup_driver(self):
        """設置 Selenium WebDriver"""
        options = Options()
        if self.headless:
            options.add_argument('--headless=new')

        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')

        # 隨機選擇 User-Agent
        ua = random.choice(Config.USER_AGENTS)
        options.add_argument(f'--user-agent={ua}')

        # 禁用自動化檢測
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option('excludeSwitches', ['enable-automation'])
        options.add_experimental_option('useAutomationExtension', False)

        try:
            self.driver = webdriver.Chrome(options=options)
            self.driver.execute_cdp_cmd(
                'Page.addScriptToEvaluateOnNewDocument',
                {'source': 'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'}
            )
            logger.info("✅ Chrome WebDriver 初始化成功")

            # Cookie 預熱: 先訪問首頁取得必要 cookies
            self._warmup_cookies()

        except Exception as e:
            raise DataCollectionError(f"Chrome WebDriver 初始化失敗: {e}")

    def _warmup_cookies(self):
        """訪問 Goodinfo 首頁預熱 cookies, 處理初次 JS redirect"""
        try:
            logger.info("🍪 預熱 Cookies: 訪問 Goodinfo 首頁...")
            self.driver.get(Config.GOODINFO_BASE_URL)
            time.sleep(1)

            # Goodinfo 首頁有時會有 JS redirect, 等它跳轉完成
            for _ in range(5):
                page_source = self.driver.page_source
                # 偵測是否還在 redirect 頁面
                if 'location.replace' in page_source or 'meta http-equiv="refresh"' in page_source.lower():
                    logger.info("  ⏳ 偵測到 redirect, 等待跳轉...")
                    time.sleep(1.5)
                else:
                    break

            # 確認頁面已載入
            current_url = self.driver.current_url
            logger.info(f"🍪 Cookie 預熱完成, 當前 URL: {current_url}")
            time.sleep(random.uniform(1, 2))

        except Exception as e:
            logger.warning(f"⚠️ Cookie 預熱失敗 (非致命): {e}")

    def _wait_and_get_page(self, url: str, wait_selector: str = 'table', timeout: int = 20):
        """
        載入頁面並等待元素出現, 含 redirect 偵測與處理

        Args:
            url: 目標網址
            wait_selector: 等待出現的 CSS 選擇器
            timeout: 逾時秒數
        """
        retry_count = 0
        while retry_count < Config.MAX_RETRIES:
            try:
                self.driver.get(url)

                # 處理 Goodinfo 的 JS redirect / 驗證頁面
                self._handle_redirect(timeout=10)

                # 等待目標元素出現 (先嘗試指定 selector, 失敗則 fallback)
                try:
                    WebDriverWait(self.driver, timeout).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, wait_selector))
                    )
                except TimeoutException:
                    # Fallback: 嘗試等待任何 table
                    logger.info(f"  ⏳ 找不到 '{wait_selector}', 嘗試等待任意 table...")
                    WebDriverWait(self.driver, timeout).until(
                        EC.presence_of_element_located((By.TAG_NAME, 'table'))
                    )

                # 隨機等待, 模擬人類行為
                time.sleep(random.uniform(Config.REQUEST_DELAY_MIN, Config.REQUEST_DELAY_MAX))
                return

            except TimeoutException:
                retry_count += 1
                # 印出頁面標題和部分內容幫助 debug
                title = self.driver.title if self.driver else 'N/A'
                logger.warning(
                    f"頁面載入逾時 (嘗試 {retry_count}/{Config.MAX_RETRIES}): {url}\n"
                    f"  頁面標題: {title}"
                )
                time.sleep(Config.RETRY_DELAY)

            except Exception as e:
                retry_count += 1
                logger.error(f"頁面載入錯誤 (嘗試 {retry_count}/{Config.MAX_RETRIES}): {e}")
                time.sleep(Config.RETRY_DELAY)

        raise DataCollectionError(f"頁面載入失敗,已重試 {Config.MAX_RETRIES} 次: {url}")

    def _handle_redirect(self, timeout: int = 10):
        """
        處理 Goodinfo 的 JS redirect 和驗證頁面
        Goodinfo 常見模式:
        1. meta http-equiv="refresh" redirect
        2. JavaScript location.replace() redirect
        3. Cookie 驗證後 redirect
        """
        start = time.time()
        while time.time() - start < timeout:
            try:
                page_source = self.driver.page_source

                # 檢查是否在 redirect 頁面
                has_location_replace = 'location.replace' in page_source
                has_location_href = (
                    'location.href' in page_source.split('<body')[0]
                    if '<body' in page_source else False
                )
                has_meta_refresh = 'meta http-equiv="refresh"' in page_source.lower()
                is_tiny_page = len(page_source) < 500

                is_redirect = has_location_replace or has_location_href or has_meta_refresh or is_tiny_page

                if not is_redirect:
                    return  # 正常頁面, 繼續

                logger.info("  ⏳ 偵測到 redirect/驗證頁面, 等待跳轉...")
                time.sleep(2)

            except Exception:
                time.sleep(1)

        logger.warning("  ⚠️ redirect 處理逾時, 繼續嘗試解析")

    def _expand_quarters(self, min_quarters: int = 8):
        """
        在 FinDetail 頁面上切換 QRY_TIME 下拉選單,
        選擇更早的起始季度, 讓頁面顯示足夠多的季度數據
        (M-Score/營收成長率需要至少 8 季)
        """
        try:
            from selenium.webdriver.support.ui import Select
            select_el = self.driver.find_element('css selector', 'select#QRY_TIME')
            sel = Select(select_el)
            options = sel.options

            if len(options) < min_quarters:
                logger.info(f"  📅 QRY_TIME 只有 {len(options)} 個選項, 無法擴展")
                return

            # 選擇足夠早的季度 (index = min_quarters - 1, 從 0 起算)
            target_idx = min(min_quarters - 1, len(options) - 1)
            target_text = options[target_idx].text
            logger.info(f"  📅 切換 QRY_TIME 到 {target_text} (取 {target_idx + 1} 季)")

            sel.select_by_index(target_idx)
            # Goodinfo 用 onchange 自動 submit, 等待頁面重新載入
            time.sleep(1)

            from selenium.webdriver.support import expected_conditions as EC
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'table#tblFinDetail'))
            )
            time.sleep(random.uniform(Config.REQUEST_DELAY_MIN, Config.REQUEST_DELAY_MAX))

        except Exception as e:
            logger.warning(f"  ⚠️ 擴展季度失敗 (非致命): {e}")

    def _parse_number(self, text: str) -> Optional[float]:
        """
        解析數字文字,處理逗號、括號、百分比等格式

        Args:
            text: 原始文字

        Returns:
            解析後的浮點數,無法解析則返回 None
        """
        if not text or text.strip() in ('-', 'N/A', '', '--', '－'):
            return None

        text = text.strip()

        # 處理負數 (括號表示法)
        is_negative = False
        if text.startswith('(') and text.endswith(')'):
            is_negative = True
            text = text[1:-1]

        # 移除逗號與百分比符號
        text = text.replace(',', '').replace('%', '').replace('元', '').replace('億', '')

        try:
            value = float(text)
            return -value if is_negative else value
        except ValueError:
            return None

    def _parse_table_to_df(self, table_element) -> Optional[pd.DataFrame]:
        """
        將 HTML table 元素解析為 DataFrame

        Args:
            table_element: Selenium WebElement 或 BeautifulSoup Tag

        Returns:
            解析後的 DataFrame
        """
        try:
            if hasattr(table_element, 'get_attribute'):
                html = table_element.get_attribute('outerHTML')
            else:
                html = str(table_element)

            dfs = pd.read_html(html, header=0)
            if dfs:
                return dfs[0]
            return None
        except Exception as e:
            logger.error(f"表格解析失敗: {e}")
            return None

    # ==================== 個股首頁數據 ====================

    def fetch_stock_info(self, stock_id: str) -> dict:
        """
        抓取個股首頁基本資料

        Args:
            stock_id: 股票代號 (例如 '2330')

        Returns:
            dict: 包含股價、市值、發行股數、Beta 等基本資料
        """
        url = self.URLS['stock_detail'].format(stock_id=stock_id)
        logger.info(f"📊 抓取個股首頁: {stock_id}")

        self._wait_and_get_page(url, wait_selector='table')

        soup = BeautifulSoup(self.driver.page_source, 'lxml')
        full_text = soup.get_text()
        result = {
            '股票代號': stock_id,
            '股票名稱': None,
            '收盤價': None,
            '市值_億': None,
            '發行股數_千股': None,
            'Beta': None,
            '每股淨值': None,
            '本益比': None,
            '股價淨值比': None,
            '殖利率': None,
            '產業分類': None,
        }

        try:
            # ===== 股票名稱 (從 title 取得) =====
            title_tag = soup.find('title')
            if title_tag:
                title_text = title_tag.get_text(strip=True)
                match = re.search(r'\d{4}\s+(\S+)', title_text)
                if match:
                    result['股票名稱'] = match.group(1)

            # ===== 全頁面 tr 搜尋: 遍歷所有 td 配對 =====
            for tr in soup.find_all('tr'):
                cells = tr.find_all(['td', 'th'])
                for idx, cell in enumerate(cells):
                    text = cell.get_text(strip=True)

                    # 市值 (格式: 市值 | 49.66兆 或 市值 | xx億)
                    if text == '市值' and idx + 1 < len(cells):
                        next_text = cells[idx + 1].get_text(strip=True)
                        val = self._parse_market_value(next_text)
                        if val and result['市值_億'] is None:
                            result['市值_億'] = val

                    # 成交股數 (格式: 成交股數 | 150,409萬股)
                    # 用來取得發行股數: 從 header row 找「成交股數」,
                    # 但發行股數在基本資料表的「資本額」旁
                    elif text == '資本額' and idx + 1 < len(cells):
                        next_text = cells[idx + 1].get_text(strip=True)
                        cap_val = self._parse_number(next_text)
                        # 從面值推算: 資本額(億) / 面值(10元) * 1億 / 1000 = 千股
                        # 但這不精確, 改用下面的方法
                        if cap_val and result['發行股數_千股'] is None:
                            result['發行股數_千股'] = cap_val * 10000

                    # 發行股數 (直接抓, 格式: 發行股數 | xx萬股 | xx.xx兆)
                    elif text == '發行股數' and idx + 1 < len(cells):
                        next_text = cells[idx + 1].get_text(strip=True)
                        # 移除「萬股」等後綴
                        m = re.match(r'([\d,]+)', next_text.replace(',', ''))
                        if m:
                            shares = int(m.group(1))  # 股
                            result['發行股數_千股'] = round(shares / 1000)

                    # 產業別
                    elif text == '產業別' and idx + 1 < len(cells):
                        next_text = cells[idx + 1].get_text(strip=True)
                        if next_text and result['產業分類'] is None:
                            result['產業分類'] = next_text

                    # PBR/PER header row 偵測 (header row 後的 value row 有數值)
                    # 結構: tr1=[成交張數, 成交金額, ..., PBR, PER, PEG]
                    #       tr2=[44,684,   852.7億,  ..., 9.94, 31.29, 0.59]
                    elif text == 'PBR':
                        # 找同一 tr 中 PER 的 index (通常在 PBR 後一欄)
                        pbr_idx = idx
                        per_idx = None
                        for j in range(idx + 1, len(cells)):
                            if cells[j].get_text(strip=True) == 'PER':
                                per_idx = j
                                break

                        # 找下一個兄弟 tr (value row)
                        next_tr = tr.find_next_sibling('tr')
                        if next_tr:
                            val_cells = next_tr.find_all(['td', 'th'])
                            if pbr_idx < len(val_cells):
                                val = self._parse_number(val_cells[pbr_idx].get_text(strip=True))
                                if val and result['股價淨值比'] is None:
                                    result['股價淨值比'] = val
                            if per_idx is not None and per_idx < len(val_cells):
                                val = self._parse_number(val_cells[per_idx].get_text(strip=True))
                                if val and result['本益比'] is None:
                                    result['本益比'] = val

                    # 成交價 header row 偵測
                    # 結構: tr1=[成交價, 昨收, 漲跌價, ...]
                    #       tr2=[1915,   1880, +35, ...]
                    elif text == '成交價' and idx == 0:
                        next_tr = tr.find_next_sibling('tr')
                        if next_tr:
                            val_cells = next_tr.find_all(['td', 'th'])
                            if val_cells:
                                val = self._parse_number(val_cells[0].get_text(strip=True))
                                if val and result['收盤價'] is None:
                                    result['收盤價'] = val

                    # Beta 從風險指標表抓取
                    # 結構: tr1=[風險指標, 5日, 10日, 1個月, 3個月, 半年, 1年, 3年, ...]
                    #       tr2=[Beta,    1.04, 1.07, 1.14,  1.33, 1.38, 1.24, 1.38, ...]
                    elif text == 'Beta' and result['Beta'] is None:
                        # 取 1 年 Beta (index 6 from header, 但直接取同 row 的 index)
                        # Beta row: [0]=Beta, [1]=5日, [2]=10日, [3]=1個月, [4]=3個月, [5]=半年, [6]=1年
                        if idx == 0 and len(cells) > 6:
                            val = self._parse_number(cells[6].get_text(strip=True))
                            if val:
                                result['Beta'] = val
                        elif idx == 0 and len(cells) > 1:
                            # fallback: 取第一個可用的 Beta 值
                            for c in cells[1:]:
                                val = self._parse_number(c.get_text(strip=True))
                                if val:
                                    result['Beta'] = val
                                    break

            # ===== nobr 搜尋: Goodinfo 用 nobr 元素包裝 =====
            for nobr in soup.find_all('nobr'):
                text = nobr.get_text(strip=True)

                # 目前淨值 (相鄰 nobr: '目前淨值', '192.74 元')
                if text == '目前淨值':
                    parent = nobr.parent
                    if parent:
                        for sib in parent.find_all('nobr'):
                            sib_text = sib.get_text(strip=True)
                            m = re.search(r'([\d,.]+)\s*元', sib_text)
                            if m:
                                result['每股淨值'] = self._parse_number(m.group(1))
                                break

            # ===== regex 從全文提取 =====
            # EPS (格式: xx年EPSxx.xx 元)
            eps_match = re.search(r'\d+年EPS([\d,.]+)\s*元', full_text)
            if eps_match:
                result['_latest_eps'] = self._parse_number(eps_match.group(1))

            # 殖利率 (格式: x.xx%)
            yield_match = re.search(r'年均現金殖利率.*?\n.*?(\d{4})\s+季\s+[\d.]+\s+\d+\s+[\d.]+\s+[\d,]+\s+([\d.]+)', full_text)
            if yield_match:
                result['殖利率'] = self._parse_number(yield_match.group(2))

            # Fallback: 從 EPS 推算本益比
            if result['本益比'] is None and result['收盤價'] and result.get('_latest_eps'):
                eps = result['_latest_eps']
                if eps > 0:
                    result['本益比'] = round(result['收盤價'] / eps, 2)

            # Beta 預設值 (只有完全找不到時才用預設)
            if result['Beta'] is None:
                logger.warning("⚠️ 無法從風險指標表取得 Beta, 使用預設值 1.0")
                result['Beta'] = 1.0

            logger.info(f"✅ 個股首頁抓取完成: {stock_id} {result.get('股票名稱', '')}")
            for k, v in result.items():
                if v is not None and not k.startswith('_'):
                    logger.info(f"  {k}: {v}")

        except Exception as e:
            logger.error(f"❌ 個股首頁解析失敗: {e}")
            import traceback
            traceback.print_exc()

        return result

    def _parse_market_value(self, text: str) -> Optional[float]:
        """解析市值文字, 處理兆/億單位"""
        if not text:
            return None
        text = text.replace(',', '').strip()
        m = re.match(r'([\d.]+)\s*兆', text)
        if m:
            return float(m.group(1)) * 10000  # 兆 → 億
        m = re.match(r'([\d.]+)\s*億', text)
        if m:
            return float(m.group(1))
        return None

    # ==================== 通用 FinDetail 垂直表解析 ====================

    def _parse_findetail_table(self, soup: BeautifulSoup, field_map: dict) -> dict:
        """
        通用 FinDetail 金額版表格解析器 (垂直式: 行=科目, 列=季度)

        Goodinfo FinDetail 表格結構:
          Header 0: ['分類名', '2025Q3', '2025Q2', ...] — 季度列
          Header 1: ['金額', '％', '金額', '％', ...] — 每季兩欄(金額+百分比)
          數據行:   ['科目名', 金額1, ％1, 金額2, ％2, ...]

        中間會有分段 header (例如 row 27「負債」, row 46「股東權益」),
        這些行的格式與數據行不同, 需要跳過。

        Args:
            soup: BeautifulSoup 物件
            field_map: {Goodinfo科目名: 儲存欄位名} 的映射
                       例如 {'營業收入': '營業收入', '固定資產合計': '固定資產'}

        Returns:
            dict: {'quarters': [...], 'data': {'欄位名': [v1, v2, ...], ...}}
        """
        result = {'quarters': [], 'data': {}}
        for field_key in field_map.values():
            result['data'][field_key] = []

        # 找主表格 (FinDetail 頁面的數據表 id='tblFinDetail')
        table = soup.find('table', id='tblFinDetail')
        if not table:
            logger.error("❌ 找不到 FinDetail 表格 (table#tblFinDetail)")
            return result

        rows = table.find_all('tr')
        if len(rows) < 3:
            return result

        # 從 Header 0 提取季度列表
        header0_cells = rows[0].find_all(['th', 'td'])
        for cell in header0_cells[1:]:  # 跳過第一格 (分類名)
            text = cell.get_text(strip=True)
            if re.match(r'^\d{4}Q\d$', text):
                result['quarters'].append(text)

        num_quarters = len(result['quarters'])
        if num_quarters == 0:
            logger.error("❌ FinDetail 表格中找不到季度")
            return result

        # 解析數據行
        for row in rows[2:]:
            cells = row.find_all(['th', 'td'])
            if len(cells) < 2:
                continue

            label = cells[0].get_text(strip=True)

            # 跳過分段 header 行 (如「負債」、「股東權益」、「業外損益」等)
            # 這些行的 cell 數通常等於 num_quarters+1 (只有季度名, 沒有金額/％對)
            # 或者 label 在 field_map 裡找不到
            if label not in field_map:
                continue

            field_key = field_map[label]

            # 提取每季金額 (跳過百分比欄)
            # 數據行結構: [科目名, 金額1, ％1, 金額2, ％2, ...]
            values = []
            for qi in range(num_quarters):
                val_idx = 1 + qi * 2  # 金額欄: 1, 3, 5, 7, ...
                if val_idx < len(cells):
                    val = self._parse_number(cells[val_idx].get_text(strip=True))
                    values.append(val)
                else:
                    values.append(None)

            result['data'][field_key] = values

        # 驗證: 確保所有欄位都有值, 沒找到的初始化為 None list
        for field_key in field_map.values():
            if not result['data'].get(field_key):
                result['data'][field_key] = [None] * num_quarters

        return result

    # ==================== 資產負債表 ====================

    def fetch_balance_sheet(self, stock_id: str) -> dict:
        """
        抓取資產負債表 (FinDetail 金額版, 季表模式)

        Args:
            stock_id: 股票代號

        Returns:
            dict: 包含各季度資產負債表數據 (金額單位: 億元)
        """
        url = self.URLS['balance_sheet'].format(stock_id=stock_id)
        logger.info(f"📋 抓取資產負債表: {stock_id}")

        self._wait_and_get_page(url, wait_selector='table')
        time.sleep(2)  # 等待表格完全載入
        self._expand_quarters()  # 擴展到 8+ 季以確保前期 TTM

        soup = BeautifulSoup(self.driver.page_source, 'lxml')

        # 資產負債表科目映射 (Goodinfo 科目名 → 儲存欄位名)
        field_map = {
            '現金及約當現金': '現金及約當現金',
            '應收帳款': '應收帳款',
            '應收款項合計': '應收帳款合計',
            '存貨': '存貨',
            '流動資產合計': '流動資產',
            '固定資產合計': '固定資產',
            '資產總額': '總資產',
            '流動負債合計': '流動負債',
            '非流動負債合計': '長期負債',
            '負債總額': '總負債',
            '股本合計': '股本',
            '資本公積合計': '資本公積',
            '保留盈餘合計': '保留盈餘',
            '股東權益總額': '股東權益',
            '每股淨值(元)': 'BPS',
        }

        result = self._parse_findetail_table(soup, field_map)

        logger.info(f"✅ 資產負債表抓取完成: {stock_id} ({len(result.get('quarters', []))} 個季度)")
        return result


    # ==================== 損益表 ====================

    def fetch_income_statement(self, stock_id: str) -> dict:
        """
        抓取損益表 (FinDetail 金額版, 季表模式)

        Args:
            stock_id: 股票代號

        Returns:
            dict: 包含各季度損益表數據 (金額單位: 億元)
        """
        url = self.URLS['income_statement'].format(stock_id=stock_id)
        logger.info(f"📋 抓取損益表: {stock_id}")

        self._wait_and_get_page(url, wait_selector='table')
        time.sleep(2)
        self._expand_quarters()  # 擴展到 8+ 季以確保前期 TTM

        soup = BeautifulSoup(self.driver.page_source, 'lxml')

        # 損益表科目映射
        field_map = {
            '營業收入': '營業收入',
            '營業成本': '營業成本',
            '營業毛利': '營業毛利',
            '營業利益': '營業利益',
            '業外損益合計': '業外損益',
            '稅後淨利': '稅後淨利',
            '每股稅後盈餘(元)': 'EPS',
            '折舊費用': '折舊費用',
        }

        result = self._parse_findetail_table(soup, field_map)

        logger.info(f"✅ 損益表抓取完成: {stock_id} ({len(result.get('quarters', []))} 個季度)")
        return result

    # ==================== 現金流量表 ====================

    def fetch_cashflow(self, stock_id: str) -> dict:
        """
        抓取現金流量表 (FinDetail 金額版, 季表模式)

        現金流量表的 FinDetail 格式較特殊:
          Header 0: ['營業活動', '2025Q3', '2025Q2', ...] — 季度列
          Header 1: ['本期淨利(淨損)', 金額1, 金額2, ...] — 第一行數據
          (沒有「金額 / ％」的 header, 直接是數據)

        Args:
            stock_id: 股票代號

        Returns:
            dict: 包含各季度現金流量表數據 (金額單位: 億元)
        """
        url = self.URLS['cashflow'].format(stock_id=stock_id)
        logger.info(f"📋 抓取現金流量表: {stock_id}")

        self._wait_and_get_page(url, wait_selector='table')
        time.sleep(2)
        self._expand_quarters()  # 擴展到 8+ 季以確保前期 TTM

        soup = BeautifulSoup(self.driver.page_source, 'lxml')
        result = self._parse_cashflow_findetail(soup)

        logger.info(f"✅ 現金流量表抓取完成: {stock_id} ({len(result.get('quarters', []))} 個季度)")
        return result

    def _parse_cashflow_findetail(self, soup: BeautifulSoup) -> dict:
        """
        解析現金流量表 FinDetail (格式與損益表/資產負債表不同)

        現金流量表沒有「金額/％」的 header 列,
        每個數據行直接是: [科目名, 金額1, 金額2, ...]
        中間有分段 header (「投資活動」、「融資活動」等)
        """
        result = {'quarters': [], 'data': {}}

        table = soup.find('table', id='tblFinDetail')
        if not table:
            logger.error("❌ 找不到現金流量表表格 (table#tblFinDetail)")
            return result

        rows = table.find_all('tr')
        if len(rows) < 3:
            return result

        # 從 Header 0 提取季度列表
        header0_cells = rows[0].find_all(['th', 'td'])
        for cell in header0_cells[1:]:
            text = cell.get_text(strip=True)
            if re.match(r'^\d{4}Q\d$', text):
                result['quarters'].append(text)

        num_quarters = len(result['quarters'])
        if num_quarters == 0:
            logger.error("❌ 現金流量表中找不到季度")
            return result

        # 現金流量表科目映射
        field_map = {
            '營業活動之淨現金流入(出)': '營運現金流',
            '投資活動之淨現金流入(出)': '投資現金流',
            '融資活動之淨現金流入(出)': '籌資現金流',
            '本期現金及約當現金增加(減少)數': '淨現金流',
            '折舊費用': '折舊費用',
        }

        for field_key in field_map.values():
            result['data'][field_key] = []

        # 現金流量表: 從 row 1 開始 (row 0 是季度 header)
        # 沒有「金額/％」header, 直接每行一個科目
        for row in rows[1:]:
            cells = row.find_all(['th', 'td'])
            if len(cells) < 2:
                continue

            label = cells[0].get_text(strip=True)
            if label not in field_map:
                continue

            field_key = field_map[label]

            # 每行: [科目名, 金額1, 金額2, ...] (無百分比欄)
            values = []
            for qi in range(num_quarters):
                val_idx = 1 + qi  # 直接連續: 1, 2, 3, ...
                if val_idx < len(cells):
                    val = self._parse_number(cells[val_idx].get_text(strip=True))
                    values.append(val)
                else:
                    values.append(None)

            result['data'][field_key] = values

        # 計算自由現金流 = 營運現金流 + 投資現金流
        cfo = result['data'].get('營運現金流', [])
        cfi = result['data'].get('投資現金流', [])
        result['data']['自由現金流'] = []
        for i in range(num_quarters):
            a = cfo[i] if i < len(cfo) else None
            b = cfi[i] if i < len(cfi) else None
            if a is not None and b is not None:
                result['data']['自由現金流'].append(a + b)
            else:
                result['data']['自由現金流'].append(None)

        # 確保所有欄位都有值
        for field_key in field_map.values():
            if not result['data'].get(field_key):
                result['data'][field_key] = [None] * num_quarters

        return result

    # ==================== 歷史 EPS ====================

    def fetch_historical_eps(self, stock_id: str, years: int = 5) -> dict:
        """
        抓取歷史年度 EPS (用於 Lynch 分類)

        Args:
            stock_id: 股票代號
            years: 需要幾年的數據

        Returns:
            dict: {'年度': [2024, 2023, ...], 'EPS': [val1, val2, ...]}
        """
        url = self.URLS['income_summary'].format(stock_id=stock_id)
        logger.info(f"📋 抓取歷史 EPS: {stock_id} (近 {years} 年)")

        self._wait_and_get_page(url, wait_selector='table#tblDetail')

        # 確保是年表模式 (預設通常是年表)
        soup = BeautifulSoup(self.driver.page_source, 'lxml')

        result = {'年度': [], 'EPS': []}

        target_table = soup.find('table', id='tblDetail')
        if not target_table:
            logger.error("❌ 找不到損益表表格 (table#tblDetail)")
            return result

        rows = target_table.find_all('tr')
        if len(rows) < 3:
            return result

        # Goodinfo StockBzPerformance.asp 年表 data row 結構:
        # Header 0 有 colspan, Header 1 因 rowspan 少了部分欄位, 
        # 導致 header1 和 data row 的欄數不一致。
        # data row 尾部固定為: [..., 稅後EPS, 年增EPS, BPS]
        # 所以用 data[-3] 取 稅後EPS 最穩定

        for row in rows[2:]:
            cells = row.find_all(['td', 'th'])
            if len(cells) < 10:
                continue

            year_text = cells[0].get_text(strip=True)
            if not re.match(r'^\d{4}$', year_text):
                continue

            year = int(year_text)

            # 稅後EPS 在 data row 倒數第 3 欄
            eps_idx = len(cells) - 3
            eps_val = self._parse_number(cells[eps_idx].get_text(strip=True))
            if eps_val is not None:
                result['年度'].append(year)
                result['EPS'].append(eps_val)
                logger.info(f"  {year} EPS: {eps_val}")

            if len(result['年度']) >= years:
                break

        logger.info(f"✅ 歷史 EPS 抓取完成: {stock_id} ({len(result['年度'])} 年)")
        return result

    # ==================== 殖利率 ====================

    def fetch_dividend_yield(self, stock_id: str) -> dict:
        """
        抓取歷史年度殖利率

        來源: StockDividendPolicy.asp, 表格 id='tblDetail'
        預設模式 (現金殖利率) 下:
          Header: 4 rows
          年度合計行 (22 cells): cells[0]=年份, cells[13]=除權/息前利率, cells[15]=年均價利率
          季度子行: cells[0]='∟', 略過

        Args:
            stock_id: 股票代號

        Returns:
            dict: {'年度': [...], '殖利率': [...]}
        """
        url = self.URLS['dividend'].format(stock_id=stock_id)
        logger.info(f"📋 抓取殖利率: {stock_id}")

        self._wait_and_get_page(url, wait_selector='table#tblDetail')
        time.sleep(2)

        soup = BeautifulSoup(self.driver.page_source, 'lxml')

        result = {'年度': [], '殖利率': []}

        table = soup.find('table', id='tblDetail')
        if not table:
            logger.error("❌ 找不到股利政策表格 (table#tblDetail)")
            return result

        rows = table.find_all('tr')

        for row in rows[4:]:  # 跳過 4 行 header
            cells = row.find_all(['td', 'th'])
            if len(cells) < 16:
                continue

            # 年度合計行: cells[0] 文字為四位數年份 (季度子行首格為 '∟')
            year_text = cells[0].get_text(strip=True)
            if not re.match(r'^\d{4}$', year_text):
                continue

            year = int(year_text)

            # cells[15] = 年均價殖利率 (預設模式)
            yield_val = self._parse_number(cells[15].get_text(strip=True))
            if yield_val is not None:
                result['年度'].append(year)
                result['殖利率'].append(yield_val)
                logger.info(f"  {year} 殖利率: {yield_val}%")

        logger.info(f"✅ 殖利率抓取完成: {stock_id} ({len(result['年度'])} 年)")
        return result

    # ==================== 高階整合方法 ====================

    def fetch_all_financial_data(self, stock_id: str) -> dict:
        """
        一次性抓取所有所需財務數據

        Args:
            stock_id: 股票代號

        Returns:
            dict: 包含所有財務數據的完整資料集
        """
        logger.info(f"🚀 開始抓取 {stock_id} 的完整財務數據")

        data = {
            'stock_info': {},
            'balance_sheet': {},
            'income_statement': {},
            'cashflow': {},
            'historical_eps': {},
            'dividend_yield': {},
        }

        try:
            # 1. 個股首頁
            data['stock_info'] = self.fetch_stock_info(stock_id)

            # 2. 資產負債表
            data['balance_sheet'] = self.fetch_balance_sheet(stock_id)

            # 3. 損益表
            data['income_statement'] = self.fetch_income_statement(stock_id)

            # 4. 現金流量表
            data['cashflow'] = self.fetch_cashflow(stock_id)

            # 5. 歷史 EPS
            data['historical_eps'] = self.fetch_historical_eps(stock_id)

            # 6. 殖利率
            data['dividend_yield'] = self.fetch_dividend_yield(stock_id)
            # 將最新殖利率寫入 stock_info
            if data['dividend_yield'].get('殖利率'):
                data['stock_info']['殖利率'] = data['dividend_yield']['殖利率'][0]

            logger.info(f"🎉 {stock_id} 完整財務數據抓取完成!")

        except DataCollectionError as e:
            logger.error(f"❌ 資料抓取失敗: {e}")
            raise

        return data

    def close(self):
        """關閉瀏覽器"""
        if self.driver:
            self.driver.quit()
            logger.info("🔒 瀏覽器已關閉")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
