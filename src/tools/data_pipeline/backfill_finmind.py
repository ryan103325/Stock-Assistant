# === 使用 FinMind 補齊剩餘個股資料 ===
# 用途：補齊 TWSE/TPEx 無法抓到的個股資料

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

# FinMind 設定
FINMIND_TOKEN = os.getenv("FINMIND_TOKEN", "")
FINMIND_API = "https://api.finmindtrade.com/api/v4/data"

# 目標日期 (補齊到這天為止)
TARGET_DATE = "2026-01-30"

# 限速設定 (低於 600 檔不需顧慮 rate limit)
REQUEST_DELAY = 0.5

# ================= 核心函數 =================

def get_stocks_needing_update(target_date: str = TARGET_DATE) -> list:
    """
    掃描所有 CSV，找出需要更新的股票 (最後日期 < target_date)
    """
    need_update = []
    csv_files = [f for f in os.listdir(DATA_FOLDER) if f.endswith('.csv')]
    
    for f in csv_files:
        try:
            df = pd.read_csv(os.path.join(DATA_FOLDER, f))
            if len(df) > 0:
                last_date = str(df['Date'].iloc[-1])
                if last_date < target_date:
                    need_update.append(f.replace('.csv', ''))
        except:
            pass
    
    return need_update


def fetch_finmind_stock(stock_id: str, start_date: str = "2026-01-01") -> pd.DataFrame:
    """
    使用 FinMind API 抓取單一股票資料
    """
    if not FINMIND_TOKEN:
        return pd.DataFrame()
    
    params = {
        "dataset": "TaiwanStockPrice",
        "data_id": stock_id,
        "start_date": start_date,
        "token": FINMIND_TOKEN
    }
    
    try:
        resp = requests.get(FINMIND_API, params=params, timeout=20)
        
        if resp.status_code == 402 or resp.status_code == 429:
            # Rate limit - 等待後重試
            print("⚠️ Rate limit, 等待 60 秒...", end=" ")
            time.sleep(60)
            resp = requests.get(FINMIND_API, params=params, timeout=20)
        
        if resp.status_code != 200:
            return pd.DataFrame()
        
        data = resp.json().get('data', [])
        if not data:
            return pd.DataFrame()
        
        df = pd.DataFrame(data)
        
        # 標準化欄位
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
        
    except Exception as e:
        return pd.DataFrame()


def update_stock_csv(stock_id: str, new_data: pd.DataFrame) -> int:
    """
    將新資料合併到現有 CSV，返回新增的行數
    """
    file_path = os.path.join(DATA_FOLDER, f"{stock_id}.csv")
    
    if not os.path.exists(file_path):
        new_data.to_csv(file_path, index=False, float_format='%.2f')
        return len(new_data)
    
    try:
        df_old = pd.read_csv(file_path)
        existing_dates = set(df_old['Date'].astype(str).tolist())
        
        new_rows = new_data[~new_data['Date'].isin(existing_dates)]
        
        if len(new_rows) == 0:
            return 0
        
        df_merged = pd.concat([df_old, new_rows], ignore_index=True)
        df_merged = df_merged.drop_duplicates(subset=['Date'], keep='last')
        df_merged = df_merged.sort_values('Date')
        
        df_merged.to_csv(file_path, index=False, float_format='%.2f')
        return len(new_rows)
        
    except Exception as e:
        print(f"❌ 合併錯誤: {e}")
        return 0


def main():
    """
    主程式：使用 FinMind 補齊剩餘個股
    """
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8')
    
    print("=" * 60)
    print("📅 FinMind 補齊腳本")
    print(f"📁 資料目錄: {DATA_FOLDER}")
    print(f"📆 目標日期: {TARGET_DATE}")
    print(f"🔑 FinMind Token: {'已設定' if FINMIND_TOKEN else '❌ 未設定'}")
    print("=" * 60)
    
    if not FINMIND_TOKEN:
        print("\n❌ 錯誤: 請先設定 FINMIND_TOKEN 環境變數")
        return
    
    # 1. 找出需要更新的股票
    print("\n🔍 掃描需要更新的股票...")
    stocks = get_stocks_needing_update()
    print(f"📋 發現 {len(stocks)} 檔需要補齊")
    
    if len(stocks) == 0:
        print("✅ 所有資料已是最新！")
        return
    
    # 預估時間
    est_hours = len(stocks) * REQUEST_DELAY / 3600
    print(f"⏱️ 預估時間: {est_hours:.1f} 小時 (每 {REQUEST_DELAY} 秒處理 1 檔)")
    print("\n" + "-" * 60)
    
    # 2. 逐一更新
    updated_count = 0
    failed_stocks = []
    deleted_count = 0
    start_time = time.time()
    
    for i, stock_id in enumerate(stocks):
        elapsed = time.time() - start_time
        remaining = (len(stocks) - i) * REQUEST_DELAY
        
        print(f"[{i+1}/{len(stocks)}] {stock_id}...", end=" ")
        
        df = fetch_finmind_stock(stock_id)
        
        if df.empty:
            # 無資料 = 下市股票，刪除 CSV
            csv_path = os.path.join(DATA_FOLDER, f"{stock_id}.csv")
            if os.path.exists(csv_path):
                os.remove(csv_path)
                print("🗑️ 已刪除 (下市)")
                deleted_count += 1
            else:
                print("❌ 無資料")
            failed_stocks.append(stock_id)
        else:
            new_rows = update_stock_csv(stock_id, df)
            if new_rows > 0:
                print(f"✅ +{new_rows} 筆")
                updated_count += 1
            else:
                print("⏭️ 已是最新")
        
        # 限速
        if i < len(stocks) - 1:
            time.sleep(REQUEST_DELAY)
    
    # 3. 總結
    total_time = time.time() - start_time
    print("\n" + "=" * 60)
    print("📊 FinMind 補齊完成！")
    print(f"   ⏱️ 耗時: {total_time/60:.1f} 分鐘")
    print(f"   ✅ 更新: {updated_count} 檔")
    print(f"   🗑️ 刪除: {deleted_count} 檔 (下市)")
    print(f"   ❌ 無資料: {len(failed_stocks) - deleted_count} 檔")
    print("=" * 60)


if __name__ == "__main__":
    main()
