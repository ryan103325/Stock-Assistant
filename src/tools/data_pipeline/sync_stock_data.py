# === 股票資料同步腳本：清理下市 + 新股建檔 ===
# 用途：
# 1. 刪除已下市股票的 CSV 檔案
# 2. 為新上市股票建立 CSV 並抓取近五年歷史資料

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

# 動態載入 Pipeline_data 的函數
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

FINMIND_TOKEN = os.getenv("FINMIND_TOKEN", "")
FINMIND_API = "https://api.finmindtrade.com/api/v4/data"
HISTORY_YEARS = 5  # 新股抓取近幾年資料

# ================= 核心函數 =================

def get_valid_stocks():
    """取得目前有效的股票清單"""
    from Pipeline_data import get_stock_list_universal
    return set(get_stock_list_universal())


def get_existing_csvs():
    """取得 history 資料夾中現有的 CSV 股票代碼"""
    csv_files = [f for f in os.listdir(DATA_FOLDER) if f.endswith('.csv')]
    return set(f.replace('.csv', '') for f in csv_files)


def delete_delisted_stocks(valid_stocks, existing_csvs):
    """刪除已下市股票的 CSV"""
    to_delete = existing_csvs - valid_stocks
    deleted_count = 0
    
    if to_delete:
        print(f"\n🗑️ 發現 {len(to_delete)} 檔下市股票，正在刪除...")
        for code in sorted(to_delete):
            file_path = os.path.join(DATA_FOLDER, f"{code}.csv")
            if os.path.exists(file_path):
                os.remove(file_path)
                deleted_count += 1
                print(f"   🗑️ 刪除 {code}.csv")
        print(f"   ✅ 已刪除 {deleted_count} 檔")
    
    return deleted_count


def fetch_finmind_history(stock_id, years=HISTORY_YEARS):
    """用 FinMind 抓取指定年數的歷史資料"""
    if not FINMIND_TOKEN:
        return pd.DataFrame()
    
    start_date = (datetime.now() - timedelta(days=years*365)).strftime('%Y-%m-%d')
    
    params = {
        "dataset": "TaiwanStockPrice",
        "data_id": stock_id,
        "start_date": start_date,
        "token": FINMIND_TOKEN
    }
    
    try:
        resp = requests.get(FINMIND_API, params=params, timeout=20)
        
        if resp.status_code == 200:
            data = resp.json().get('data', [])
            if data:
                df = pd.DataFrame(data)
                result = pd.DataFrame({
                    'Date': df['date'],
                    'Open': df['open'].astype(float),
                    'High': df['max'].astype(float),
                    'Low': df['min'].astype(float),
                    'Close': df['close'].astype(float),
                    'Volume': df['Trading_Volume'].astype(float),
                })
                result['Amount'] = result['Close'] * result['Volume']
                return result
        return pd.DataFrame()
    except:
        return pd.DataFrame()


def create_new_stocks(valid_stocks, existing_csvs):
    """為新上市股票建立 CSV 並抓取歷史資料"""
    new_stocks = valid_stocks - existing_csvs
    created_count = 0
    
    if new_stocks:
        print(f"\n🆕 發現 {len(new_stocks)} 檔新股票，正在建立...")
        
        for i, code in enumerate(sorted(new_stocks)):
            print(f"   [{i+1}/{len(new_stocks)}] {code}...", end=" ")
            
            df = fetch_finmind_history(code)
            
            if not df.empty:
                file_path = os.path.join(DATA_FOLDER, f"{code}.csv")
                df.to_csv(file_path, index=False, float_format='%.2f')
                print(f"✅ {len(df)} 筆資料")
                created_count += 1
            else:
                print("❌ 無資料")
            
            time.sleep(1)  # 限速
        
        print(f"   ✅ 已建立 {created_count} 檔")
    
    return created_count


def main():
    """主程式：同步股票資料"""
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8')
    
    print("=" * 60)
    print("🔄 股票資料同步腳本")
    print(f"📁 資料目錄: {DATA_FOLDER}")
    print("=" * 60)
    
    # 1. 取得有效股票清單
    print("\n📡 取得目前有效股票清單...")
    valid_stocks = get_valid_stocks()
    
    if len(valid_stocks) == 0:
        print("❌ 無法取得有效清單")
        return
    
    # 2. 取得現有 CSV
    existing_csvs = get_existing_csvs()
    print(f"📂 現有 CSV: {len(existing_csvs)} 檔")
    
    # 3. 刪除下市股票
    deleted = delete_delisted_stocks(valid_stocks, existing_csvs)
    
    # 4. 建立新股票
    created = create_new_stocks(valid_stocks, existing_csvs)
    
    # 5. 總結
    print("\n" + "=" * 60)
    print("🔄 同步完成！")
    print(f"   🗑️ 刪除下市: {deleted} 檔")
    print(f"   🆕 新增建檔: {created} 檔")
    print(f"   📊 目前有效: {len(valid_stocks)} 檔")
    print("=" * 60)


if __name__ == "__main__":
    main()
