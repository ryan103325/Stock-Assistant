"""
籌碼面資料抓取模組 — Goodinfo 爬蟲
抓取：法人買賣超、股權分散表、融資融券、分點主力
"""

import time
import re
import requests
from bs4 import BeautifulSoup

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    ),
    'Accept-Language': 'zh-TW,zh;q=0.9',
    'Referer': 'https://goodinfo.tw/',
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def _get(url: str, params: dict = None, retries: int = 3) -> BeautifulSoup | None:
    """帶重試的 GET，回傳 BeautifulSoup 或 None"""
    for i in range(retries):
        try:
            resp = SESSION.get(url, params=params, timeout=20)
            resp.encoding = 'utf-8'
            if resp.status_code == 200:
                return BeautifulSoup(resp.text, 'lxml')
        except Exception as e:
            print(f"[fetcher] 第 {i+1} 次請求失敗: {e}")
        time.sleep(3)
    return None


def _parse_int(s: str) -> int | None:
    """解析帶逗號的整數字串，支援負數"""
    if not s:
        return None
    s = s.strip().replace(',', '').replace(' ', '')
    try:
        return int(s)
    except ValueError:
        return None


def _parse_float(s: str) -> float | None:
    """解析浮點數字串"""
    if not s:
        return None
    s = s.strip().replace(',', '').replace('%', '').replace(' ', '')
    try:
        return float(s)
    except ValueError:
        return None


def fetch_institutional(stock_id: str) -> dict:
    """
    抓取法人買賣超（投信、外資）近 5 日資料
    來源：Goodinfo 法人買賣超彙總
    回傳：
        trust_buy_5d: 投信近5日買賣超張數
        trust_consecutive_days: 投信連續買超天數
        foreign_buy_5d: 外資近5日買賣超張數
        capital_million: 股本（百萬元，用於計算佔比）
    """
    url = f'https://goodinfo.tw/tw/ShowBrokerInfoSummary.asp'
    params = {'STOCK_ID': stock_id, 'CHT_CAT': 'DATE'}
    soup = _get(url, params)

    result = {
        'trust_buy_5d': None,
        'trust_consecutive_days': 0,
        'foreign_buy_5d': None,
        'capital_million': None,
    }

    if not soup:
        return result

    # 找法人買賣超表格
    tables = soup.find_all('table')
    for table in tables:
        rows = table.find_all('tr')
        # 找含「投信」的行
        trust_vals = []
        foreign_vals = []
        for row in rows:
            cells = row.find_all(['td', 'th'])
            texts = [c.get_text(strip=True) for c in cells]
            if len(texts) < 3:
                continue
            # 尋找投信欄位（通常第一欄是日期）
            # Goodinfo 表格結構：日期 | 外資 | 投信 | 自營商 | 合計
            if texts[0] and re.match(r'\d{4}/\d{2}/\d{2}', texts[0]):
                if len(texts) >= 4:
                    foreign_vals.append(_parse_int(texts[1]))
                    trust_vals.append(_parse_int(texts[2]))

        if trust_vals:
            # 取最近 5 筆
            trust_5 = [v for v in trust_vals[:5] if v is not None]
            foreign_5 = [v for v in foreign_vals[:5] if v is not None]
            result['trust_buy_5d'] = sum(trust_5) if trust_5 else 0
            result['foreign_buy_5d'] = sum(foreign_5) if foreign_5 else 0

            # 計算連續買超天數
            consecutive = 0
            for v in trust_vals:
                if v is not None and v > 0:
                    consecutive += 1
                else:
                    break
            result['trust_consecutive_days'] = consecutive
            break

    time.sleep(2)
    return result


def fetch_ownership(stock_id: str) -> dict:
    """
    抓取股權分散表（千張大戶、散戶持股比例）
    來源：Goodinfo 股權分散表
    回傳：
        whale_pct_this: 本週千張大戶持股比例
        whale_pct_last: 上週千張大戶持股比例
        retail_pct_this: 本週100張以下散戶持股比例
        retail_pct_last: 上週100張以下散戶持股比例
        data_date: 資料日期
    """
    url = 'https://goodinfo.tw/tw/StockShareholdingSchedule.asp'
    params = {'STOCK_ID': stock_id}
    soup = _get(url, params)

    result = {
        'whale_pct_this': None,
        'whale_pct_last': None,
        'retail_pct_this': None,
        'retail_pct_last': None,
        'data_date': None,
    }

    if not soup:
        return result

    # Goodinfo 股權分散表：找「1000張以上」和「1-100張」的持股比例
    # 表格通常有兩期資料（本週、上週）
    tables = soup.find_all('table')
    for table in tables:
        rows = table.find_all('tr')
        dates = []
        whale_rows = []
        retail_rows = []

        for row in rows:
            cells = row.find_all(['td', 'th'])
            texts = [c.get_text(strip=True) for c in cells]
            if not texts:
                continue

            # 找日期行
            if texts[0] and re.match(r'\d{4}/\d{2}/\d{2}', texts[0]):
                dates.append(texts[0])

            # 找千張大戶行（1000張以上）
            if texts and ('1,000' in texts[0] or '1000' in texts[0] or '千張' in texts[0]):
                whale_rows.append(texts)

            # 找散戶行（100張以下，通常標示為 1-100 或 100以下）
            if texts and re.search(r'^1-100|^100以下|^1張.*100張', texts[0]):
                retail_rows.append(texts)

        if whale_rows and len(whale_rows[0]) >= 3:
            result['whale_pct_this'] = _parse_float(whale_rows[0][1])
            result['whale_pct_last'] = _parse_float(whale_rows[0][2]) if len(whale_rows[0]) > 2 else None

        if retail_rows and len(retail_rows[0]) >= 3:
            result['retail_pct_this'] = _parse_float(retail_rows[0][1])
            result['retail_pct_last'] = _parse_float(retail_rows[0][2]) if len(retail_rows[0]) > 2 else None

        if dates:
            result['data_date'] = dates[0]

        if result['whale_pct_this'] is not None:
            break

    time.sleep(2)
    return result


def fetch_margin(stock_id: str) -> dict:
    """
    抓取融資融券資料
    來源：Goodinfo 信用交易
    回傳：
        margin_change: 融資增減張數（近5日）
        short_ratio: 券資比（%）
        total_volume: 當日總成交量（張）
    """
    url = 'https://goodinfo.tw/tw/StockMarginTrading.asp'
    params = {'STOCK_ID': stock_id}
    soup = _get(url, params)

    result = {
        'margin_change': None,
        'short_ratio': None,
        'total_volume': None,
    }

    if not soup:
        return result

    tables = soup.find_all('table')
    margin_vals = []
    short_ratios = []

    for table in tables:
        rows = table.find_all('tr')
        for row in rows:
            cells = row.find_all(['td', 'th'])
            texts = [c.get_text(strip=True) for c in cells]
            if not texts or not re.match(r'\d{4}/\d{2}/\d{2}', texts[0]):
                continue
            # Goodinfo 融資融券表格：日期|融資餘額|融資增減|融券餘額|融券增減|券資比
            if len(texts) >= 6:
                margin_vals.append(_parse_int(texts[2]))   # 融資增減
                short_ratios.append(_parse_float(texts[5]))  # 券資比

    if margin_vals:
        # 近5日融資增減合計
        vals_5 = [v for v in margin_vals[:5] if v is not None]
        result['margin_change'] = sum(vals_5) if vals_5 else 0

    if short_ratios:
        result['short_ratio'] = short_ratios[0]  # 最新一日

    time.sleep(2)
    return result


def fetch_broker(stock_id: str) -> dict:
    """
    抓取分點主力資料（近1日、近5日、近20日買超第一名券商）
    來源：Goodinfo 分點進出（公開資料）
    回傳：
        broker_name_1d: 近1日買超第一名券商
        broker_buy_1d: 近1日買超張數
        broker_name_5d: 近5日買超第一名券商
        broker_buy_5d: 近5日買超張數
        broker_name_20d: 近20日買超第一名券商
        broker_buy_20d: 近20日買超張數
        total_volume_1d: 近1日總成交量
        is_geo_broker: 地緣券商（預設 False，需人工確認）
    """
    result = {
        'broker_name_1d': None,
        'broker_buy_1d': None,
        'broker_name_5d': None,
        'broker_buy_5d': None,
        'broker_name_10d': None,
        'broker_buy_10d': None,
        'broker_name_20d': None,
        'broker_buy_20d': None,
        'total_volume_1d': None,
        'is_geo_broker': False,  # 需人工確認
    }

    for period, key_name, key_buy in [
        ('1', 'broker_name_1d', 'broker_buy_1d'),
        ('5', 'broker_name_5d', 'broker_buy_5d'),
        ('10', 'broker_name_10d', 'broker_buy_10d'),
        ('20', 'broker_name_20d', 'broker_buy_20d'),
    ]:
        url = 'https://goodinfo.tw/tw/ShowBrokerInfoSummary.asp'
        params = {
            'STOCK_ID': stock_id,
            'CHT_CAT': 'BROKER',
            'PERIOD': period,
        }
        soup = _get(url, params)
        if not soup:
            continue

        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                texts = [c.get_text(strip=True) for c in cells]
                # 找買超第一名（跳過標題行）
                if len(texts) >= 3 and texts[0] and not re.match(r'券商|名稱|買超', texts[0]):
                    buy_val = _parse_int(texts[1]) if len(texts) > 1 else None
                    if buy_val and buy_val > 0:
                        result[key_name] = texts[0]
                        result[key_buy] = buy_val
                        break
            if result[key_name]:
                break

        time.sleep(2)

    # 抓近1日總成交量（從法人頁面）
    url = f'https://goodinfo.tw/tw/ShowBrokerInfoSummary.asp'
    params = {'STOCK_ID': stock_id, 'CHT_CAT': 'DATE'}
    soup = _get(url, params)
    if soup:
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                texts = [c.get_text(strip=True) for c in cells]
                if texts and re.match(r'\d{4}/\d{2}/\d{2}', texts[0]):
                    # 找總成交量欄位（通常在最後幾欄）
                    for t in texts:
                        vol = _parse_int(t)
                        if vol and vol > 100:
                            result['total_volume_1d'] = vol
                            break
                    break

    return result


def fetch_stock_info(stock_id: str) -> dict:
    """抓取股票基本資訊（名稱、股價、股本）"""
    url = 'https://goodinfo.tw/tw/StockDetail.asp'
    params = {'STOCK_ID': stock_id}
    soup = _get(url, params)

    result = {
        'stock_name': stock_id,
        'current_price': None,
        'capital_million': None,
    }

    if not soup:
        return result

    # 股票名稱
    title = soup.find('title')
    if title:
        m = re.search(r'(\d+)\s+(.+?)\s*[-|]', title.get_text())
        if m:
            result['stock_name'] = m.group(2).strip()

    # 股價（找含「元」的數字）
    for tag in soup.find_all(['td', 'span', 'div']):
        text = tag.get_text(strip=True)
        if re.match(r'^\d+(\.\d+)?$', text):
            val = _parse_float(text)
            if val and 10 < val < 10000:
                result['current_price'] = val
                break

    return result


def fetch_all(stock_id: str) -> dict:
    """
    抓取所有籌碼面資料，回傳整合後的 dict
    """
    print(f"[fetcher] 開始抓取 {stock_id} 籌碼面資料...")

    info = fetch_stock_info(stock_id)
    print(f"[fetcher] 基本資訊: {info}")

    institutional = fetch_institutional(stock_id)
    print(f"[fetcher] 法人資料: {institutional}")

    ownership = fetch_ownership(stock_id)
    print(f"[fetcher] 股權分散: {ownership}")

    margin = fetch_margin(stock_id)
    print(f"[fetcher] 融資融券: {margin}")

    broker = fetch_broker(stock_id)
    print(f"[fetcher] 分點主力: {broker}")

    return {
        **info,
        **institutional,
        **ownership,
        **margin,
        **broker,
        'stock_id': stock_id,
    }
