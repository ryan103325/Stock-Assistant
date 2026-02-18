"""
籌碼面資料抓取模組 — Selenium + requests 版

資料來源（已 debug 確認）:
- 法人買賣超: Goodinfo ShowBuySaleChart.asp?CHT_CAT2=DATE  -> id=tblDetail
- 融資融券:   Goodinfo ShowBuySaleChart.asp?CHT_CAT2=MARGIN -> selKCSheet AJAX -> tblDetail
- 股權分散:   Goodinfo EquityDistributionClassHis.asp        -> id=tblDetail
- 主力走勢:   永豐金 API CZCO.DJBCD?A={id}                    -> requests GET
- 券商分點:   永豐金 sinotrade 頁面                            -> Selenium #oMainTable
"""

import time
import random
import re
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from bs4 import BeautifulSoup

GOODINFO_BASE = 'https://goodinfo.tw/tw'
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
]
MAX_RETRIES = 3
RETRY_DELAY = 3

_driver = None


# ================================================================
# WebDriver 管理
# ================================================================

def _get_driver():
    global _driver
    if _driver is not None:
        return _driver

    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument(f'--user-agent={random.choice(USER_AGENTS)}')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_experimental_option('useAutomationExtension', False)

    _driver = webdriver.Chrome(options=options)
    _driver.execute_cdp_cmd(
        'Page.addScriptToEvaluateOnNewDocument',
        {'source': 'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'}
    )
    print("[fetcher] Chrome WebDriver init OK")
    _warmup_cookies()
    return _driver


def _warmup_cookies():
    global _driver
    print("[fetcher] Warming up cookies...")
    try:
        _driver.get(GOODINFO_BASE)
        time.sleep(2)
        for _ in range(5):
            if len(_driver.page_source) > 1000:
                break
            time.sleep(1.5)
        print("[fetcher] Cookie warmup done")
    except Exception as e:
        print(f"[fetcher] Cookie warmup failed (non-fatal): {e}")


def _fetch_page(url: str, timeout: int = 25) -> BeautifulSoup | None:
    """載入頁面，等待頁面大小穩定，回傳 BeautifulSoup"""
    driver = _get_driver()

    for attempt in range(MAX_RETRIES):
        try:
            driver.get(url)
            # 等待頁面大小 > 5000 bytes（排除 redirect 小頁面）
            start = time.time()
            while time.time() - start < timeout:
                if len(driver.page_source) > 5000:
                    break
                time.sleep(2)

            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, 'table'))
                )
            except TimeoutException:
                pass

            time.sleep(random.uniform(1.0, 2.0))
            page = driver.page_source
            if len(page) < 1000:
                print(f"[fetcher] Page too small ({len(page)} bytes), likely blocked: {url}")
                return None
            return BeautifulSoup(page, 'lxml')

        except Exception as e:
            print(f"[fetcher] Page error (attempt {attempt+1}/{MAX_RETRIES}): {e}")
            time.sleep(RETRY_DELAY)

    return None


def cleanup():
    global _driver
    if _driver:
        try:
            _driver.quit()
            print("[fetcher] WebDriver closed")
        except Exception:
            pass
        _driver = None


# ================================================================
# 工具函式
# ================================================================

def _parse_int(s: str) -> int | None:
    if not s:
        return None
    s = s.strip().replace(',', '').replace(' ', '').replace('\xa0', '')
    neg = s.startswith('(') and s.endswith(')')
    if neg:
        s = s[1:-1]
    s = re.sub(r'[^\d\-]', '', s)
    try:
        v = int(s)
        return -v if neg else v
    except ValueError:
        return None


def _parse_float(s: str) -> float | None:
    if not s or s.strip() in ('-', 'N/A', '', '--', '-'):
        return None
    s = s.strip().replace(',', '').replace('%', '').replace('\xa0', '').replace('億', '')
    try:
        return float(s)
    except ValueError:
        return None


def _find_table_by_id(soup: BeautifulSoup, table_id: str):
    return soup.find('table', id=table_id)


# ================================================================
# 法人買賣超
# ================================================================

def fetch_institutional(stock_id: str) -> dict:
    """
    抓取法人買賣超
    URL: ShowBuySaleChart.asp?CHT_CAT2=DATE
    資料表: id=tblDetail
    欄位（已 debug 確認）:
      col[0]=期別, col[4]=成交量, col[7]=外資買賣超, col[12]=投信買賣超
    """
    result = {
        'trust_buy_5d': None,
        'trust_consecutive_days': 0,
        'foreign_buy_5d': None,
        'total_volume_1d': None,
    }

    url = f'{GOODINFO_BASE}/ShowBuySaleChart.asp?STOCK_ID={stock_id}&CHT_CAT2=DATE'
    soup = _fetch_page(url)
    if not soup:
        return result

    table = _find_table_by_id(soup, 'tblDetail')
    if not table:
        print(f"[fetcher] WARNING: institutional tblDetail not found")
        return result

    rows = table.find_all('tr')
    # row[0] = header1: 期別 | 成交 | 漲跌 | 漲跌(%) | 成交量(張) | 外資(買進/賣出/買賣超/持有/持股比) | 投信(買進/賣出/買賣超) | ...
    # row[1] = header2: 買進(張) | 賣出(張) | 買賣超(張) | ...
    # row[2+] = 資料: '26/02/11 | 1915 | +35 | +1.86 | 44,684 | 24,488 | 29,430 | -4,941 | 18,699,093 | 72.1 | 1,362 | 221 | +1,141 | ...

    VOLUME_COL = 4
    FOREIGN_NET_COL = 7
    TRUST_NET_COL = 12

    foreign_vals = []
    trust_vals = []
    volume_1d = None

    for row in rows[2:]:
        cells = row.find_all(['td', 'th'])
        if len(cells) < 13:
            continue
        texts = [c.get_text(strip=True) for c in cells]
        # 確認是日期行
        if not re.match(r"'?\d{2}/\d{2}/\d{2}", texts[0]):
            continue

        vol = _parse_int(texts[VOLUME_COL]) if len(texts) > VOLUME_COL else None
        foreign_net = _parse_int(texts[FOREIGN_NET_COL]) if len(texts) > FOREIGN_NET_COL else None
        trust_net = _parse_int(texts[TRUST_NET_COL]) if len(texts) > TRUST_NET_COL else None

        if vol is not None and volume_1d is None:
            volume_1d = vol
        if foreign_net is not None:
            foreign_vals.append(foreign_net)
        if trust_net is not None:
            trust_vals.append(trust_net)

    result['total_volume_1d'] = volume_1d

    if foreign_vals:
        result['foreign_buy_5d'] = sum(foreign_vals[:5])

    if trust_vals:
        result['trust_buy_5d'] = sum(trust_vals[:5])
        consecutive = 0
        for v in trust_vals:
            if v > 0:
                consecutive += 1
            else:
                break
        result['trust_consecutive_days'] = consecutive

    print(f"[fetcher] Institutional: trust_5d={result['trust_buy_5d']}, "
          f"foreign_5d={result['foreign_buy_5d']}, "
          f"consecutive={result['trust_consecutive_days']}, "
          f"volume={result['total_volume_1d']}")
    return result


# ================================================================
# 融資融券
# ================================================================

def fetch_margin(stock_id: str) -> dict:
    """
    抓取融資融券
    URL: ShowBuySaleChart.asp?CHT_CAT2=MARGIN
    操作：用 Selenium 點選 selKCSheet 下拉選單切換到「融資融券餘額」
    AJAX 更新後 tblDetail 欄位（已 debug 確認）:
      row[0]: 期別 | 收盤 | 漲跌 | 漲跌(%) | 成交(張) | 融資(張) | 融券(張) | ... | 券資比(%)
      row[1]: 買進 | 賣出 | 現償 | 增減 | 餘額 | 使用率 | 買進 | 賣出 | 現償 | 增減 | 餘額 | 使用率
      row[2]: '26/02/11 | 1915 | +35 | +1.86 | 44,684 | 1,535 | 1,353 | 151 | +31 | 21,275 | 0.33 | 18
    融資增減 = col[8]
    券資比 = col[9]
    """
    result = {
        'margin_change': None,
        'short_ratio': None,
    }

    driver = _get_driver()
    url = f'{GOODINFO_BASE}/ShowBuySaleChart.asp?STOCK_ID={stock_id}&CHT_CAT2=MARGIN'
    driver.get(url)

    # 等待頁面載入
    start = time.time()
    while time.time() - start < 20:
        if len(driver.page_source) > 5000:
            break
        time.sleep(2)
    time.sleep(2)

    try:
        from selenium.webdriver.support.ui import Select
        # 找到 selKCSheet 下拉選單
        sel_el = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, 'selKCSheet'))
        )
        sel = Select(sel_el)
        # 找到「融資融券餘額」選項
        for opt in sel.options:
            if '融資融券餘額' in opt.text:
                sel.select_by_value(opt.get_attribute('value'))
                print(f"[fetcher] 選擇融資融券餘額選項")
                break
        time.sleep(4)  # 等待 AJAX 更新
    except Exception as e:
        print(f"[fetcher] WARNING: 無法點選融資融券選項: {e}")
        return result

    soup = BeautifulSoup(driver.page_source, 'lxml')
    table = soup.find('table', id='tblDetail')
    if not table:
        print(f"[fetcher] WARNING: margin tblDetail not found after select")
        return result

    rows = table.find_all('tr')

    # 實際資料行欄位（header 有 colspan）:
    # col[0]=期別, col[1]=收盤, col[2]=漲跌, col[3]=漲跌%, col[4]=成交量
    # col[5~10]=融資(買進/賣出/現償/增減/餘額/使用率)
    # col[11~16]=融券(買進/賣出/現償/增減/餘額/使用率)
    # col[17]=資券互抵, col[18]=資券當沖%, col[19]=券資比%, col[20]=現股當沖%
    MARGIN_CHANGE_COL = 8   # 融資增減
    SHORT_RATIO_COL = 19    # 券資比(%)

    margin_changes = []

    for row in rows[2:]:
        cells = row.find_all(['td', 'th'])
        if len(cells) < 20:
            continue
        texts = [c.get_text(strip=True) for c in cells]
        if not re.match(r"'?\d{2}/\d{2}/\d{2}", texts[0]):
            continue

        mc = _parse_int(texts[MARGIN_CHANGE_COL])
        if mc is not None:
            margin_changes.append(mc)

        if result['short_ratio'] is None:
            sr = _parse_float(texts[SHORT_RATIO_COL])
            if sr is not None and 0 < sr < 100:
                result['short_ratio'] = sr

    if margin_changes:
        result['margin_change'] = sum(margin_changes[:5])

    print(f"[fetcher] Margin: change_5d={result['margin_change']}, short_ratio={result['short_ratio']}")
    return result

# ================================================================
# 股權分散（內部人結構）
# ================================================================

def fetch_ownership(stock_id: str) -> dict:
    """
    抓取股權分散表（內部人結構）
    URL: EquityDistributionClassHis.asp
    資料表: id=tblDetail
    欄位（已 debug 確認）:
      row[0]: 週別 | 統計日期 | 當週股價 | 集保庫存 | 各持股等級股東之持有比例(%)
      row[1]: 收盤 | 漲跌(元) | 漲跌(%) | <=10張 | >10<=50張 | >50<=100張 | >100<=200張 | >200<=400張 | >400<=800張 | >800<=1千張 | >1千張
      row[2]: 26W07 | - | 1915 | ... (未結算，統計日期為 '-')
      row[3]: 26W06 | 02/06 | 1780 | 2593 | 4.81 | 2.67 | 1.04 | 1.04 | 1.41 | 1.93
    散戶 = col[3] (⩽10張)
    大戶 = col[-1] (>1千張)
    """
    result = {
        'whale_pct_this': None,
        'whale_pct_last': None,
        'retail_pct_this': None,
        'retail_pct_last': None,
        'data_date': None,
    }

    url = f'{GOODINFO_BASE}/EquityDistributionClassHis.asp?STOCK_ID={stock_id}'
    soup = _fetch_page(url)
    if not soup:
        return result

    table = _find_table_by_id(soup, 'tblDetail')
    if not table:
        print(f"[fetcher] WARNING: ownership tblDetail not found")
        return result

    rows = table.find_all('tr')
    data_rows = []

    for row in rows[2:]:  # 跳過兩行 header
        cells = row.find_all(['td', 'th'])
        texts = [c.get_text(strip=True) for c in cells]
        if len(texts) < 8:
            continue
        # 第二欄是統計日期（MM/DD 或 '-'）
        # 跳過未結算的週（統計日期為 '-'）
        if texts[1] == '-' or not texts[1]:
            continue
        data_rows.append(texts)
        if len(data_rows) >= 2:
            break

    if data_rows:
        result['data_date'] = data_rows[0][1]  # MM/DD 格式
        for row_idx, row_texts in enumerate(data_rows[:2]):
            # 散戶 = col[3] (⩽10張持股比例)
            # 大戶 = col[-1] (>1千張持股比例)
            retail = _parse_float(row_texts[3]) if len(row_texts) > 3 else None
            whale = _parse_float(row_texts[-1]) if row_texts else None
            if row_idx == 0:
                result['retail_pct_this'] = retail
                result['whale_pct_this'] = whale
            else:
                result['retail_pct_last'] = retail
                result['whale_pct_last'] = whale

    print(f"[fetcher] Ownership: whale={result['whale_pct_this']}, "
          f"retail={result['retail_pct_this']}, date={result['data_date']}")
    return result


# ================================================================
# 股票基本資訊
# ================================================================

def fetch_stock_info(stock_id: str) -> dict:
    """抓取股票名稱、股價"""
    result = {
        'stock_name': stock_id,
        'current_price': None,
    }

    url = f'{GOODINFO_BASE}/StockDetail.asp?STOCK_ID={stock_id}'
    soup = _fetch_page(url)
    if not soup:
        return result

    title = soup.find('title')
    if title:
        m = re.search(r'\d+\s+(\S+)', title.get_text())
        if m:
            result['stock_name'] = m.group(1)

    for tr in soup.find_all('tr'):
        cells = tr.find_all(['td', 'th'])
        texts = [c.get_text(strip=True) for c in cells]
        if texts and texts[0] == '成交價' and len(texts) >= 2:
            next_tr = tr.find_next_sibling('tr')
            if next_tr:
                val_cells = next_tr.find_all(['td', 'th'])
                if val_cells:
                    val = _parse_float(val_cells[0].get_text(strip=True))
                    if val and 1 < val < 100000:
                        result['current_price'] = val
                        break

    print(f"[fetcher] Stock info: {result['stock_name']}, price={result['current_price']}")
    return result


# ================================================================
# 分點主力（永豐金證券）
# ================================================================

SINOTRADE_TREND_API = 'https://stockchannelnew.sinotrade.com.tw/Z/ZC/ZCO/CZCO.DJBCD'
SINOTRADE_BROKER_URL = 'https://www.sinotrade.com.tw/Stock/Stock_3_1/Stock_3_1_6_7'


def fetch_broker_trend(stock_id: str) -> dict:
    """
    主力走勢 API（不需登入，直接 GET）
    回傳三行純文字：日期/收盤價/主力淨買張數
    """
    result = {
        'main_force_net_5d': None,
        'main_force_consecutive': 0,
        'main_force_trend': [],
    }

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://www.sinotrade.com.tw/Stock/Stock_3_1?ch=Stock_3_1_6_7',
        }
        resp = requests.get(
            f'{SINOTRADE_TREND_API}?A={stock_id}',
            headers=headers,
            timeout=10,
            verify=False,
        )
        resp.raise_for_status()

        # API 回傳格式：三段用空格分隔，每段用逗號分隔
        # dates prices nets
        parts = resp.text.strip().split(' ')
        if len(parts) < 3:
            print(f"[fetcher] WARNING: broker trend API returned {len(parts)} parts")
            return result

        dates = parts[0].split(',')
        prices = parts[1].split(',')
        nets = parts[2].split(',')

        trend = []
        for d, p, n in zip(dates, prices, nets):
            try:
                trend.append({'date': d, 'price': int(p), 'net_buy': int(n)})
            except (ValueError, TypeError):
                continue

        result['main_force_trend'] = trend

        # 最近 5 天淨買超合計
        if trend:
            recent = trend[-5:] if len(trend) >= 5 else trend
            result['main_force_net_5d'] = sum(r['net_buy'] for r in recent)

            # 連續買超天數（從最新往回算）
            consecutive = 0
            for r in reversed(trend):
                if r['net_buy'] > 0:
                    consecutive += 1
                else:
                    break
            result['main_force_consecutive'] = consecutive

        print(f"[fetcher] BrokerTrend: net_5d={result['main_force_net_5d']}, "
              f"consecutive={result['main_force_consecutive']}, "
              f"total_days={len(trend)}")

    except Exception as e:
        print(f"[fetcher] WARNING: broker trend fetch failed: {e}")

    return result

def fetch_broker_detail(stock_id: str, period: str = '1') -> dict:
    """
    券商分點明細（需 Selenium 渲染頁面）
    資料在 SysJustIFRAME iframe 內的 #oMainTable
    period: '1'=1日, '2'=5日, '3'=10日, '4'=20日
    row[7]=header, row[8~22]=10-cell 買賣超明細, row[23]=合計
    """
    result = {
        'buy_brokers': [],
        'sell_brokers': [],
        'top_buy_broker': None,
        'top_buy_net': None,
        'top_sell_broker': None,
        'top_sell_net': None,
    }

    driver = _get_driver()
    url = f'{SINOTRADE_BROKER_URL}?ticker={stock_id}'

    try:
        driver.get(url)
        time.sleep(8)

        # 切換到 SysJustIFRAME iframe
        driver.switch_to.frame('SysJustIFRAME')
        time.sleep(3)

        # 選擇期間
        if period != '1':
            try:
                from selenium.webdriver.support.ui import Select
                sel_el = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'select[name="D"]'))
                )
                Select(sel_el).select_by_value(period)
                time.sleep(3)
            except Exception as e:
                print(f"[fetcher] WARNING: period select failed: {e}")

        # 擷取主表格
        soup = BeautifulSoup(driver.page_source, 'lxml')
        table = soup.find(id='oMainTable')
        if not table:
            print(f"[fetcher] WARNING: #oMainTable not found in iframe")
            driver.switch_to.default_content()
            return result

        rows = table.find_all('tr')

        # 解析買超/賣超（只取 10-cell 的資料行，跳過 header 和合計）
        buy_list, sell_list = [], []
        for row in rows:
            cells = row.find_all('td')
            if len(cells) != 10:
                continue
            texts = [c.get_text(strip=True) for c in cells]
            # 跳過 header row（第一欄是「買超券商」）
            if texts[0] == '買超券商':
                continue
            buy_list.append({
                'broker': texts[0], 'buy': texts[1],
                'sell': texts[2], 'net': texts[3], 'ratio': texts[4],
            })
            sell_list.append({
                'broker': texts[5], 'buy': texts[6],
                'sell': texts[7], 'net': texts[8], 'ratio': texts[9],
            })

        result['buy_brokers'] = buy_list
        result['sell_brokers'] = sell_list

        if buy_list:
            result['top_buy_broker'] = buy_list[0]['broker']
            try:
                result['top_buy_net'] = int(buy_list[0]['net'].replace(',', ''))
            except (ValueError, AttributeError):
                pass

        if sell_list:
            result['top_sell_broker'] = sell_list[0]['broker']
            try:
                result['top_sell_net'] = int(sell_list[0]['net'].replace(',', ''))
            except (ValueError, AttributeError):
                pass

        print(f"[fetcher] BrokerDetail(period={period}): "
              f"buy_top={result['top_buy_broker']}({result['top_buy_net']}), "
              f"sell_top={result['top_sell_broker']}({result['top_sell_net']}), "
              f"total_buy={len(buy_list)}, total_sell={len(sell_list)}")

        driver.switch_to.default_content()

    except TimeoutException:
        print(f"[fetcher] WARNING: broker detail page timeout")
        try:
            driver.switch_to.default_content()
        except Exception:
            pass
    except Exception as e:
        print(f"[fetcher] WARNING: broker detail fetch failed: {e}")
        try:
            driver.switch_to.default_content()
        except Exception:
            pass

    return result


# ================================================================
# 整合
# ================================================================

def fetch_all(stock_id: str) -> dict:
    """抓取所有籌碼面資料（法人、融資券、股權分散、分點主力）"""
    print(f"[fetcher] ===== Start fetching {stock_id} =====")

    info = fetch_stock_info(stock_id)
    institutional = fetch_institutional(stock_id)
    ownership = fetch_ownership(stock_id)
    margin = fetch_margin(stock_id)
    broker_trend = fetch_broker_trend(stock_id)
    broker_detail = fetch_broker_detail(stock_id, period='2')  # 近5日

    return {
        **info,
        **institutional,
        **ownership,
        **margin,
        **broker_trend,
        **broker_detail,
        'stock_id': stock_id,
    }
