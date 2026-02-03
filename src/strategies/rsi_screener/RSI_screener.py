import os
import sys
import pandas as pd
import numpy as np
import requests
from datetime import datetime
from dotenv import load_dotenv

# ============================================================
# RSI 底背離篩選系統 (Bullish RSI Divergence Screener)
# v2.0 - ATR 優化版
# ============================================================

# --- Load Environment Variables ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
env_path = os.path.join(project_root, ".env")
load_dotenv(env_path)

# --- Configuration ---
CACHE_FILE = os.path.join(project_root, "src", "cache", "market_matrix.pkl")
TAIEX_FILE = os.path.join(project_root, "src", "data_core", "TAIEX.csv")
NAME_MAP_FILE = os.path.join(project_root, "src", "data_core", "market_meta", "moneydj_industries.csv")

# --- Parameters ---
LIQUIDITY_THRESHOLD = 50_000_000  # 5000萬 (Filter 1)
MIN_DISTANCE = 5                   # Point A 至 Point B 最少 5 根 K 棒
LOOKBACK_DAYS = 60                 # 日線回朔期（找 Point A）
LOOKBACK_WEEKS = 20                # 周線回朔期（找 Point A）
ATR_MULTIPLIER = 1.5               # ATR 倍數門檻（可調整 1.0~2.0）
ENABLE_WEEKLY = True               # 是否啟用周線篩選
DEBUG_MODE = "--debug" in sys.argv # Debug 模式


def load_data():
    """載入市場矩陣快取"""
    if not os.path.exists(CACHE_FILE):
        print("❌ Cache not found! Please run 'optimize_matrix.py' first.")
        return None
    
    print("✅ 載入市場矩陣 (Market Matrix)...")
    try:
        import pickle
        with open(CACHE_FILE, 'rb') as f:
            data = pickle.load(f)
        return data
    except Exception as e:
        print(f"❌ 快取損壞: {e}")
        return None


def load_name_map():
    """載入股票名稱對照表"""
    name_map = {}
    try:
        if os.path.exists(NAME_MAP_FILE):
            with open(NAME_MAP_FILE, 'r', encoding='utf-8-sig', errors='ignore') as f:
                for line in f:
                    parts = line.strip().split(',')
                    if len(parts) >= 2:
                        name_map[parts[0].strip()] = parts[1].strip()
    except Exception:
        pass
    return name_map


def is_trading_day():
    """檢查今日是否為交易日"""
    today_str = datetime.now().strftime('%Y-%m-%d')
    force_mode = "--force" in sys.argv
    
    if os.path.exists(TAIEX_FILE):
        try:
            with open(TAIEX_FILE, "r") as f:
                last_line = f.readlines()[-1]
                last_date = last_line.split(",")[0].strip().replace("/", "-")
                if last_date == today_str:
                    return True
        except Exception:
            pass
    
    if force_mode:
        print(f"⚠️ [Force Mode] TAIEX 日期不符，但強制繼續執行。")
        return True
    
    print(f"😴 今日 ({today_str}) 非交易日或資料未更新，跳過執行。")
    return False


def calculate_rsi(price_series, period=8):
    """
    按 XQ 軟體公式計算 RSI
    
    邏輯：
    - 第一根 K 棒：用 SMA 初始化 sumUp/sumDown
    - 之後的 K 棒：Wilder 平滑 sumUp = sumUp[1] + (up - sumUp[1]) / length
    - RSI = 100 * sumUp / (sumUp + sumDown)
    - 分母為 0 時 RSI = 0
    """
    delta = price_series.diff()
    up = delta.clip(lower=0)      # max(price - price[1], 0)
    down = (-delta).clip(lower=0)  # max(price[1] - price, 0)
    
    # 初始化
    sum_up = np.zeros(len(price_series))
    sum_down = np.zeros(len(price_series))
    rsi = np.zeros(len(price_series))
    
    # 找到第一個有效位置（需要 period 個數據來計算 SMA）
    first_valid = period
    
    # 第一根有效 K 棒：用 SMA 初始化
    if first_valid < len(price_series):
        sum_up[first_valid] = up.iloc[1:first_valid+1].mean()
        sum_down[first_valid] = down.iloc[1:first_valid+1].mean()
    
    # 之後的 K 棒：Wilder 平滑
    alpha = 1.0 / period
    for i in range(first_valid + 1, len(price_series)):
        sum_up[i] = sum_up[i-1] + (up.iloc[i] - sum_up[i-1]) * alpha
        sum_down[i] = sum_down[i-1] + (down.iloc[i] - sum_down[i-1]) * alpha
    
    # 計算 RSI
    for i in range(first_valid, len(price_series)):
        denominator = sum_up[i] + sum_down[i]
        if denominator == 0:
            rsi[i] = 0  # XQ: 分母為 0 時 RSI = 0
        else:
            rsi[i] = 100 * sum_up[i] / denominator
    
    return pd.Series(rsi, index=price_series.index)


def calculate_atr(high, low, close, period=14):
    """
    計算 ATR (Average True Range)
    
    Args:
        high: 最高價 Series
        low: 最低價 Series
        close: 收盤價 Series
        period: ATR 週期（預設 14）
    
    Returns:
        ATR Series
    """
    # True Range = max(H-L, |H-C_prev|, |L-C_prev|)
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    
    return atr


def find_zigzag_lows_atr(price_series, high_series, low_series, atr_multiplier=1.5, min_distance=5):
    """
    使用 ATR 動態門檻找低點（ZigZag 演算法）
    
    邏輯：
    1. 找局部最低點
    2. 檢查反彈幅度是否 >= ATR × atr_multiplier
    3. 確保低點之間距離 >= min_distance
    
    Args:
        price_series: 收盤價 Series
        high_series: 最高價 Series
        low_series: 最低價 Series
        atr_multiplier: ATR 倍數門檻（預設 1.5）
        min_distance: 低點最小間距（預設 5）
    
    Returns:
        低點列表 [{'idx': 位置, 'date': 日期, 'value': 價格}, ...]
    """
    # 計算 ATR
    atr = calculate_atr(high_series, low_series, price_series, period=14)
    
    lows = []
    vals = price_series.values
    dates = price_series.index
    atr_vals = atr.values
    
    i = 14  # 跳過 ATR 計算不足的前 14 根
    while i < len(vals) - 1:
        # 找局部最低點（往前看 20 根 K 棒）
        local_low_idx = i
        local_low_val = vals[i]
        
        for j in range(i, min(i + 20, len(vals))):
            if vals[j] < local_low_val:
                local_low_val = vals[j]
                local_low_idx = j
        
        # 動態門檻：該點的 ATR × 倍數
        if local_low_idx < len(atr_vals) and not np.isnan(atr_vals[local_low_idx]):
            threshold = atr_vals[local_low_idx] * atr_multiplier
        else:
            # Fallback: 如果 ATR 無效，使用固定 2%
            threshold = local_low_val * 0.02
        
        # 檢查反彈幅度（往後看 15 根 K 棒）
        rebound = False
        for j in range(local_low_idx + 1, min(local_low_idx + 15, len(vals))):
            bounce_amount = vals[j] - local_low_val
            if bounce_amount >= threshold:
                rebound = True
                i = j  # 跳到反彈點繼續找
                break
        
        if rebound:
            lows.append({
                'idx': local_low_idx,
                'date': dates[local_low_idx],
                'value': local_low_val
            })
        else:
            i += 1
    
    # 過濾：確保低點之間距離 >= min_distance
    if not lows:
        return []
    
    filtered = [lows[0]]
    for low in lows[1:]:
        if (low['idx'] - filtered[-1]['idx']) >= min_distance:
            filtered.append(low)
    
    return filtered


def calc_ma_slope(ma_series, window=10):
    """
    計算移動平均線的斜率（線性回歸）
    
    Args:
        ma_series: MA Series
        window: 回歸窗口（預設 10）
    
    Returns:
        斜率 Series
    """
    def linear_slope(y):
        if len(y) < window or y.isna().any():
            return np.nan
        x = np.arange(len(y))
        slope = np.polyfit(x, y, 1)[0]
        return slope
    
    return ma_series.rolling(window).apply(linear_slope, raw=False)


def check_daily_divergence(price_series, rsi_series, high_series, low_series):
    """
    日線 RSI 底背離檢測（優化版）
    
    改進：
    1. 今天必須「剛突破」（昨天還沒突破）
    2. 低點 B 到今天不能超過 MAX_DAYS_FROM_LOW（預設 10 天）
    3. 使用 ATR 動態門檻找低點
    4. 加入背離強度篩選（價格跌幅、RSI 漲幅）
    
    Returns: (是否符合, metrics字典 or None)
    """
    MAX_DAYS_FROM_LOW = 10        # 從低點到突破最多 10 天
    MIN_PRICE_DROP_PCT = 1.5      # 價格至少跌 1.5%
    MIN_RSI_RISE_PCT = 5.0        # RSI 至少上升 5%
    
    if len(price_series) < LOOKBACK_DAYS:
        return False, None
    
    # 使用最近 LOOKBACK_DAYS 天的資料
    recent_price = price_series.iloc[-LOOKBACK_DAYS:]
    recent_rsi = rsi_series.iloc[-LOOKBACK_DAYS:]
    recent_high = high_series.iloc[-LOOKBACK_DAYS:]
    recent_low = low_series.iloc[-LOOKBACK_DAYS:]
    
    # --- Step 1: 今天是否「剛突破」？---
    today_close = recent_price.iloc[-1]
    yesterday_close = recent_price.iloc[-2]
    yesterday_high = recent_high.iloc[-2]
    day_before_high = recent_high.iloc[-3]
    breakout_level = max(yesterday_high, day_before_high)
    
    # 今天突破，但昨天還沒突破
    if not (today_close > breakout_level and yesterday_close <= breakout_level):
        return False, None  # 不是今天剛突破
    
    # --- Step 2: 使用 ATR 找低點 ---
    # 在「今天之前」的區間找低點（排除今天）
    search_price = recent_price.iloc[:-1]
    search_high = recent_high.iloc[:-1]
    search_low = recent_low.iloc[:-1]
    
    lows = find_zigzag_lows_atr(
        search_price, 
        search_high, 
        search_low, 
        atr_multiplier=ATR_MULTIPLIER,
        min_distance=MIN_DISTANCE
    )
    
    if len(lows) < 2:
        return False, None
    
    # Point B: 最近的低點
    point_b = lows[-1]
    
    # 檢查：低點距今天數不能超過 MAX_DAYS_FROM_LOW
    days_since_low = len(search_price) - point_b['idx']
    if days_since_low > MAX_DAYS_FROM_LOW:
        return False, None  # 盤整太久，動能減弱
    
    # Point A: 在 B 之前至少 MIN_DISTANCE 根 K 棒的另一個低點
    point_a = None
    for low in reversed(lows[:-1]):
        if (point_b['idx'] - low['idx']) >= MIN_DISTANCE:
            point_a = low
            break
    
    if point_a is None:
        return False, None
    
    # --- Step 3: 底背離檢測 + 強度篩選 ---
    p_a = point_a['value']
    p_b = point_b['value']
    r_a = recent_rsi.iloc[point_a['idx']]
    r_b = recent_rsi.iloc[point_b['idx']]
    
    # 底背離條件
    if not (p_b < p_a and r_b > r_a):
        return False, None
    
    # 背離強度篩選
    price_drop_pct = (p_a - p_b) / p_a * 100
    rsi_rise_pct = (r_b - r_a) / r_a * 100
    
    if price_drop_pct < MIN_PRICE_DROP_PCT:
        return False, None  # 價格跌幅不足
    
    if rsi_rise_pct < MIN_RSI_RISE_PCT:
        return False, None  # RSI 漲幅不足
    
    # 今天剛好發生底背離突破！
    return True, {
        "date_a": point_a['date'].strftime('%Y-%m-%d'),
        "date_b": point_b['date'].strftime('%Y-%m-%d'),
        "date_confirm": recent_price.index[-1].strftime('%Y-%m-%d'),
        "days_since_low": days_since_low,
        "p_a": p_a,
        "p_b": p_b,
        "r_a": r_a,
        "r_b": r_b,
        "price_drop_pct": price_drop_pct,
        "rsi_rise_pct": rsi_rise_pct,
        "breakout_level": breakout_level
    }


def check_weekly_divergence(df_close_stock, df_high_stock, df_low_stock):
    """
    周線 RSI 底背離檢測（優化版）
    
    改進：
    1. 本週必須「剛突破」（上週還沒突破）
    2. 低點 B 到本週不能超過 MAX_WEEKS_FROM_LOW（預設 8 週）
    3. 使用 ATR 動態門檻找低點
    4. 加入背離強度篩選
    
    Returns: (是否符合, metrics字典 or None)
    """
    MAX_WEEKS_FROM_LOW = 8        # 從低點到突破最多 8 週
    MIN_PRICE_DROP_PCT = 1.5
    MIN_RSI_RISE_PCT = 5.0
    
    if len(df_close_stock) < 100:
        return False, None
    
    # 日線轉周線（每週五收盤價 / 最高價 / 最低價）
    weekly_close = df_close_stock.resample('W-FRI').last().dropna()
    weekly_high = df_high_stock.resample('W-FRI').max().dropna()
    weekly_low = df_low_stock.resample('W-FRI').min().dropna()
    
    if len(weekly_close) < LOOKBACK_WEEKS:
        return False, None
    
    # 計算周線 RSI (週期=8)
    weekly_rsi = calculate_rsi(weekly_close, period=8)
    
    # 使用最近 LOOKBACK_WEEKS 週的資料
    recent_close = weekly_close.iloc[-LOOKBACK_WEEKS:]
    recent_high = weekly_high.iloc[-LOOKBACK_WEEKS:]
    recent_low = weekly_low.iloc[-LOOKBACK_WEEKS:]
    recent_rsi = weekly_rsi.iloc[-LOOKBACK_WEEKS:]
    
    # --- Step 1: 本週是否「剛突破」？---
    this_week_close = recent_close.iloc[-1]
    last_week_close = recent_close.iloc[-2]
    last_week_high = recent_high.iloc[-2]
    
    # 本週突破，但上週還沒突破
    if not (this_week_close > last_week_high and last_week_close <= last_week_high):
        return False, None
    
    # --- Step 2: 使用 ATR 找低點 ---
    search_close = recent_close.iloc[:-1]
    search_high = recent_high.iloc[:-1]
    search_low = recent_low.iloc[:-1]
    
    lows = find_zigzag_lows_atr(
        search_close,
        search_high,
        search_low,
        atr_multiplier=ATR_MULTIPLIER,
        min_distance=MIN_DISTANCE
    )
    
    if len(lows) < 2:
        return False, None
    
    # Point B: 最近的低點
    point_b = lows[-1]
    
    # 檢查：低點距本週不能超過 MAX_WEEKS_FROM_LOW
    weeks_since_low = len(search_close) - point_b['idx']
    if weeks_since_low > MAX_WEEKS_FROM_LOW:
        return False, None
    
    # Point A
    point_a = None
    for low in reversed(lows[:-1]):
        if (point_b['idx'] - low['idx']) >= MIN_DISTANCE:
            point_a = low
            break
    
    if point_a is None:
        return False, None
    
    # --- Step 3: 底背離檢測 + 強度篩選 ---
    p_a = point_a['value']
    p_b = point_b['value']
    r_a = recent_rsi.iloc[point_a['idx']]
    r_b = recent_rsi.iloc[point_b['idx']]
    
    if not (p_b < p_a and r_b > r_a):
        return False, None
    
    price_drop_pct = (p_a - p_b) / p_a * 100
    rsi_rise_pct = (r_b - r_a) / r_a * 100
    
    if price_drop_pct < MIN_PRICE_DROP_PCT or rsi_rise_pct < MIN_RSI_RISE_PCT:
        return False, None
    
    return True, {
        "date_a": point_a['date'].strftime('%Y-%m-%d'),
        "date_b": point_b['date'].strftime('%Y-%m-%d'),
        "date_confirm": recent_close.index[-1].strftime('%Y-%m-%d'),
        "weeks_since_low": weeks_since_low,
        "p_a": p_a,
        "p_b": p_b,
        "r_a": r_a,
        "r_b": r_b,
        "price_drop_pct": price_drop_pct,
        "rsi_rise_pct": rsi_rise_pct,
        "breakout_level": last_week_high
    }


def run_screener():
    """主篩選流程"""
    print("🚀 啟動 RSI 底背離篩選系統 v2.0 (ATR 優化版)...")
    print("   📋 優化內容：ATR 動態低點 + 背離強度篩選 + 剛突破限制")
    
    # 檢查交易日
    if not is_trading_day():
        return
    
    # 載入資料
    data = load_data()
    if data is None:
        return
    
    df_close = data.get('close')
    df_high = data.get('high')
    df_low = data.get('low')
    df_rsi = data.get('rsi')
    df_volume = data.get('volume')
    
    if df_close is None or df_high is None:
        print("❌ 缺少必要資料 (close/high).")
        return
    
    if df_low is None:
        print("❌ 缺少必要資料 (low).")
        return
    
    # 前向填充缺失值
    df_close = df_close.ffill()
    df_high = df_high.ffill()
    df_low = df_low.ffill()
    
    # 強制使用 XQ 公式重新計算 RSI (週期=8)，不使用快取
    print("📊 使用 XQ 公式計算 RSI (週期=8)...")
    df_rsi = df_close.apply(lambda col: calculate_rsi(col, period=8))
    
    idx = -1
    date_str = df_close.index[idx].strftime('%Y-%m-%d')
    print(f"📅 分析日期: {date_str}")
    
    s_close = df_close.iloc[idx]
    
    # ========================================
    # 第一階段：基礎過濾 (Filter 1, 2, 3)
    # ========================================
    print("\n🌊 第一階段：基礎過濾 (Filters 1,2,3)...")
    
    # Filter 1: 流動性 (20日均量成交額 > 5000萬)
    if 'vol_ma20' in data:
        s_vol_ma20 = data['vol_ma20'].iloc[idx]
    else:
        s_vol_ma20 = df_volume.rolling(20).mean().iloc[idx]
    s_turnover = s_close * s_vol_ma20
    mask_liquid = (s_turnover > LIQUIDITY_THRESHOLD)
    
    # Filter 2: 趨勢排列 (Close > MA50 > MA150 > MA200)
    ma50 = df_close.rolling(50).mean()
    ma150 = df_close.rolling(150).mean()
    ma200 = df_close.rolling(200).mean()
    
    s_ma50 = ma50.iloc[idx]
    s_ma150 = ma150.iloc[idx]
    s_ma200 = ma200.iloc[idx]
    
    mask_trend_order = (s_close > s_ma50) & (s_ma50 > s_ma150) & (s_ma150 > s_ma200)
    
    # Filter 3: 趨勢向上 (MA200 斜率 > 0)
    ma200_slope = calc_ma_slope(ma200, window=10)
    s_ma200_slope = ma200_slope.iloc[idx]
    mask_trend_up = s_ma200_slope > 0
    
    # 合併過濾條件
    mask_final = mask_liquid & mask_trend_order & mask_trend_up
    candidates = s_close[mask_final].index.tolist()
    
    print(f"   🔍 初選合格: {len(candidates)} 檔")
    
    # 載入名稱對照
    name_map = load_name_map()
    
    # 計算漲跌幅
    s_prev = df_close.iloc[idx - 1]
    s_pchg = (s_close - s_prev) / s_prev * 100
    
    # ========================================
    # 第二階段：日線 RSI 底背離 + 突破確認
    # ========================================
    print("\n📈 第二階段：日線 RSI 底背離掃描 (含突破確認)...")
    
    daily_candidates = []
    total = len(candidates)
    
    for i, code in enumerate(candidates):
        if (i + 1) % 50 == 0:
            print(f"   Progress: {i + 1}/{total}...", end="\r")
        
        try:
            price_series = df_close[code].dropna()
            rsi_series = df_rsi[code].dropna()
            high_series = df_high[code].dropna()
            low_series = df_low[code].dropna()
            
            # 對齊索引
            common_idx = price_series.index.intersection(rsi_series.index).intersection(high_series.index).intersection(low_series.index)
            if len(common_idx) < LOOKBACK_DAYS:
                continue
            
            price_seg = price_series.loc[common_idx]
            rsi_seg = rsi_series.loc[common_idx]
            high_seg = high_series.loc[common_idx]
            low_seg = low_series.loc[common_idx]
            
            is_div, metrics = check_daily_divergence(price_seg, rsi_seg, high_seg, low_seg)
            
            if is_div:
                daily_candidates.append({
                    "code": code,
                    "name": name_map.get(code, code),
                    "price": s_close[code],
                    "pchg": s_pchg.get(code, 0.0),
                    "metrics": metrics,
                    "timeframe": "日線"
                })
        except Exception as e:
            if DEBUG_MODE:
                print(f"   ⚠️ {code} 處理失敗: {str(e)[:50]}")
            continue
    
    print(f"\n✅ 日線掃描完成！發現 {len(daily_candidates)} 檔 RSI 底背離突破。")
    
    # ========================================
    # 第三階段：周線 RSI 底背離 + 突破確認
    # ========================================
    weekly_candidates = []
    
    if ENABLE_WEEKLY:
        print("\n📊 第三階段：周線 RSI 底背離掃描 (含突破確認)...")
        
        for i, code in enumerate(candidates):
            if (i + 1) % 50 == 0:
                print(f"   Weekly Progress: {i + 1}/{total}...", end="\r")
            
            try:
                price_series = df_close[code].dropna()
                high_series = df_high[code].dropna()
                low_series = df_low[code].dropna()
                
                common_idx = price_series.index.intersection(high_series.index).intersection(low_series.index)
                if len(common_idx) < 100:
                    continue
                
                price_seg = price_series.loc[common_idx]
                high_seg = high_series.loc[common_idx]
                low_seg = low_series.loc[common_idx]
                
                is_div, metrics = check_weekly_divergence(price_seg, high_seg, low_seg)
                
                if is_div:
                    weekly_candidates.append({
                        "code": code,
                        "name": name_map.get(code, code),
                        "price": s_close[code],
                        "pchg": s_pchg.get(code, 0.0),
                        "metrics": metrics,
                        "timeframe": "周線"
                    })
            except Exception as e:
                if DEBUG_MODE:
                    print(f"   ⚠️ {code} 周線處理失敗: {str(e)[:50]}")
                continue
        
        print(f"\n✅ 周線掃描完成！發現 {len(weekly_candidates)} 檔周線 RSI 底背離突破。")
    
    # ========================================
    # 輸出報告
    # ========================================
    all_candidates = daily_candidates + weekly_candidates
    
    if all_candidates:
        msg = f"💎 **RSI 底背離精選** (Trend Follow)\n📅 {date_str}\n\n"
        
        # 日線結果
        if daily_candidates:
            msg += "📈 【日線底背離突破】\n"
            for x in daily_candidates:
                sign = "+" if x['pchg'] >= 0 else ""
                m = x['metrics']
                msg += f"💎 {x['code']} {x['name']}\n"
                msg += f"   💰 {x['price']:.1f}({sign}{x['pchg']:.1f}%)\n"
                msg += f"   📉 Price: {m['p_a']:.1f}→{m['p_b']:.1f} | RSI: {m['r_a']:.0f}→{m['r_b']:.0f}\n"
                msg += f"   ✅ 突破 {m['breakout_level']:.1f} (距低點{m['days_since_low']}天)\n\n"
        
        # 周線結果
        if weekly_candidates:
            msg += "📊 【周線底背離突破】\n"
            for x in weekly_candidates:
                sign = "+" if x['pchg'] >= 0 else ""
                m = x['metrics']
                msg += f"🔷 {x['code']} {x['name']}\n"
                msg += f"   💰 {x['price']:.1f}({sign}{x['pchg']:.1f}%)\n"
                msg += f"   📉 Price: {m['p_a']:.1f}→{m['p_b']:.1f} | RSI: {m['r_a']:.0f}→{m['r_b']:.0f}\n"
                msg += f"   ✅ 周線突破 {m['breakout_level']:.1f} (距低點{m['weeks_since_low']}週)\n\n"
        
        send_tg_msg(msg)
        print("\n📢 報告已發送至 Telegram。")
        
        # 新增：輸出到 CSV
        df_result = pd.DataFrame([
            {
                'code': x['code'],
                'name': x['name'],
                'timeframe': x['timeframe'],
                'price': x['price'],
                'pchg': x['pchg'],
                'date_a': x['metrics']['date_a'],
                'date_b': x['metrics']['date_b'],
                'date_confirm': x['metrics']['date_confirm'],
                'days_since_low': x['metrics'].get('days_since_low') or x['metrics'].get('weeks_since_low'),
                'p_a': x['metrics']['p_a'],
                'p_b': x['metrics']['p_b'],
                'r_a': x['metrics']['r_a'],
                'r_b': x['metrics']['r_b'],
                'price_drop_pct': x['metrics'].get('price_drop_pct', 0),
                'rsi_rise_pct': x['metrics'].get('rsi_rise_pct', 0),
                'breakout_level': x['metrics']['breakout_level']
            }
            for x in all_candidates
        ])
        
        csv_filename = os.path.join(project_root, 'logs', f'rsi_divergence_{date_str}.csv')
        os.makedirs(os.path.dirname(csv_filename), exist_ok=True)
        df_result.to_csv(csv_filename, index=False, encoding='utf-8-sig')
        print(f"✅ 結果已存檔至 {csv_filename}")
    else:
        print("\n🍂 今日無符合 RSI 底背離突破的股票。")
        send_tg_msg(f"💎 **RSI 底背離精選**\n📅 {date_str}\n\n今日無符合標準的標的 (Wait for setup)。")


def send_tg_msg(message):
    """發送 Telegram 訊息"""
    CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
    TOKEN = os.getenv("TELEGRAM_TOKEN", "")
    if not TOKEN or not CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"},
            timeout=10
        )
    except Exception:
        pass


if __name__ == "__main__":
    try:
        run_screener()
    except Exception as e:
        print(f"\n❌ 錯誤: {e}")
        import traceback
        traceback.print_exc()
