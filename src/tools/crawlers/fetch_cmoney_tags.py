# -*- coding: utf-8 -*-
"""
CMoney 股票分類爬蟲 (整合版)
同時爬取 Category (產業分類) 與 Concept (概念股)
使用 requests + BeautifulSoup，不需要 Playwright
"""
import os
import csv
import time
import random
import re
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm
import urllib3

# 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 路徑設定
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))  # src/tools/crawlers
TOOLS_DIR = os.path.dirname(SCRIPT_DIR)  # src/tools
SRC_DIR = os.path.dirname(TOOLS_DIR)  # src
DATA_DIR = os.path.join(SRC_DIR, "data_core")  # src/data_core
MARKET_META_DIR = os.path.join(DATA_DIR, "market_meta")  # src/data_core/market_meta

# 輸出檔案（直接放在 market_meta 目錄）
OUTPUT_FILE = os.path.join(MARKET_META_DIR, "cmoney_all_tags.csv")

# URLs
CATEGORY_INDEX_URL = "https://www.cmoney.tw/forum/category"
CONCEPT_INDEX_URL = "https://www.cmoney.tw/forum/concept"

# User-Agent
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]

# 要跳過的標籤清單（非產業/概念類標籤）
SKIP_TAGS = [
    # 排行榜類
    "熱門排行", "人氣排行", "討論度排行", "本日熱門", "本週熱門",
    "漲幅排行", "跌幅排行", "成交量排行", "振幅排行",
    
    # 法人動向類
    "法人買超", "法人賣超", "外資買超", "外資賣超", 
    "投信買超", "投信賣超", "自營商買超", "自營商賣超",
    "三大法人買超", "三大法人賣超",
    
    # 技術面類
    "股價創高", "股價創低", "突破新高", "跌破新低",
    "黃金交叉", "死亡交叉", "KD黃金交叉", "KD死亡交叉",
    "均線糾結", "突破季線", "跌破季線",
    
    # 時間相關
    "今日", "本週", "本月", "近期", "最新",
    
    # 其他
    "高殖利率", "高股息", "低本益比", "高本益比",
    "融資增加", "融券增加", "借券賣出",
    "權證標的", "可轉債", "牛市", "熊市"
]


def should_skip_tag(tag_name: str) -> bool:
    """
    判斷是否要跳過這個標籤
    
    Args:
        tag_name: 標籤名稱
        
    Returns:
        True = 跳過, False = 保留
    """
    # 完全匹配
    if tag_name in SKIP_TAGS:
        return True
    
    # 部分匹配（包含關鍵字）
    skip_keywords = [
        "排行", "人氣", "熱門", "討論度",
        "買超", "賣超", "法人", "外資", "投信", "自營商",
        "創高", "創低", "突破", "跌破",
        "今日", "本週", "本月", "近期", "最新"
    ]
    
    for keyword in skip_keywords:
        if keyword in tag_name:
            return True
    
    # 保留
    return False


def get_soup(url):
    """發送請求並回傳 BeautifulSoup"""
    for attempt in range(3):
        try:
            headers = {"User-Agent": random.choice(USER_AGENTS)}
            resp = requests.get(url, headers=headers, timeout=15, verify=False)
            if resp.status_code == 200:
                return BeautifulSoup(resp.text, 'html.parser')
            time.sleep(1)
        except Exception as e:
            if attempt == 2:
                print(f"  ⚠️ {url}: {e}")
            time.sleep(1)
    return None

def extract_tags_from_index(url, tag_type):
    """從索引頁面提取所有分類/概念連結"""
    print(f"📡 載入 {tag_type} 索引: {url}")
    soup = get_soup(url)
    if not soup:
        return []
    
    tags = []
    # 尋找所有連結
    for a in soup.find_all('a', href=True):
        href = a['href']
        text = a.get_text(strip=True)
        
        # 過濾：category 或 concept 連結
        if f'/forum/{tag_type}/' in href and text:
            # 提取 ID
            match = re.search(r'/forum/' + tag_type + r'/([A-Z0-9]+)', href)
            if match:
                tag_id = match.group(1)
                full_url = f"https://www.cmoney.tw/forum/{tag_type}/{tag_id}"
                tags.append({
                    "id": tag_id,
                    "name": text,
                    "url": full_url,
                    "type": tag_type
                })
    
    # 去重
    seen = set()
    unique_tags = []
    for t in tags:
        if t["id"] not in seen:
            seen.add(t["id"])
            unique_tags.append(t)
    
    print(f"   找到 {len(unique_tags)} 個 {tag_type}")
    return unique_tags

def scrape_tag_stocks(tag_info):
    """爬取單一分類/概念的成分股"""
    soup = get_soup(tag_info["url"])
    if not soup:
        return []
    
    stocks = []
    
    # 方法 1: 尋找 table__stock 連結
    for a in soup.find_all('a', class_='table__stock'):
        title = a.get('title', '')
        if title:
            parts = title.split(' ', 1)
            if len(parts) >= 2:
                code = parts[0].strip()
                name = parts[1].strip()
                if code.isdigit() and len(code) >= 4:
                    stocks.append({
                        "TagId": tag_info["id"],
                        "TagName": tag_info["name"],
                        "TagType": tag_info["type"],
                        "StockCode": code,
                        "StockName": name
                    })
    
    # 方法 2: 尋找 /forum/stock/ 連結 (備用)
    if not stocks:
        for a in soup.find_all('a', href=True):
            href = a['href']
            if '/forum/stock/' in href:
                match = re.search(r'/forum/stock/(\d+)', href)
                if match:
                    code = match.group(1)
                    name = a.get_text(strip=True)
                    if code and name and len(code) >= 4:
                        stocks.append({
                            "TagId": tag_info["id"],
                            "TagName": tag_info["name"],
                            "TagType": tag_info["type"],
                            "StockCode": code,
                            "StockName": name
                        })
    
    return stocks

def main():
    print("🚀 CMoney 整合爬蟲啟動...")
    print("   來源 1: category (產業分類)")
    print("   來源 2: concept (概念股)")
    
    os.makedirs(MARKET_META_DIR, exist_ok=True)
    
    # 1. 載入 category 索引
    categories = extract_tags_from_index(CATEGORY_INDEX_URL, "category")
    
    # 2. 載入 concept 索引
    concepts = extract_tags_from_index(CONCEPT_INDEX_URL, "concept")
    
    # 3. 合併所有標籤
    all_tags = categories + concepts
    print(f"\n📊 總計 {len(all_tags)} 個標籤待爬取")
    
    # 4. 載入已爬取的標籤 (斷點續爬)
    existing_tags = set()
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_tags.add(row.get("TagId"))
    
    remaining_tags = [t for t in all_tags if t["id"] not in existing_tags]
    print(f"   已完成 {len(existing_tags)}，剩餘 {len(remaining_tags)}")
    
    if not remaining_tags:
        print("✅ 所有標籤已爬取完畢！")
        return
    
    # 5. 爬取成分股
    all_stocks = []
    skipped_count = 0
    
    for i, tag in enumerate(tqdm(remaining_tags, desc="爬取中")):
        # ✨ 新增：過濾無效標籤
        if should_skip_tag(tag["name"]):
            skipped_count += 1
            continue
        
        stocks = scrape_tag_stocks(tag)
        all_stocks.extend(stocks)
        
        # 每 20 個標籤儲存一次
        if (i + 1) % 20 == 0:
            save_stocks(all_stocks, append=True)
            all_stocks = []
        
        time.sleep(random.uniform(0.3, 0.8))
    
    print(f"   已跳過 {skipped_count} 個非產業標籤")
    
    # 6. 儲存剩餘結果
    if all_stocks:
        save_stocks(all_stocks, append=True)
    
    # 7. 統計
    print_stats()

def save_stocks(stocks, append=False):
    """儲存股票資料"""
    if not stocks:
        return
    
    mode = 'a' if append and os.path.exists(OUTPUT_FILE) else 'w'
    write_header = mode == 'w'
    
    with open(OUTPUT_FILE, mode, encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=["TagId", "TagName", "TagType", "StockCode", "StockName"])
        if write_header:
            writer.writeheader()
        writer.writerows(stocks)

def print_stats():
    """印出統計資訊"""
    if not os.path.exists(OUTPUT_FILE):
        return
    
    import pandas as pd
    df = pd.read_csv(OUTPUT_FILE)
    
    print(f"\n✅ 完成！總計 {len(df)} 筆資料")
    print(f"   Category: {len(df[df['TagType'] == 'category'])} 筆")
    print(f"   Concept:  {len(df[df['TagType'] == 'concept'])} 筆")
    
    # 前 10 大標籤
    top_tags = df.groupby('TagName')['StockCode'].nunique().sort_values(ascending=False).head(10)
    print("\n📊 前 10 大標籤:")
    for name, count in top_tags.items():
        print(f"   {name}: {count} 檔")

if __name__ == "__main__":
    main()
