import os
import glob
import pandas as pd
import numpy as np
import pickle
import time
import sys

# 強制將輸出編碼設為 utf-8 以支援 emoji
sys.stdout.reconfigure(encoding='utf-8')

# 設定路徑
SRC_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASE_DIR = SRC_ROOT # Keep alias if used elsewhere, but ideally use SRC_ROOT
PROJECT_ROOT = os.path.dirname(SRC_ROOT)

DATA_FOLDER = os.path.join(SRC_ROOT, "data_core", "history")
META_FOLDER = os.path.join(SRC_ROOT, "data_core", "market_meta")
CACHE_FILE = os.path.join(SRC_ROOT, "cache", "market_matrix.pkl")

def generate_cache():
    print("🚀 開始製作加速快取檔 (完整指標版)...")
    
    if not os.path.exists(DATA_FOLDER):
        print("❌ 錯誤：找不到 stock_db 資料夾！")
        return

    csv_files_all = glob.glob(os.path.join(DATA_FOLDER, "*.csv"))
    if not csv_files_all:
        print("⚠️ 無 CSV 檔案")
        return

    # 1. 讀取 MoneyDJ 清單 (User Requirement: Strict Filter)
    valid_codes = set()
    dj_file = os.path.join(META_FOLDER, "moneydj_industries.csv")
    
    if os.path.exists(dj_file):
        try:
            print(f"📋 載入 MoneyDJ 清單 (過濾器): {dj_file}")
            # Robust Reading (Manual Parse)
            with open(dj_file, 'r', encoding='utf-8-sig') as f:
                lines = f.readlines()
                # Skip Header if detected
                start_idx = 0
                if lines and "Code" in lines[0] and "Name" in lines[0]:
                    start_idx = 1
                
                for line in lines[start_idx:]:
                    parts = line.strip().split(',')
                    if len(parts) >= 1:
                        code = parts[0].strip()
                        if code: valid_codes.add(code)
                        
            print(f"✅ 有效代碼清單: {len(valid_codes)} 筆")
        except Exception as e:
            print(f"⚠️ 讀取 MoneyDJ 清單失敗: {e}")
    else:
        print("⚠️ 警告：找不到 MoneyDJ 清單，無法執行過濾！(將讀取所有檔案)")

    # 2. 執行過濾
    csv_files = []
    for f in csv_files_all:
        sid = os.path.basename(f).replace('.csv', '')
        # 如果有清單，就只收清單內的；否則全收
        if valid_codes:
            if sid in valid_codes:
                csv_files.append(f)
        else:
            csv_files.append(f)

    print(f"📖 正在讀取 {len(csv_files)} 檔股票資料 (已過濾)...")
    
    close_dict = {}
    high_dict = {}
    low_dict = {}
    vol_dict = {}
    
    for i, file in enumerate(csv_files):
        try:
            stock_id = os.path.basename(file).replace('.csv', '')
            # 讀取 Close, High, Low, Volume
            df = pd.read_csv(file, usecols=['Date', 'Close', 'High', 'Low', 'Volume'])
            df['Date'] = pd.to_datetime(df['Date'])
            df.set_index('Date', inplace=True)
            # 去重並保留最後一筆
            df = df[~df.index.duplicated(keep='last')]
            
            close_dict[stock_id] = df['Close']
            high_dict[stock_id] = df['High']
            low_dict[stock_id]  = df['Low']
            vol_dict[stock_id]  = df['Volume']
            
            if i % 100 == 0:
                print(f"   已讀取 {i}/{len(csv_files)}...", end='\r')
        except: continue
    print(f"✅ 讀取完成！共 {len(close_dict)} 檔")

    print("⚡ 建立全市場矩陣與轉換 Float32...")
    # 建立全市場股價矩陣 (轉 float32 節省空間)
    df_matrix = pd.DataFrame(close_dict).sort_index().astype('float32')
    df_high_matrix = pd.DataFrame(high_dict).sort_index().astype('float32')
    df_low_matrix = pd.DataFrame(low_dict).sort_index().astype('float32')
    df_vol_matrix = pd.DataFrame(vol_dict).sort_index().astype('float32')

    # Debug: Check Matrix Quality
    print(f"📊 矩陣時間範圍: {df_matrix.index[0]} ~ {df_matrix.index[-1]}")
    print(f"📉 最後一日有效股數: {df_matrix.iloc[-1].count()} / {len(df_matrix.columns)}")
    print(f"📉 倒數第二日有效股數: {df_matrix.iloc[-2].count()} / {len(df_matrix.columns)}")
    
    # ----------------------------------------------------
    # 1. 計算 Mansfield (需要大盤)
    # ----------------------------------------------------
    # ----------------------------------------------------
    taiex_path = os.path.join(SRC_ROOT, "data_core", "TAIEX.csv")
    df_mansfield_pr = None
    
    if os.path.exists(taiex_path):
        try:
            print("⚡ 計算 Mansfield Strength...")
            df_taiex = pd.read_csv(taiex_path)
            df_taiex['Date'] = pd.to_datetime(df_taiex['Date'])
            df_taiex.set_index('Date', inplace=True)
            s_taiex = df_taiex['Close'].reindex(df_matrix.index, method='ffill').astype('float32')
            
            df_rel = df_matrix.div(s_taiex, axis=0)
            df_ma = df_rel.rolling(window=252, min_periods=200).mean()
            df_mansfield_raw = ((df_rel / df_ma) - 1) * 10
            df_mansfield_pr = df_mansfield_raw.rank(axis=1, pct=True) * 100
            df_mansfield_pr = df_mansfield_pr.astype('float32')
        except Exception as e:
            print(f"❌ Mansfield 計算失敗: {e}")
    else:
        print("⚠️ 缺少 TAIEX.csv，跳過 Mansfield")

    # ----------------------------------------------------
    # 2. 計算 IBD Rating (RS Score)
    # ----------------------------------------------------
    print("⚡ 計算 IBD RS Rating...")
    # Future Warning Fix: pct_change now defaults to no fill, older pandas used pad.
    # We use ffill() explicitly before pct_change if needed, or rely on built-in behavior with fill_method=None (for newer pandas)
    roc1 = df_matrix.pct_change(63, fill_method=None)
    roc2 = df_matrix.pct_change(126, fill_method=None)
    roc3 = df_matrix.pct_change(189, fill_method=None)
    roc4 = df_matrix.pct_change(252, fill_method=None)
    df_ibd_raw = (roc1 * 0.4) + (roc2 * 0.2) + (roc3 * 0.2) + (roc4 * 0.2)
    df_ibd_pr = df_ibd_raw.rank(axis=1, pct=True) * 100
    df_ibd_pr = df_ibd_pr.astype('float32')
    
    # ----------------------------------------------------
    # New: 計算 PR 值的 50日均線 (For Momentum Trend)
    # ----------------------------------------------------
    print("⚡ 計算 PR 值均線 (MA50)...")
    df_mansfield_pr_ma50 = None
    if df_mansfield_pr is not None:
        df_mansfield_pr_ma50 = df_mansfield_pr.rolling(50, min_periods=25).mean().astype('float32')
        
    df_ibd_pr_ma50 = df_ibd_pr.rolling(50, min_periods=25).mean().astype('float32')

    # ----------------------------------------------------
    # 3. 計算 均線 (MA)
    # ----------------------------------------------------
    print("⚡ 計算各期均線 (MA)...")
    df_ma5 = df_matrix.rolling(5, min_periods=3).mean().astype('float32')
    df_ma10 = df_matrix.rolling(10, min_periods=5).mean().astype('float32')
    df_ma20 = df_matrix.rolling(20, min_periods=10).mean().astype('float32')
    df_ma50 = df_matrix.rolling(50, min_periods=25).mean().astype('float32')
    df_ma150 = df_matrix.rolling(150, min_periods=75).mean().astype('float32')
    df_ma200 = df_matrix.rolling(200, min_periods=100).mean().astype('float32')

    # Volume MA
    print("⚡ 計算成交量均線...")
    df_vol_ma5 = df_vol_matrix.rolling(5, min_periods=3).mean().astype('float32')
    df_vol_ma20 = df_vol_matrix.rolling(20, min_periods=10).mean().astype('float32') # Added as per VCP requirement
    df_vol_ma50 = df_vol_matrix.rolling(50, min_periods=25).mean().astype('float32')

    # ----------------------------------------------------
    # 4. 計算 RSI (14)
    # ----------------------------------------------------
    # ----------------------------------------------------
    # 4. 計算 RSI (14) & ATR (14)
    # ----------------------------------------------------
    print("⚡ 計算 RSI (14) & ATR (14)...")
    delta = df_matrix.diff()
    
    # Use Wilder's Smoothing (EWM with com=13 for N=14)
    # Standard Simple Rolling Mean (SMA) gives different results than TradingView
    gain = (delta.where(delta > 0, 0)).ewm(com=13, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(com=13, adjust=False).mean()
    
    rs = gain / loss
    df_rsi = 100 - (100 / (1 + rs))
    df_rsi = df_rsi.astype('float32')
    
    # ATR Calculation
    # TR = max(High-Low, abs(High-PrevClose), abs(Low-PrevClose))
    prev_close = df_matrix.shift(1)
    
    # Correct Vectorized TR:
    tr = np.maximum(
        (df_high_matrix - df_low_matrix),
        np.maximum(
            (df_high_matrix - prev_close).abs(),
            (df_low_matrix - prev_close).abs()
        )
    )
    df_atr = tr.rolling(14, min_periods=5).mean().astype('float32') # Relaxed
    df_atr5 = tr.rolling(5, min_periods=3).mean().astype('float32') # NEW for V3 (Relaxed)
    df_atr20 = tr.rolling(20, min_periods=10).mean().astype('float32') # NEW for V3 (Relaxed)

    # 4.2 Volume MAs (Fibonacci)
    df_vol_ma8 = df_vol_matrix.rolling(8, min_periods=3).mean().astype('float32')
    df_vol_ma34 = df_vol_matrix.rolling(34, min_periods=15).mean().astype('float32')

    # Removed Linear Regression Slope calculation (too slow and unused) 


    # ----------------------------------------------------
    # 5. 計算 52週高低價
    # ----------------------------------------------------
    print("⚡ 計算 52週高低價...")
    df_high_52w = df_high_matrix.rolling(252, min_periods=120).max().astype('float32')
    df_low_52w = df_low_matrix.rolling(252, min_periods=120).min().astype('float32')

    # ----------------------------------------------------
    # 6. 計算 波動率 (Amplitude)
    # ----------------------------------------------------
    print("⚡ 計算波動率 (Amp)...")
    # (High - Low) / Close
    df_amplitude = (df_high_matrix - df_low_matrix) / df_matrix
    df_amp_ma10 = df_amplitude.rolling(10).mean().astype('float32')
    df_amp_ma20 = df_amplitude.rolling(20).mean().astype('float32')

    # ----------------------------------------------------
    # 7. 計算 1日漲跌幅 (Use ffill to calculate change vs Last Valid Close)
    # ----------------------------------------------------
    df_change_1 = df_matrix.ffill().pct_change() * 100
    df_change_1 = df_change_1.astype('float32')

    # 儲存
    print("💾 正在寫入擴充快取檔...")
    cache_data = {
        'timestamp': time.time(),
        
        # 原始資料
        'close': df_matrix,
        'high': df_high_matrix,
        'low': df_low_matrix,
        'volume': df_vol_matrix,
        
        # 強度指標
        'mansfield_raw': df_mansfield_raw, # NEW: Added per user request
        'mansfield_pr': df_mansfield_pr,
        'mansfield_pr_ma50': df_mansfield_pr_ma50,
        'ibd_pr': df_ibd_pr,
        'ibd_pr_ma50': df_ibd_pr_ma50,
        
        # 均線
        'ma5': df_ma5, 'ma10': df_ma10, 'ma20': df_ma20,
        'ma50': df_ma50, 'ma150': df_ma150, 'ma200': df_ma200,
        
        # 量能
        'vol_ma5': df_vol_ma5, 'vol_ma20': df_vol_ma20, 'vol_ma50': df_vol_ma50,
        'vol_ma8': df_vol_ma8, 'vol_ma34': df_vol_ma34, # NEW for V3
        
        # 其他技術指標
        'rsi': df_rsi,
        'atr': df_atr, 'atr5': df_atr5, 'atr20': df_atr20, # NEW for V3
        # Removed Slope keys
        'high_52w': df_high_52w, 'low_52w': df_low_52w,
        'amp_ma10': df_amp_ma10, 'amp_ma20': df_amp_ma20,
        'change_1': df_change_1
    }
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    
    with open(CACHE_FILE, 'wb') as f:
        pickle.dump(cache_data, f)
        
    size_mb = os.path.getsize(CACHE_FILE) / 1024 / 1024
    print(f"🎉 快取製作完成！(已包含所有篩選指標)")
    print(f"📁 檔案位置: {CACHE_FILE}")
    print(f"📦 檔案大小: {size_mb:.2f} MB")

if __name__ == "__main__":
    
    # Optimization: Check if already run today
    if os.path.exists(CACHE_FILE):
        mtime = datetime.fromtimestamp(os.path.getmtime(CACHE_FILE))
        if mtime.date() == datetime.now().date():
            print(f"✅ [optimize_matrix] 今日 ({mtime.date()}) 已產生矩陣，跳過執行。")
            sys.exit(0)

    generate_cache()
