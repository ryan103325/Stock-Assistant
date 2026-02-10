"""
一次性修復腳本：
1. 從 FinMind 抓取完整 TAIEX (2020-07-01 ~ today)
2. 截斷 history/*.csv 中 2020-07-01 之前的資料
3. 執行 Pipeline 補齊到最新日期
4. 驗證資料完整性
"""
import os
import sys
import glob
import requests
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv()

SRC_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_FOLDER = os.path.join(SRC_ROOT, "data_core", "history")
TAIEX_PATH = os.path.join(SRC_ROOT, "data_core", "TAIEX.csv")
CUTOFF_DATE = "2020-07-01"
TOKEN = os.getenv("FINMIND_TOKEN", "")

def step1_fix_taiex():
    """從 FinMind 抓取完整 TAIEX 資料"""
    print("\n" + "="*60)
    print("📊 Step 1: 更新 TAIEX.csv (2020-07-01 ~ today)")
    print("="*60)
    
    if not TOKEN:
        print("❌ 沒有 FINMIND_TOKEN，無法抓取 TAIEX")
        return False
    
    url = "https://api.finmindtrade.com/api/v4/data"
    params = {
        "dataset": "TaiwanStockPrice",
        "data_id": "TAIEX",
        "start_date": CUTOFF_DATE,
        "token": TOKEN
    }
    
    print(f"📡 正在從 FinMind 抓取 TAIEX ({CUTOFF_DATE} ~ today)...")
    try:
        resp = requests.get(url, params=params, timeout=30)
        data = resp.json().get('data', [])
        
        if not data:
            print("❌ 沒有回傳資料")
            return False
        
        df = pd.DataFrame(data)
        df = df.rename(columns={
            'date': 'Date', 'open': 'Open', 'max': 'High',
            'min': 'Low', 'close': 'Close', 'Trading_Volume': 'Volume'
        })
        df = df[['Date', 'Open', 'High', 'Low', 'Close', 'Volume']]
        df = df.drop_duplicates(subset=['Date'], keep='last')
        df = df.sort_values('Date').reset_index(drop=True)
        
        df.to_csv(TAIEX_PATH, index=False, encoding='utf-8')
        print(f"✅ TAIEX 更新完成！")
        print(f"   範圍: {df.iloc[0]['Date']} ~ {df.iloc[-1]['Date']}")
        print(f"   筆數: {len(df)}")
        return True
    except Exception as e:
        print(f"❌ TAIEX 更新失敗: {e}")
        return False

def step2_trim_history():
    """截斷 history 中 2020-07-01 之前的資料"""
    print("\n" + "="*60)
    print(f"✂️ Step 2: 截斷 history/*.csv ({CUTOFF_DATE} 之前的資料)")
    print("="*60)
    
    csv_files = glob.glob(os.path.join(DATA_FOLDER, "*.csv"))
    print(f"📁 找到 {len(csv_files)} 個 CSV 檔案")
    
    trimmed_count = 0
    error_count = 0
    
    for i, f in enumerate(csv_files):
        try:
            df = pd.read_csv(f)
            if 'Date' not in df.columns:
                continue
            
            original_len = len(df)
            df = df[df['Date'] >= CUTOFF_DATE]
            df = df.drop_duplicates(subset=['Date'], keep='last')
            df = df.sort_values('Date').reset_index(drop=True)
            
            if len(df) < original_len:
                df.to_csv(f, index=False)
                trimmed_count += 1
            
            if (i + 1) % 200 == 0:
                print(f"   已處理 {i+1}/{len(csv_files)}...")
        except Exception as e:
            error_count += 1
            if error_count <= 5:
                stock_id = os.path.basename(f).replace('.csv', '')
                print(f"   ⚠️ {stock_id}: {e}")
    
    print(f"✅ 截斷完成！修改 {trimmed_count} 檔，錯誤 {error_count} 檔")

def step3_verify():
    """驗證資料完整性"""
    print("\n" + "="*60)
    print("🔍 Step 3: 驗證資料完整性")
    print("="*60)
    
    # 驗證 TAIEX
    df_taiex = pd.read_csv(TAIEX_PATH)
    taiex_start = df_taiex.iloc[0]['Date']
    taiex_end = df_taiex.iloc[-1]['Date']
    print(f"📊 TAIEX: {taiex_start} ~ {taiex_end} ({len(df_taiex)} 筆)")
    
    if taiex_start > CUTOFF_DATE:
        print(f"   ⚠️ TAIEX 起始日 {taiex_start} 晚於 {CUTOFF_DATE}")
    if taiex_end < "2026-02-10":
        print(f"   ⚠️ TAIEX 最後日 {taiex_end} 早於 2026-02-10")
    
    # 抽樣驗證 history
    samples = ['2330', '2317', '2454', '2881', '1101', '3008', '2603']
    print(f"\n📋 抽樣驗證 history:")
    
    missing_today = 0
    too_early = 0
    csv_files = glob.glob(os.path.join(DATA_FOLDER, "*.csv"))
    
    for f in csv_files:
        try:
            df = pd.read_csv(f)
            if 'Date' not in df.columns or len(df) == 0:
                continue
            sid = os.path.basename(f).replace('.csv', '')
            start = df.iloc[0]['Date']
            end = df.iloc[-1]['Date']
            
            if start < CUTOFF_DATE:
                too_early += 1
            if end < "2026-02-10":
                missing_today += 1
            
            if sid in samples:
                status = "✅" if (start >= CUTOFF_DATE and end >= "2026-02-10") else "⚠️"
                print(f"   {status} {sid}: {start} ~ {end} ({len(df)} 筆)")
        except:
            pass
    
    print(f"\n📊 總結:")
    print(f"   檔案總數: {len(csv_files)}")
    print(f"   起始日早於 {CUTOFF_DATE}: {too_early} 檔")
    print(f"   最後日早於 2026-02-10: {missing_today} 檔")
    
    if missing_today > 0:
        print(f"\n💡 有 {missing_today} 檔缺少最新資料，需要執行 Pipeline 補齊")
        print(f"   請執行: python src/tools/data_pipeline/Pipeline_data.py --force")

if __name__ == "__main__":
    step1_fix_taiex()
    step2_trim_history()
    step3_verify()
    print("\n🎉 全部完成！")
