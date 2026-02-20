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
    抓取法人買賣超（20天日線含三大法人）
    URL: ShowBuySaleChart.asp?CHT_CAT2=DATE
    資料表: id=tblDetail
    欄位（已 debug 確認 19 cols）:
      col[0]=期別, col[4]=成交量
      col[5~7]=外資(買/賣/淨), col[8~9]=外資持有+持股比
      col[10~12]=投信(買/賣/淨)
      col[13~15]=自營商(買/賣/淨)
      col[16~18]=三大法人合計(買/賣/淨)
    """
    result = {
        'trust_buy_5d': None,
        'trust_consecutive_days': 0,
        'foreign_buy_5d': None,
        'dealer_buy_5d': None,
        'total_volume_1d': None,
        'institutional_daily': [],  # 最近20天日線
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

    VOLUME_COL = 4
    FOREIGN_NET_COL = 7
    TRUST_NET_COL = 12
    DEALER_NET_COL = 15

    daily_data = []
    volume_1d = None

    for row in rows[2:]:
        cells = row.find_all(['td', 'th'])
        if len(cells) < 13:
            continue
        texts = [c.get_text(strip=True) for c in cells]
        if not re.match(r"'?\d{2}/\d{2}/\d{2}", texts[0]):
            continue

        vol = _parse_int(texts[VOLUME_COL]) if len(texts) > VOLUME_COL else None
        foreign_net = _parse_int(texts[FOREIGN_NET_COL]) if len(texts) > FOREIGN_NET_COL else None
        trust_net = _parse_int(texts[TRUST_NET_COL]) if len(texts) > TRUST_NET_COL else None
        dealer_net = _parse_int(texts[DEALER_NET_COL]) if len(texts) > DEALER_NET_COL else None

        if vol is not None and volume_1d is None:
            volume_1d = vol

        daily_data.append({
            'date': texts[0].lstrip("'"),
            'volume': vol,
            'foreign_net': foreign_net,
            'trust_net': trust_net,
            'dealer_net': dealer_net,
        })
        if len(daily_data) >= 20:
            break

    result['total_volume_1d'] = volume_1d
    result['institutional_daily'] = daily_data

    # 彙總
    foreign_vals = [d['foreign_net'] for d in daily_data if d['foreign_net'] is not None]
    trust_vals = [d['trust_net'] for d in daily_data if d['trust_net'] is not None]
    dealer_vals = [d['dealer_net'] for d in daily_data if d['dealer_net'] is not None]

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
    if dealer_vals:
        result['dealer_buy_5d'] = sum(dealer_vals[:5])

    # 各法人連續天數
    def _count_consecutive(vals):
        cnt = 0
        for v in vals:
            if v > 0:
                cnt += 1
            else:
                break
        return cnt

    result['foreign_consecutive_days'] = _count_consecutive(foreign_vals) if foreign_vals else 0
    result['dealer_consecutive_days'] = _count_consecutive(dealer_vals) if dealer_vals else 0

    print(f"[fetcher] Institutional: trust_5d={result['trust_buy_5d']}, "
          f"foreign_5d={result['foreign_buy_5d']}, dealer_5d={result['dealer_buy_5d']}, "
          f"consecutive(trust/foreign/dealer)={result['trust_consecutive_days']}/"
          f"{result['foreign_consecutive_days']}/{result['dealer_consecutive_days']}, "
          f"volume={result['total_volume_1d']}, daily_rows={len(daily_data)}")
    return result


# ================================================================
# 融資融券
# ================================================================

def fetch_margin(stock_id: str) -> dict:
    """
    抓取融資融券
    URL: ShowBuySaleChart.asp?CHT_CAT2=MARGIN
    操作：用 Selenium 點選 selKCSheet 下拉選單切換到「融資融券餘額」
    AJAX 更新後 tblDetail 欄位（共 21 欄）:
      col[0]=期別, col[1]=收盤, col[2]=漲跌, col[3]=漲跌%, col[4]=成交量
      col[5]=融資買進, col[6]=融資賣出, col[7]=融資現償, col[8]=融資增減,
      col[9]=融資餘額, col[10]=融資使用率
      col[11]=融券買進, col[12]=融券賣出, col[13]=融券現償, col[14]=融券增減,
      col[15]=融券餘額, col[16]=融券使用率
      col[17]=資券互抵, col[18]=資券當沖%, col[19]=券資比%, col[20]=現股當沖%
    """
    result = {
        'margin_change': None,
        'short_ratio': None,
        'margin_daily': [],  # 最近5日每日 {date, margin_change, short_change}
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
    SHORT_CHANGE_COL = 14   # 融券增減
    SHORT_RATIO_COL = 19    # 券資比(%)

    margin_daily = []

    for row in rows[2:]:
        cells = row.find_all(['td', 'th'])
        if len(cells) < 20:
            continue
        texts = [c.get_text(strip=True) for c in cells]
        if not re.match(r"'?\d{2}/\d{2}/\d{2}", texts[0]):
            continue

        mc = _parse_int(texts[MARGIN_CHANGE_COL])
        sc = _parse_int(texts[SHORT_CHANGE_COL]) if len(texts) > SHORT_CHANGE_COL else None
        margin_daily.append({
            'date': texts[0].lstrip("'"),
            'margin_change': mc,
            'short_change': sc,
        })

        if result['short_ratio'] is None:
            sr = _parse_float(texts[SHORT_RATIO_COL])
            if sr is not None and 0 < sr < 100:
                result['short_ratio'] = sr

        if len(margin_daily) >= 5:
            break

    result['margin_daily'] = margin_daily
    if margin_daily:
        result['margin_change'] = sum(d['margin_change'] or 0 for d in margin_daily)
        result['short_change'] = sum(d['short_change'] or 0 for d in margin_daily)

    print(f"[fetcher] Margin: change_5d={result['margin_change']}, short_5d={result.get('short_change')}, short_ratio={result['short_ratio']}, daily_rows={len(margin_daily)}")
    return result

# ================================================================
# 股東結構（神秘金字塔 norway.twsthr.info）
# ================================================================

NORWAY_BASE = 'https://norway.twsthr.info'

def fetch_ownership(stock_id: str) -> dict:
    """
    從神秘金字塔抓取股東結構（最多 50 週趨勢）
    URL: StockHolders.aspx?stock={id}
    資料表: table[9] id=Details (16 cols)
    欄位（已 debug 確認）:
      col[2]=資料日期, col[3]=集保總張數, col[4]=總股東人數,
      col[5]=平均張數/人, col[6]=>400張大股東持有張數,
      col[7]=>400張大股東持有百分比, col[8]=>400張大股東人數,
      col[13]=>1000張大股東持有百分比, col[14]=收盤價
    散戶 = 總股東人數 - >400張大股東人數
    """
    result = {
        'whale_pct_this': None,
        'whale_pct_last': None,
        'retail_pct_this': None,
        'retail_pct_last': None,
        'total_holders_this': None,
        'avg_shares_this': None,
        'data_date': None,
        'ownership_weekly': [],  # 最多50週趨勢
    }

    # 優先用 Selenium（帶真實瀏覽器 fingerprint，可繞過 CI IP 封鎖）
    soup = None
    try:
        driver = _get_driver()
        driver.get(f'{NORWAY_BASE}/StockHolders.aspx?stock={stock_id}')
        # 等待 Details table 出現
        start = time.time()
        while time.time() - start < 20:
            if len(driver.page_source) > 5000:
                break
            time.sleep(1.5)
        time.sleep(random.uniform(1.0, 2.0))
        page = driver.page_source
        if len(page) > 5000:
            soup = BeautifulSoup(page, 'lxml')
            print(f"[fetcher] Ownership: fetched via Selenium ({len(page)} bytes)")
        else:
            print(f"[fetcher] WARNING: ownership page too small ({len(page)} bytes), trying requests")
    except Exception as e:
        print(f"[fetcher] WARNING: ownership Selenium failed: {e}, falling back to requests")

    # Fallback: requests
    if soup is None:
        try:
            headers = {
                'User-Agent': random.choice(USER_AGENTS),
                'Referer': f'{NORWAY_BASE}/StockHolders.aspx',
            }
            resp = requests.get(
                f'{NORWAY_BASE}/StockHolders.aspx?stock={stock_id}',
                headers=headers,
                timeout=15,
            )
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'lxml')
            print(f"[fetcher] Ownership: fetched via requests fallback")
        except Exception as e:
            print(f"[fetcher] WARNING: ownership fetch failed (both methods): {e}")
            return result

    # 找 table id=Details 且 row[0] 含 '資料日期' 和 16 cols
    details_tables = soup.find_all('table', id='Details')
    target_table = None
    for t in details_tables:
        first_row = t.find('tr')
        if first_row:
            cells = first_row.find_all(['td', 'th'])
            if len(cells) == 16:
                target_table = t
                break

    if not target_table:
        print(f"[fetcher] WARNING: ownership Details table not found")
        return result

    rows = target_table.find_all('tr')
    weekly_data = []

    for row in rows:
        cells = row.find_all(['td', 'th'])
        if len(cells) != 16:
            continue
        texts = [c.get_text(strip=True) for c in cells]
        # col[2] = 日期 (YYYYMMDD)
        date_str = texts[2]
        if not re.match(r'\d{8}', date_str):
            continue

        total_holders = _parse_int(texts[4])
        avg_shares = _parse_float(texts[5])
        whale_400_pct = _parse_float(texts[7])   # >400張大股東持有百分比
        whale_400_count = _parse_int(texts[8])    # >400張大股東人數
        whale_1000_pct = _parse_float(texts[13])  # >1000張持有百分比
        price = _parse_float(texts[14])

        # 散戶人數 = 總股東人數 - 400張以上大股東人數
        retail_count = None
        retail_pct = None
        if total_holders is not None and whale_400_count is not None:
            retail_count = total_holders - whale_400_count
            # 散戶持股比 = 100% - 大戶持股比
            if whale_400_pct is not None:
                retail_pct = round(100.0 - whale_400_pct, 2)

        weekly_data.append({
            'date': date_str,
            'total_holders': total_holders,
            'avg_shares': avg_shares,
            'whale_400_pct': whale_400_pct,
            'whale_1000_pct': whale_1000_pct,
            'retail_count': retail_count,
            'retail_pct': retail_pct,
            'price': price,
        })
        if len(weekly_data) >= 50:
            break

    result['ownership_weekly'] = weekly_data

    if weekly_data:
        latest = weekly_data[0]
        result['data_date'] = latest['date']
        result['whale_pct_this'] = latest['whale_400_pct']
        result['total_holders_this'] = latest['total_holders']
        result['avg_shares_this'] = latest['avg_shares']
        result['retail_pct_this'] = latest['retail_pct']

    if len(weekly_data) >= 2:
        last = weekly_data[1]
        result['whale_pct_last'] = last['whale_400_pct']
        result['retail_pct_last'] = last['retail_pct']

    print(f"[fetcher] Ownership(norway): whale={result['whale_pct_this']}, "
          f"retail={result['retail_pct_this']}, holders={result['total_holders_this']}, "
          f"avg_shares={result['avg_shares_this']}, date={result['data_date']}, "
          f"weeks={len(weekly_data)}")
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
    period: '1'=1日, '2'=5日, '3'=10日, '4'=20日, '5'=40日, '6'=60日
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

def fetch_broker_all_periods(stock_id: str) -> dict:
    """
    用同一個 WebDriver session 依序抓取五個期間的分點明細。
    先載入頁面一次，然後用 select 切換期間。
    period mapping: 1=1日, 2=5日, 3=10日, 4=20日, 6=60日
    """
    periods = {
        '1d': '1',
        '5d': '2',
        '10d': '3',
        '20d': '4',
        '60d': '6',
    }
    result = {}

    driver = _get_driver()
    url = f'{SINOTRADE_BROKER_URL}?ticker={stock_id}'

    try:
        driver.get(url)
        time.sleep(8)
        driver.switch_to.frame('SysJustIFRAME')
        time.sleep(3)

        for label, period_val in periods.items():
            try:
                if period_val != '1':  # 第一次載入就是近一日，但我們先切到該期間
                    from selenium.webdriver.support.ui import Select
                    sel_el = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, 'select[name="D"]'))
                    )
                    Select(sel_el).select_by_value(period_val)
                    time.sleep(3)

                soup = BeautifulSoup(driver.page_source, 'lxml')
                table = soup.find(id='oMainTable')
                if not table:
                    print(f"[fetcher] WARNING: #oMainTable not found for period {label}")
                    result[f'broker_{label}'] = {'buy_brokers': [], 'sell_brokers': []}
                    continue

                rows = table.find_all('tr')
                buy_list, sell_list = [], []
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) != 10:
                        continue
                    texts = [c.get_text(strip=True) for c in cells]
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

                period_data = {
                    'buy_brokers': buy_list,
                    'sell_brokers': sell_list,
                }
                if buy_list:
                    period_data['top_buy_broker'] = buy_list[0]['broker']
                    try:
                        period_data['top_buy_net'] = int(buy_list[0]['net'].replace(',', ''))
                    except (ValueError, AttributeError):
                        period_data['top_buy_net'] = None
                if sell_list:
                    period_data['top_sell_broker'] = sell_list[0]['broker']
                    try:
                        period_data['top_sell_net'] = int(sell_list[0]['net'].replace(',', ''))
                    except (ValueError, AttributeError):
                        period_data['top_sell_net'] = None

                result[f'broker_{label}'] = period_data
                print(f"[fetcher] BrokerDetail({label}): "
                      f"buy_top={period_data.get('top_buy_broker')}({period_data.get('top_buy_net')}), "
                      f"sell_top={period_data.get('top_sell_broker')}({period_data.get('top_sell_net')})")

            except Exception as e:
                print(f"[fetcher] WARNING: broker period {label} failed: {e}")
                result[f'broker_{label}'] = {'buy_brokers': [], 'sell_brokers': []}

        driver.switch_to.default_content()

    except Exception as e:
        print(f"[fetcher] WARNING: broker all periods failed: {e}")
        try:
            driver.switch_to.default_content()
        except Exception:
            pass

    # 向後相容：將 5d 的 top 資料放到根層級
    if 'broker_5d' in result:
        bd = result['broker_5d']
        result['top_buy_broker'] = bd.get('top_buy_broker')
        result['top_buy_net'] = bd.get('top_buy_net')
        result['top_sell_broker'] = bd.get('top_sell_broker')
        result['top_sell_net'] = bd.get('top_sell_net')
        result['buy_brokers'] = bd.get('buy_brokers', [])
        result['sell_brokers'] = bd.get('sell_brokers', [])

    return result


def fetch_all(stock_id: str) -> dict:
    """抓取所有籌碼面資料（法人、股東結構、融資券、分點主力）"""
    print(f"[fetcher] ===== Start fetching {stock_id} =====")

    info = fetch_stock_info(stock_id)
    institutional = fetch_institutional(stock_id)
    ownership = fetch_ownership(stock_id)
    margin = fetch_margin(stock_id)
    broker_trend = fetch_broker_trend(stock_id)
    broker_all = fetch_broker_all_periods(stock_id)

    return {
        **info,
        **institutional,
        **ownership,
        **margin,
        **broker_trend,
        **broker_all,
        'stock_id': stock_id,
    }
