# === 使用 TWSE/TPEx 官方 API 補齊歷史資料 ===
# 用途：補齊指定月份的股票資料（無速度限制）
# 優點：官方資料、快速、無需 Token

import os
import sys
import time
import requests
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# ================= 設定區 =================
SRC_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_FOLDER = os.path.join(SRC_ROOT, "data_core", "history")

# 目標月份 (YYYYMM 格式)
TARGET_MONTH = "202602"  # 2026年2月

# 限速設定（避免被封鎖）
REQUEST_DELAY = 1.0  # 秒 - 增加延遲避免 rate limit

# ================= 核心函數 =================

def get_stock_list():
    """從現有 CSV 檔案取得股票清單"""
    csv_files = [f.replace('.csv', '') for f in os.listdir(DATA_FOLDER) if f.endswith('.csv')]
    return sorted(csv_files)

def fetch_twse_monthly(stock_id: str, date_str: str = None) -> list:
    """
    使用 TWSE 官方 API 抓取單一股票的月資料
    date_str: YYYYMMDD 格式，會自動抓取該月份全部資料
    """
    if date_str is None:
        date_str = TARGET_MONTH + "01"  # 該月第一天
    
    url = f"https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY?date={date_str}&stockNo={stock_id}&response=json"
    
    try:
        requests.packages.urllib3.disable_warnings()
        r = requests.get(url, verify=False, timeout=15)
        
        if r.status_code != 200:
            return []
        
        data = r.json()
        
        if data.get('stat') != 'OK' or 'data' not in data:
            return []
        
        # 解析資料
        # fields: ["日期","成交股數","成交金額","開盤價","最高價","最低價","收盤價","漲跌價差","成交筆數","註記"]
        results = []
        for row in data['data']:
            try:
                # 日期轉換 (115/02/03 -> 2026-02-03)
                date_parts = row[0].split('/')
                y = int(date_parts[0]) + 1911
                m = date_parts[1]
                d = date_parts[2]
                date_ad = f"{y}-{m}-{d}"
                
                # 數值處理 (去除逗號)
                vol = float(row[1].replace(',', ''))
                amount = float(row[2].replace(',', ''))
                op = float(row[3].replace(',', ''))
                hi = float(row[4].replace(',', ''))
                lo = float(row[5].replace(',', ''))
                cl = float(row[6].replace(',', ''))
                
                results.append({
                    'Date': date_ad,
                    'Open': op,
                    'High': hi,
                    'Low': lo,
                    'Close': cl,
                    'Volume': vol,
                    'Amount': amount
                })
            except:
                continue
        
        return results
        
    except Exception as e:
        return []

def fetch_tpex_monthly(stock_id: str, date_str: str = None) -> list:
    """
    使用 TPEx 官方 API 抓取單一股票的月資料
    date_str: YYYY/MM/DD 格式
    """
    if date_str is None:
        # 轉換格式 202602 -> 2026/02/01
        y = TARGET_MONTH[:4]
        m = TARGET_MONTH[4:6]
        date_str = f"{y}/{m}/01"
    
    url = f"https://www.tpex.org.tw/www/zh-tw/afterTrading/tradingStock?date={date_str}&code={stock_id}&response=json"
    
    try:
        requests.packages.urllib3.disable_warnings()
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, verify=False, timeout=15)
        
        if r.status_code != 200:
            return []
        
        data = r.json()
        
        if data.get('stat') != 'ok' or 'tables' not in data or not data['tables']:
            return []
        
        # TPEx 格式: ["日 期","成交張數","成交仟元","開盤","最高","最低","收盤","漲跌","筆數"]
        results = []
        for table in data.get('tables', []):
            if 'data' not in table:
                continue
            
            for row in table['data']:
                try:
                    # 日期轉換 (115/02/03 -> 2026-02-03)
                    date_parts = row[0].split('/')
                    y = int(date_parts[0]) + 1911
                    m = date_parts[1].zfill(2)
                    d = date_parts[2].zfill(2)
                    date_ad = f"{y}-{m}-{d}"
                    
                    # 欄位順序: 日期, 成交張數, 成交仟元, 開盤, 最高, 最低, 收盤, 漲跌, 筆數
                    vol_lots = float(str(row[1]).replace(',', ''))  # 張數
                    amount_k = float(str(row[2]).replace(',', ''))  # 千元
                    op = float(str(row[3]).replace(',', ''))
                    hi = float(str(row[4]).replace(',', ''))
                    lo = float(str(row[5]).replace(',', ''))
                    cl = float(str(row[6]).replace(',', ''))
                    
                    # 轉換單位
                    vol = vol_lots * 1000  # 張 -> 股
                    amount = amount_k * 1000  # 千元 -> 元
                    
                    results.append({
                        'Date': date_ad,
                        'Open': op,
                        'High': hi,
                        'Low': lo,
                        'Close': cl,
                        'Volume': vol,
                        'Amount': amount
                    })
                except:
                    continue
        
        return results
        
    except Exception as e:
        return []

def update_stock_csv(stock_id: str, new_data: list) -> int:
    """將新資料合併到現有 CSV，返回新增的行數"""
    if not new_data:
        return 0
    
    file_path = os.path.join(DATA_FOLDER, f"{stock_id}.csv")
    
    new_df = pd.DataFrame(new_data)
    
    if not os.path.exists(file_path):
        new_df.to_csv(file_path, index=False, float_format='%.2f')
        return len(new_df)
    
    try:
        df_old = pd.read_csv(file_path)
        existing_dates = set(df_old['Date'].astype(str).tolist())
        
        # 只保留新日期的資料
        new_rows = [r for r in new_data if r['Date'] not in existing_dates]
        
        if len(new_rows) == 0:
            return 0
        
        new_rows_df = pd.DataFrame(new_rows)
        df_merged = pd.concat([df_old, new_rows_df], ignore_index=True)
        df_merged = df_merged.drop_duplicates(subset=['Date'], keep='last')
        df_merged = df_merged.sort_values('Date')
        
        df_merged.to_csv(file_path, index=False, float_format='%.2f')
        return len(new_rows)
        
    except Exception as e:
        print(f"❌ 合併錯誤 {stock_id}: {e}")
        return 0

def main():
    """主程式：補齊歷史資料"""
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8')
    
    print("=" * 60)
    print("📅 TWSE/TPEx 歷史資料補齊腳本 (官方 API)")
    print(f"📁 資料目錄: {DATA_FOLDER}")
    print(f"📆 目標月份: {TARGET_MONTH[:4]}/{TARGET_MONTH[4:]}")
    print("=" * 60)
    
    # 取得股票清單
    stocks = get_stock_list()
    print(f"📋 發現 {len(stocks)} 檔股票需要處理")
    
    # 預估時間
    est_minutes = len(stocks) * REQUEST_DELAY / 60
    print(f"⏱️ 預估時間: {est_minutes:.1f} 分鐘")
    print("-" * 60)
    
    # 逐一更新
    updated_count = 0
    twse_count = 0
    tpex_count = 0
    start_time = time.time()
    
    for i, stock_id in enumerate(stocks):
        print(f"[{i+1}/{len(stocks)}] {stock_id}...", end=" ")
        
        # 先試 TWSE (上市)
        data = fetch_twse_monthly(stock_id)
        source = "TWSE"
        
        # 沒資料就試 TPEx (上櫃)
        if not data:
            data = fetch_tpex_monthly(stock_id)
            source = "TPEx"
        
        if data:
            new_rows = update_stock_csv(stock_id, data)
            if new_rows > 0:
                print(f"✅ +{new_rows} 筆 ({source})")
                updated_count += 1
                if source == "TWSE":
                    twse_count += 1
                else:
                    tpex_count += 1
            else:
                print("⏭️ 已是最新")
        else:
            print("❌ 無資料")
        
        # 限速
        if i < len(stocks) - 1:
            time.sleep(REQUEST_DELAY)
    
    # 總結
    total_time = time.time() - start_time
    print("\n" + "=" * 60)
    print("📊 補齊完成！")
    print(f"   ⏱️ 耗時: {total_time/60:.1f} 分鐘")
    print(f"   ✅ 更新: {updated_count} 檔")
    print(f"   📈 TWSE: {twse_count} 檔, TPEx: {tpex_count} 檔")
    print("=" * 60)

if __name__ == "__main__":
    main()
