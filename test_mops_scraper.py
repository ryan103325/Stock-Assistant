# -*- coding: utf-8 -*-
"""
MOPS 內部人持股異動事後申報表 - 爬蟲測試腳本 V2
精確解析表格結構，提取「本月增加」資料
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import time
from bs4 import BeautifulSoup

# ============ MOPS 設定 ============
MOPS_URL = "https://mopsov.twse.com.tw/mops/web/ajax_query6_1"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://mopsov.twse.com.tw/mops/web/query6_1",
    "Content-Type": "application/x-www-form-urlencoded",
    "Accept": "text/html, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
}


def query_insider(session, stock_id):
    """查詢單一公司的內部人持股異動（最新資料）"""
    payload = {
        "encodeURIComponent": "1",
        "step": "1",
        "firstin": "1",
        "off": "0",
        "co_id": stock_id,
        "isnew": "true",
        "TYPEK": "all",
    }
    try:
        resp = session.post(MOPS_URL, data=payload, headers=HEADERS, timeout=15, verify=False)
        resp.encoding = "utf-8"
        return resp.status_code, resp.text
    except Exception as e:
        return -1, str(e)


def parse_insider_increases(html, stock_id, stock_name=""):
    """
    解析 MOPS HTML，提取本月有增加持股的內部人
    
    表格結構（每人一行，7 個 td）：
    td[0]: 身分別
    td[1]: 姓名
    td[2]: 持股種類
    td[3]: 數字群組 - 選任當時/上月實際/截至上月底信託/累計設質/私募股票 (5個數字黏在一起)
    td[4]: 本月增加 - 集中/其它/私募/信託/質權 (5個數字黏在一起)
    td[5]: 本月減少 - 集中/其它/私募/信託/質權解除 (5個數字或7個)
    td[6]: 本月實際持有相關 (多個數字黏在一起)
    
    關鍵：td[4] 就是「本月增加」，包含 5 個數字，我們需要加總
    """
    soup = BeautifulSoup(html, "html.parser")
    results = []

    if "查無資料" in html or "沒有符合條件的資料" in html:
        return results

    tables = soup.find_all("table")
    target_table = None
    for t in tables:
        text = t.get_text()
        if "身份別" in text or "身分別" in text:
            target_table = t
            break

    if not target_table:
        return results

    rows = target_table.find_all("tr")

    for row in rows:
        tds = row.find_all("td")
        # 跳過表頭行 (th) 和非資料行
        if len(tds) < 4:
            continue

        # 取得每個 td 的「子元素文字列表」而非黏在一起的文字
        identity = tds[0].get_text(strip=True)

        # 跳過表頭行（含「身份別」字樣）
        if "身份別" in identity or "身分別" in identity:
            continue

        name = tds[1].get_text(strip=True) if len(tds) > 1 else ""
        stock_type = tds[2].get_text(strip=True) if len(tds) > 2 else ""

        # td[4] = 本月增加 (5個數字)
        if len(tds) > 4:
            increase_td = tds[4]
            # 嘗試用 <br> 或子元素分割數字
            increase_nums = extract_numbers_from_td(increase_td)
            total_increase = sum(increase_nums)
        else:
            total_increase = 0

        if total_increase > 0:
            results.append({
                "stock_id": stock_id,
                "stock_name": stock_name,
                "身分別": identity,
                "姓名": name,
                "持股種類": stock_type,
                "增加股數": total_increase,
                "增加張數": round(total_increase / 1000, 2),
                "增加明細": increase_nums,
            })

    return results


def extract_numbers_from_td(td):
    """
    從 td 元素中提取所有獨立數字
    MOPS 的 td 裡面，數字之間通常用 <br> 或 <br/> 分隔
    """
    nums = []
    
    # 方法 1: 用 strings 迭代器取得所有文字節點
    for text in td.stripped_strings:
        cleaned = text.replace(",", "").replace("\xa0", "").strip()
        if cleaned:
            try:
                nums.append(int(cleaned))
            except ValueError:
                pass

    # 如果方法 1 只拿到一個大數字，嘗試用 <br> 分割
    if len(nums) <= 1:
        # 方法 2: 用 decode_contents 取 HTML，按 <br> 分割
        inner_html = td.decode_contents()
        parts = inner_html.replace("<br/>", "<br>").replace("<BR>", "<br>").split("<br>")
        alt_nums = []
        for part in parts:
            cleaned = BeautifulSoup(part, "html.parser").get_text(strip=True)
            cleaned = cleaned.replace(",", "").replace("\xa0", "").strip()
            if cleaned:
                try:
                    alt_nums.append(int(cleaned))
                except ValueError:
                    pass
        if len(alt_nums) > len(nums):
            nums = alt_nums

    return nums


# ============ 主測試 ============
if __name__ == "__main__":
    session = requests.Session()

    # === 測試: 先用幾檔有名的股票來驗證解析 ===
    test_cases = [
        ("2330", "台積電"),
        ("2317", "鴻海"),
        ("2454", "聯發科"),
        ("3008", "大立光"),
        ("1301", "台塑"),
    ]

    print("=" * 70)
    print("MOPS 內部人持股異動 - 解析測試")
    print("=" * 70)

    all_increases = []

    for stock_id, stock_name in test_cases:
        status, html = query_insider(session, stock_id)
        
        if status != 200:
            print(f"❌ {stock_id} {stock_name}: HTTP {status}")
            continue

        increases = parse_insider_increases(html, stock_id, stock_name)
        
        if increases:
            print(f"\n📈 {stock_id} {stock_name} - 本月有增加:")
            for item in increases:
                print(f"   {item['身分別']} | {item['姓名']} | {item['增加張數']}張 ({item['增加股數']}股)")
                print(f"      明細: {item['增加明細']}")
            all_increases.extend(increases)
        else:
            print(f"   {stock_id} {stock_name}: 本月無增加")

        time.sleep(0.5)

    print(f"\n{'=' * 70}")
    print(f"📊 測試總結: {len(test_cases)} 檔 → 找到 {len(all_increases)} 筆本月增加")
    print(f"{'=' * 70}")

    # === 額外: dump 一個 td 的原始 HTML 看結構 ===
    print("\n\n=== Debug: 2330 原始 td HTML 結構 ===")
    status, html = query_insider(session, "2330")
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")
    for t in tables:
        if "身份別" in t.get_text():
            rows = t.find_all("tr")
            for ri, row in enumerate(rows[:5]):
                tds = row.find_all("td")
                if len(tds) >= 5:
                    print(f"\n--- Row {ri} ---")
                    for ci, td in enumerate(tds):
                        print(f"  td[{ci}] HTML: {td.decode_contents()[:200]}")
                        print(f"  td[{ci}] text: {td.get_text(strip=True)[:100]}")
                        print(f"  td[{ci}] nums: {extract_numbers_from_td(td)}")
            break
