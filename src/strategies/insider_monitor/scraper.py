# -*- coding: utf-8 -*-
"""
MOPS 內部人持股異動監測器
==========================================
功能：掃描全市場上市櫃公司，找出本月有「增加持股」的內部人
資料來源：公開資訊觀測站 (MOPS) - 內部人持股異動事後申報表
輸出：Discord Webhook 通知

使用方式：
    python -m src.strategies.insider_monitor.scraper [--test] [--force]
"""
import sys
import os
import json
import time
import requests
import urllib3
from datetime import datetime
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ================= 設定 =================
MOPS_URL = "https://mopsov.twse.com.tw/mops/web/ajax_query6_1"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://mopsov.twse.com.tw/mops/web/query6_1",
    "Content-Type": "application/x-www-form-urlencoded",
    "Accept": "text/html, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
}

# 請求間隔 (秒)
REQUEST_DELAY = 0.5

# Discord Webhook
DISCORD_WEBHOOK_URL = os.getenv(
    "DISCORD_WEBHOOK_URL",
    "https://discord.com/api/webhooks/1493221666321469461/nn1JnqVYobmUooKba1kNPaSwPU0u8GBuL-8zLYG0_fMJ9kBY1H1wrKmalYK2c3X-WnkP"
)

# 路徑
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
STOCK_LIST_PATH = os.path.join(BASE_DIR, "docs", "data", "stock_list.json")
OUTPUT_DIR = os.path.join(BASE_DIR, "src", "strategies", "insider_monitor")


# ================= 核心函數 =================

def load_stock_list():
    """讀取股票清單"""
    with open(STOCK_LIST_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    # {id: name}
    return {item["id"]: item["name"] for item in data}


def query_mops(session, stock_id):
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


def extract_numbers_from_td(td):
    """從 td 元素中提取用 <br/> 分隔的數字列表"""
    inner_html = td.decode_contents()
    parts = inner_html.replace("<br/>", "<br>").replace("<BR>", "<br>").split("<br>")
    nums = []
    for part in parts:
        cleaned = BeautifulSoup(part, "html.parser").get_text(strip=True)
        cleaned = cleaned.replace(",", "").replace("\xa0", "").strip()
        if cleaned:
            try:
                nums.append(int(cleaned))
            except ValueError:
                pass
    return nums


def parse_insider_increases(html, stock_id, stock_name=""):
    """
    解析 MOPS HTML，提取本月有增加持股的內部人

    表格每人一行，共 7 個 td:
      td[0]: 身分別
      td[1]: 姓名
      td[2]: 持股種類
      td[3]: 選任/上月/信託/設質/私募 (5 數字)
      td[4]: 本月增加 - 集中/其它原因/私募/信託/質權 (5 數字)
      td[5]: 本月減少 (5-7 數字)
      td[6]: 本月實際持有相關

    回傳: list[dict]
    """
    soup = BeautifulSoup(html, "html.parser")
    results = []

    if "查無資料" in html or "沒有符合條件的資料" in html:
        return results

    # 找含有「身份別」的表格
    tables = soup.find_all("table")
    target_table = None
    for t in tables:
        if "身份別" in t.get_text() or "身分別" in t.get_text():
            target_table = t
            break

    if not target_table:
        return results

    # 去重用 set: (stock_id, 姓名)
    seen_names = set()

    for row in target_table.find_all("tr"):
        tds = row.find_all("td")
        if len(tds) < 5:
            continue

        identity = tds[0].get_text(strip=True)
        if "身份別" in identity or "身分別" in identity:
            continue

        name = tds[1].get_text(strip=True)
        stock_type = tds[2].get_text(strip=True) if len(tds) > 2 else ""

        # td[4] = 本月增加
        increase_nums = extract_numbers_from_td(tds[4])
        total_increase = sum(increase_nums)

        if total_increase <= 0:
            continue

        # 去重: 同一支股票同一個姓名，只保留第一筆
        # 姓名為空時（配偶/子女行），改用「身分別」作 key
        dedup_key = (stock_id, name) if name else (stock_id, identity)
        if dedup_key in seen_names:
            continue
        seen_names.add(dedup_key)

        results.append({
            "stock_id": stock_id,
            "stock_name": stock_name,
            "身分別": identity,
            "姓名": name,
            "持股種類": stock_type,
            "增加股數": total_increase,
            "增加張數": round(total_increase / 1000, 2),
        })

    return results


# ================= Discord 發送 =================

def send_discord(content, username="📊 內部人持股監測"):
    """透過 Discord Webhook 發送訊息（自動切割 2000 字）"""
    if not DISCORD_WEBHOOK_URL:
        print("⚠️ 未設定 DISCORD_WEBHOOK_URL，跳過發送")
        return

    # Discord 限制 2000 字，需要切割
    chunks = split_message(content, max_len=1950)

    for i, chunk in enumerate(chunks):
        payload = {
            "username": username,
            "content": chunk,
        }
        try:
            resp = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
            if resp.status_code in (200, 204):
                print(f"  ✅ Discord 訊息 [{i+1}/{len(chunks)}] 發送成功")
            else:
                print(f"  ❌ Discord 發送失敗: {resp.status_code} {resp.text[:200]}")
            time.sleep(1)  # Discord rate limit
        except Exception as e:
            print(f"  ❌ Discord 發送錯誤: {e}")


def split_message(text, max_len=1950):
    """按行切割訊息，確保不超過 max_len"""
    lines = text.split("\n")
    chunks = []
    current = ""

    for line in lines:
        if len(current) + len(line) + 1 > max_len:
            if current:
                chunks.append(current)
            current = line
        else:
            current = current + "\n" + line if current else line

    if current:
        chunks.append(current)

    return chunks


# ================= 報告格式 =================

def format_report(all_increases):
    """將結果整理成 Discord 可讀的報告"""
    if not all_increases:
        return "📊 **內部人持股異動月報**\n\n本月無任何內部人增加持股。"

    today = datetime.now().strftime("%Y/%m/%d")
    stock_count = len(set(r["stock_id"] for r in all_increases))

    lines = [
        f"📊 **內部人持股異動月報** ({today})",
        f"> 共 **{stock_count}** 檔股票，**{len(all_increases)}** 筆增加紀錄",
        "",
    ]

    # 按股票代號分組
    by_stock = {}
    for r in all_increases:
        key = r["stock_id"]
        if key not in by_stock:
            by_stock[key] = {"name": r["stock_name"], "records": []}
        by_stock[key]["records"].append(r)

    for sid in sorted(by_stock.keys()):
        info = by_stock[sid]
        lines.append(f"**{sid} {info['name']}**")
        for r in info["records"]:
            lots = r["增加張數"]
            lots_str = f"{lots:,.0f}" if lots == int(lots) else f"{lots:,.2f}"
            name_display = r["姓名"] if r["姓名"] else "(配偶/子女)"
            # 簡化身分別
            identity_short = r["身分別"].replace("之配偶及未成年子女", "").replace("之法人代表人", "(法代)")
            lines.append(f"　└ {name_display}：**{lots_str}** 張（{identity_short}）")
        lines.append("")

    return "\n".join(lines)


# ================= 主程式 =================

def run(test_mode=False):
    """
    主流程
    test_mode: 僅測試前 30 檔
    """
    sys.stdout.reconfigure(encoding="utf-8")

    print("=" * 60)
    print("📊 MOPS 內部人持股異動監測器")
    print(f"📅 執行時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 1. 讀取股票清單
    stock_map = load_stock_list()
    stock_ids = sorted(stock_map.keys())
    total = len(stock_ids)

    if test_mode:
        stock_ids = stock_ids[:30]
        print(f"⚠️ 測試模式：僅掃描前 {len(stock_ids)} 檔")
    else:
        print(f"📋 股票清單: {total} 檔")

    # 2. 逐一查詢 MOPS
    session = requests.Session()
    all_increases = []
    success = 0
    fail = 0
    empty = 0

    print(f"\n🚀 開始掃描 MOPS (間隔 {REQUEST_DELAY}s)...\n")
    t_start = time.time()

    for i, sid in enumerate(stock_ids):
        sname = stock_map.get(sid, "")

        status, html = query_mops(session, sid)

        if status != 200:
            fail += 1
            print(f"  ❌ [{i+1}/{len(stock_ids)}] {sid} {sname}: HTTP {status}")
            # 如果連續失敗，增加等待
            time.sleep(3)
            continue

        increases = parse_insider_increases(html, sid, sname)

        if increases:
            success += 1
            all_increases.extend(increases)
            names = ", ".join(f"{r['姓名']}({r['增加張數']}張)" for r in increases)
            print(f"  📈 [{i+1}/{len(stock_ids)}] {sid} {sname}: {names}")
        else:
            empty += 1
            # 只每 100 檔印一次進度
            if (i + 1) % 100 == 0:
                elapsed = time.time() - t_start
                eta = elapsed / (i + 1) * (len(stock_ids) - i - 1)
                print(f"  ⏳ [{i+1}/{len(stock_ids)}] 已掃描 {success} 有增加 / {empty} 無 / {fail} 失敗 (ETA: {eta/60:.1f}分)")

        time.sleep(REQUEST_DELAY)

    elapsed = time.time() - t_start
    print(f"\n✅ 掃描完成！耗時 {elapsed/60:.1f} 分鐘")
    print(f"   有增加: {success} 檔 / 無增加: {empty} 檔 / 失敗: {fail} 檔")
    print(f"   共 {len(all_increases)} 筆增加紀錄")

    # 3. 儲存結果 JSON
    output_file = os.path.join(OUTPUT_DIR, "latest_increases.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_increases, f, ensure_ascii=False, indent=2)
    print(f"💾 結果已存至: {output_file}")

    # 4. 發送 Discord
    if all_increases:
        print("\n📤 發送 Discord 通知...")
        report = format_report(all_increases)
        send_discord(report)
    else:
        print("\n📭 本月無增加，不發送通知")

    return all_increases


if __name__ == "__main__":
    test_mode = "--test" in sys.argv
    run(test_mode=test_mode)
