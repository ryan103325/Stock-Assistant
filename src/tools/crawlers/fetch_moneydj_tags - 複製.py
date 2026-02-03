
# ==========================================
# 🏭 MoneyDJ 細產業分類 爬蟲工具
# ==========================================
# 功能: 爬取 MoneyDJ「產業分類」頁面 (ZH00.djhtm) 的「細產業」清單與成分股
#       直接輸出歸戶後的 CSV (ID, Tag1, Tag2...)
#
# 目標 URL: https://www.moneydj.com/Z/ZH/ZH00.djhtm (via ZHA index)
# 輸出: moneydj_industries_grouped.csv
# ==========================================

import requests
from bs4 import BeautifulSoup
import time
import random
from tqdm import tqdm
import os
import urllib3
from collections import defaultdict

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ================= 設定區 =================
BASE_URL = "https://www.moneydj.com"
INDEX_URL = "https://www.moneydj.com/Z/ZH/ZHA/ZHA.djhtm"

# 檔案路徑
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.dirname(SCRIPT_DIR)  # src
DATA_DIR = os.path.join(SRC_DIR, "data_core")  # src/data_core
GROUPED_FILE = os.path.join(DATA_DIR, "market_meta", "moneydj_industries.csv")

# User-Agent 池
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36"
]

def get_soup(url, verbose=False):
    max_retries = 3
    for attempt in range(max_retries):
        try:
            headers = {"User-Agent": random.choice(USER_AGENTS)}
            resp = requests.get(url, headers=headers, timeout=15, verify=False)
            resp.encoding = 'cp950' # Big5
            if resp.status_code == 200:
                return BeautifulSoup(resp.text, 'html.parser')
            time.sleep(2)
        except Exception as e:
            if verbose: print(f"⚠️ Error: {e}")
            time.sleep(2)
    return None

def main():
    print("🚀 啟動 MoneyDJ 細產業爬蟲 (直接歸戶模式)...")
    
    # ----------------------------------------
    # Step 1: 抓取產業分類索引
    # ----------------------------------------
    print(f"📡 正在請求索引頁: {INDEX_URL}")
    # ----------------------------------------
    # Step 1: 抓取產業分類索引 (含主產業判斷)
    # ----------------------------------------
    print(f"📡 正在請求索引頁: {INDEX_URL}")
    soup_index = get_soup(INDEX_URL, verbose=True)
    if not soup_index: return
    
    category_list = []
    
    # Locate the main table(s) containing the industry list
    # Usually it is in a table with specific class or just explore all tables
    tables = soup_index.find_all('table')
    
    for table in tables:
        rows = table.find_all('tr')
        for row in rows:
            cols = row.find_all('td')
            if not cols: continue
            
            # Context: Col 0 is usually "Main Industry" (e.g. 水泥工業)
            # But sometimes it's also a link.
            # Strategy: Take Col 0 text as "Main Industry"
            main_ind = cols[0].text.strip()
            if not main_ind: continue
            if "產業" in main_ind and len(main_ind) > 10: continue # Skip weird headers
            
            # Find all relevant Detail Industry links in this row
            links = row.find_all('a', href=True)
            for a in links:
                href = a['href']
                text = a.text.strip()
                href_lower = href.lower()
                
                # Check valid link (ZH00 + a=)
                if 'zh00.djhtm' in href_lower and 'a=' in href_lower:
                    if 'Link(' in href: continue
                    if not text: continue
                    
                    if href.startswith('http'): full_url = href
                    elif href.startswith('/'): full_url = BASE_URL + href
                    else: full_url = "https://www.moneydj.com/Z/ZH/ZHA/" + href
                    
                    full_url = full_url.replace('com//', 'com/')
                    
                    # Store with Main Industry
                    category_list.append({
                        'name': text, 
                        'url': full_url,
                        'main_ind': main_ind
                    })

    # Deduplicate (Keep first occurrence to preserve Main Industry association)
    # Use dict to dedupe by URL
    unique_cats = {}
    for cat in category_list:
        if cat['url'] not in unique_cats:
            unique_cats[cat['url']] = cat
    
    category_list = list(unique_cats.values())
    print(f"✅ 找到 {len(category_list)} 個細產業分類 (含主產業標籤)。")
    
    # 初始化儲存結構 (In-Memory)
    stock_groups = defaultdict(set)
    stock_names = {}
    stock_main_ind = {}
    
    # ----------------------------------------
    # Step 2: 深入抓取
    # ----------------------------------------
    try:
        for cat in tqdm(category_list, desc="Scraping", unit="cat"):
            cat_name = cat['name']
            cat_url = cat['url']
            main_ind = cat['main_ind']
            
            time.sleep(random.uniform(0.5, 1.5)) # Safety delay
            
            soup_cat = get_soup(cat_url)
            if not soup_cat: continue
            
            table = soup_cat.find('table', class_='t01')
            if not table: continue
            
            rows = table.find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                if len(cols) < 3: continue
                
                tx0 = cols[0].text.strip()
                if "代號" in tx0 or "名稱" in tx0: continue
                
                # Extract ID and Name
                # User Rule: First 4 digits are ID, rest is Name
                if len(tx0) >= 4:
                    stock_id = tx0[:4]
                    stock_name = tx0[4:].strip()
                    
                    if stock_id.isdigit():
                        # Save Industry
                        stock_groups[stock_id].add(cat_name)
                        # Save Name
                        if stock_name:
                            stock_names[stock_id] = stock_name
                        # Save Main Industry (If not set, or prefer the one that matches sub-ind?)
                        # Logic: First encounter wins, or logic to prioritize? 
                        # User example: 1101 Main=水泥, Sub=水泥. 
                        # If MainInd is not set, set it.
                        if stock_id not in stock_main_ind:
                            stock_main_ind[stock_id] = main_ind

    except KeyboardInterrupt:
        print("\n⚠️ 使用者中斷，正在保存目前進度...")
    except Exception as e:
        print(f"\n❌ 發生錯誤: {e}")
    finally:
        # Step 3: 直接輸出歸戶檔案 (ID, Name, MainInd, Ind1, Ind2...)
        print(f"\n💾 正在儲存歸戶檔案: {GROUPED_FILE}")
        
        if not stock_groups:
             print("⚠️ 警告：沒有抓取到任何資料，不進行存檔。")
             return

        sorted_ids = sorted(stock_groups.keys())
        output_rows = []
        
        for sid in sorted_ids:
            # Sort tags for consistency
            industries = sorted(list(stock_groups[sid]))
            sname = stock_names.get(sid, "")
            m_ind = stock_main_ind.get(sid, "")
            
            # Format: ID, Name, MainInd, Ind1, Ind2...
            row = [sid, sname, m_ind] + industries
            output_rows.append(row)
            
        try:
            with open(GROUPED_FILE, 'w', encoding='utf-8-sig') as f:
                # User requested header row
                f.write("Code,Name,Industry,SubIndustries\n")
                for row in output_rows:
                    f.write(",".join(row) + "\n")
            print(f"✅ 成功儲存 {len(output_rows)} 筆資料。")
        except Exception as e:
            print(f"❌ 存檔失敗: {e}")

if __name__ == "__main__":
    main()
