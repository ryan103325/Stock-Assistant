import os
import sys
import pandas as pd
import numpy as np
import requests
from datetime import datetime
from dotenv import load_dotenv

# ============================================================
# RSI 背離篩選系統 (RSI Divergence Screener)
# v3.1 - TradingView Pivot + ISO 周線版
# ============================================================

# --- Load Environment Variables ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
env_path = os.path.join(project_root, ".env")
load_dotenv(env_path)

# 加入 src 路徑以便 import 共用模組
sys.path.insert(0, os.path.join(project_root, "src"))
from utils.trading_day_utils import is_trading_day

# --- Configuration ---
CACHE_FILE = os.path.join(project_root, "src", "cache", "market_matrix.pkl")
NAME_MAP_FILE = os.path.join(project_root, "src", "data_core", "market_meta", "moneydj_industries.csv")

# --- Parameters ---
LIQUIDITY_THRESHOLD = 50_000_000  # 5000萬 (Filter 1)
RSI_PERIOD = 14                    # RSI 週期（對齊 TradingView）
PIVOT_LB_LEFT = 5                  # Pivot Lookback Left
PIVOT_LB_RIGHT = 5                 # Pivot Lookback Right
RANGE_UPPER = 60                   # Max lookback range（前一個 pivot 最遠距離）
RANGE_LOWER = 5                    # Min lookback range（前一個 pivot 最近距離）
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


# is_trading_day 已移至 utils.trading_day_utils（透過 FinMind API 判斷）


# ============================================================
# 🔧 核心計算模組（對齊 TradingView）
# ============================================================

def calculate_rsi(price_series, period=14):
    """
    Wilder's RSI（與 TradingView ta.rsi 相同）
    
    邏輯：
    - 初始化：前 period 根用 SMA
    - 之後：Wilder 平滑 (alpha = 1/period)
    - RSI = 100 * avgUp / (avgUp + avgDown)
    """
    delta = price_series.diff()
    up = delta.clip(lower=0)
    down = (-delta).clip(lower=0)
    
    sum_up = np.zeros(len(price_series))
    sum_down = np.zeros(len(price_series))
    rsi = np.full(len(price_series), np.nan)
    
    first_valid = period
    
    if first_valid < len(price_series):
        sum_up[first_valid] = up.iloc[1:first_valid+1].mean()
        sum_down[first_valid] = down.iloc[1:first_valid+1].mean()
    
    alpha = 1.0 / period
    for i in range(first_valid + 1, len(price_series)):
        sum_up[i] = sum_up[i-1] + (up.iloc[i] - sum_up[i-1]) * alpha
        sum_down[i] = sum_down[i-1] + (down.iloc[i] - sum_down[i-1]) * alpha
    
    for i in range(first_valid, len(price_series)):
        denom = sum_up[i] + sum_down[i]
        if denom == 0:
            rsi[i] = 0
        else:
            rsi[i] = 100 * sum_up[i] / denom
    
    return pd.Series(rsi, index=price_series.index)


def find_pivot_lows(series, lbL=5, lbR=5):
    """
    翻譯 TradingView 的 ta.pivotlow
    
    在位置 i 處，如果 series[i] 是 [i-lbL, i+lbR] 範圍內的最小值，
    則 i 是 pivot low。
    
    Returns:
        list of int: pivot low 的位置索引
    """
    vals = series.values
    pivots = []
    
    for i in range(lbL, len(vals) - lbR):
        val = vals[i]
        if np.isnan(val):
            continue
        
        is_pivot = True
        for j in range(i - lbL, i):
            if np.isnan(vals[j]) or vals[j] < val:
                is_pivot = False
                break
        
        if not is_pivot:
            continue
        
        for j in range(i + 1, i + lbR + 1):
            if np.isnan(vals[j]) or vals[j] < val:
                is_pivot = False
                break
        
        if is_pivot:
            pivots.append(i)
    
    return pivots


def find_pivot_highs(series, lbL=5, lbR=5):
    """
    翻譯 TradingView 的 ta.pivothigh
    
    在位置 i 處，如果 series[i] 是 [i-lbL, i+lbR] 範圍內的最大值，
    則 i 是 pivot high。
    
    Returns:
        list of int: pivot high 的位置索引
    """
    vals = series.values
    pivots = []
    
    for i in range(lbL, len(vals) - lbR):
        val = vals[i]
        if np.isnan(val):
            continue
        
        is_pivot = True
        for j in range(i - lbL, i):
            if np.isnan(vals[j]) or vals[j] > val:
                is_pivot = False
                break
        
        if not is_pivot:
            continue
        
        for j in range(i + 1, i + lbR + 1):
            if np.isnan(vals[j]) or vals[j] > val:
                is_pivot = False
                break
        
        if is_pivot:
            pivots.append(i)
    
    return pivots


def detect_divergences(rsi_series, price_high, price_low,
                       lbL=5, lbR=5, range_lower=5, range_upper=60):
    """
    翻譯 TradingView RSI Divergence Indicator 的背離偵測邏輯
    
    Regular Bullish:  RSI Higher Low + Price Lower Low   (底部反轉)
    Hidden Bullish:   RSI Lower Low  + Price Higher Low  (趨勢延續)
    Regular Bearish:  RSI Lower High + Price Higher High  (頂部反轉)
    Hidden Bearish:   RSI Higher High + Price Lower High  (趨勢延續)
    
    Args:
        rsi_series: RSI pd.Series
        price_high: 最高價 pd.Series（用於 bearish 比較）
        price_low:  最低價 pd.Series（用於 bullish 比較）
        lbL, lbR:   Pivot lookback 參數
        range_lower, range_upper: 前一個 pivot 的有效距離範圍
    
    Returns:
        list of dict: 每個背離訊號
    """
    rsi_vals = rsi_series.values
    high_vals = price_high.values
    low_vals = price_low.values
    
    # 找 RSI 的 pivot points
    pivot_lows = find_pivot_lows(rsi_series, lbL, lbR)
    pivot_highs = find_pivot_highs(rsi_series, lbL, lbR)
    
    signals = []
    
    # --- Bullish divergences (在 pivot low 處檢查) ---
    for i, pl_idx in enumerate(pivot_lows):
        prev_pl_idx = None
        for j in range(i - 1, -1, -1):
            bars_diff = pl_idx - pivot_lows[j]
            if range_lower <= bars_diff <= range_upper:
                prev_pl_idx = pivot_lows[j]
                break
        
        if prev_pl_idx is None:
            continue
        
        rsi_curr = rsi_vals[pl_idx]
        rsi_prev = rsi_vals[prev_pl_idx]
        price_curr = low_vals[pl_idx]
        price_prev = low_vals[prev_pl_idx]
        
        confirm_bar = pl_idx + lbR
        if confirm_bar >= len(rsi_vals):
            continue
        
        # Regular Bullish: RSI Higher Low + Price Lower Low
        if rsi_curr > rsi_prev and price_curr < price_prev:
            signals.append({
                'bar': pl_idx,
                'confirm_bar': confirm_bar,
                'type': 'bull',
                'rsi_curr': rsi_curr,
                'rsi_prev': rsi_prev,
                'price_curr': price_curr,
                'price_prev': price_prev,
            })
        
        # Hidden Bullish: RSI Lower Low + Price Higher Low
        if rsi_curr < rsi_prev and price_curr > price_prev:
            signals.append({
                'bar': pl_idx,
                'confirm_bar': confirm_bar,
                'type': 'hidden_bull',
                'rsi_curr': rsi_curr,
                'rsi_prev': rsi_prev,
                'price_curr': price_curr,
                'price_prev': price_prev,
            })
    
    # --- Bearish divergences (在 pivot high 處檢查) ---
    for i, ph_idx in enumerate(pivot_highs):
        prev_ph_idx = None
        for j in range(i - 1, -1, -1):
            bars_diff = ph_idx - pivot_highs[j]
            if range_lower <= bars_diff <= range_upper:
                prev_ph_idx = pivot_highs[j]
                break
        
        if prev_ph_idx is None:
            continue
        
        rsi_curr = rsi_vals[ph_idx]
        rsi_prev = rsi_vals[prev_ph_idx]
        price_curr = high_vals[ph_idx]
        price_prev = high_vals[prev_ph_idx]
        
        confirm_bar = ph_idx + lbR
        if confirm_bar >= len(rsi_vals):
            continue
        
        # Regular Bearish: RSI Lower High + Price Higher High
        if rsi_curr < rsi_prev and price_curr > price_prev:
            signals.append({
                'bar': ph_idx,
                'confirm_bar': confirm_bar,
                'type': 'bear',
                'rsi_curr': rsi_curr,
                'rsi_prev': rsi_prev,
                'price_curr': price_curr,
                'price_prev': price_prev,
            })
        
        # Hidden Bearish: RSI Higher High + Price Lower High
        if rsi_curr > rsi_prev and price_curr < price_prev:
            signals.append({
                'bar': ph_idx,
                'confirm_bar': confirm_bar,
                'type': 'hidden_bear',
                'rsi_curr': rsi_curr,
                'rsi_prev': rsi_prev,
                'price_curr': price_curr,
                'price_prev': price_prev,
            })
    
    signals.sort(key=lambda x: x['confirm_bar'])
    return signals


def check_divergences_for_stock(price_close, price_high, price_low,
                                rsi_period=14, max_bars_ago=10):
    """
    對單一股票偵測最近的 RSI 背離訊號
    """
    if len(price_close) < rsi_period + PIVOT_LB_LEFT + PIVOT_LB_RIGHT + RANGE_LOWER:
        return []
    
    rsi = calculate_rsi(price_close, period=rsi_period)
    
    all_signals = detect_divergences(
        rsi, price_high, price_low,
        lbL=PIVOT_LB_LEFT, lbR=PIVOT_LB_RIGHT,
        range_lower=RANGE_LOWER, range_upper=RANGE_UPPER
    )
    
    if not all_signals:
        return []
    
    last_bar = len(price_close) - 1
    recent_signals = []
    
    for sig in all_signals:
        bars_ago = last_bar - sig['confirm_bar']
        if 0 <= bars_ago <= max_bars_ago:
            sig['date_pivot'] = price_close.index[sig['bar']]
            sig['date_confirm'] = price_close.index[sig['confirm_bar']]
            sig['bars_ago'] = bars_ago
            recent_signals.append(sig)
    
    return recent_signals


# ============================================================
# 📅 周線聚合（ISO 周次分組）
# ============================================================

def daily_to_weekly(daily_series, agg='last'):
    """
    將日線 Series 轉為周線，使用 ISO 周次分組
    
    邏輯：
    - 用 isocalendar() 取得每個交易日的 (year, week)
    - 同一 (year, week) 的交易日歸為同一週
    - 正確處理假日（如春節週只有 2~3 天交易）
    
    Args:
        daily_series: 日線資料 pd.Series (DatetimeIndex)
        agg: 聚合方式 'last'(收盤), 'max'(最高), 'min'(最低),
             'first'(開盤), 'sum'(成交量)
    
    Returns:
        pd.Series: 周線資料，index 為該週最後一個交易日
    """
    if daily_series.empty:
        return daily_series
    
    # 建立 (year, week) 分組 key
    iso = daily_series.index.isocalendar()
    group_key = iso.year.astype(str) + '-W' + iso.week.astype(str).str.zfill(2)
    
    grouped = daily_series.groupby(group_key)
    
    if agg == 'last':
        result = grouped.last()
    elif agg == 'max':
        result = grouped.max()
    elif agg == 'min':
        result = grouped.min()
    elif agg == 'first':
        result = grouped.first()
    elif agg == 'sum':
        result = grouped.sum()
    else:
        result = grouped.last()
    
    # 用每組最後一個交易日作為 index（保留 DatetimeIndex）
    last_dates = daily_series.groupby(group_key).apply(lambda x: x.index[-1])
    result.index = last_dates.values
    result.index = pd.DatetimeIndex(result.index)
    result = result.sort_index()
    
    return result


# ============================================================
# 📈 日線背離掃描
# ============================================================

def scan_daily_divergences(candidates, df_close, df_high, df_low,
                           name_map, s_close, s_pchg):
    """
    日線 RSI 背離掃描（獨立函數）
    
    Args:
        candidates: 股票代碼列表
        df_close/df_high/df_low: 日線 OHLC DataFrame
        name_map: 股票名稱對照表
        s_close: 最新收盤價 Series
        s_pchg: 最新漲跌幅 Series
    
    Returns:
        list of dict: 日線背離訊號列表
    """
    print(f"\n📈 日線 RSI 背離掃描 (RSI={RSI_PERIOD}, Pivot L={PIVOT_LB_LEFT}/R={PIVOT_LB_RIGHT})...")
    
    daily_results = []
    total = len(candidates)
    
    for i, code in enumerate(candidates):
        if (i + 1) % 50 == 0:
            print(f"   Progress: {i + 1}/{total}...", end="\r")
        
        try:
            price_close = df_close[code].dropna()
            price_high = df_high[code].dropna()
            price_low = df_low[code].dropna()
            
            common_idx = price_close.index.intersection(price_high.index).intersection(price_low.index)
            if len(common_idx) < 100:
                continue
            
            pc = price_close.loc[common_idx]
            ph = price_high.loc[common_idx]
            pl = price_low.loc[common_idx]
            
            signals = check_divergences_for_stock(
                pc, ph, pl,
                rsi_period=RSI_PERIOD,
                max_bars_ago=0  # 只取今天確認的
            )
            
            for sig in signals:
                daily_results.append({
                    "code": code,
                    "name": name_map.get(code, code),
                    "price": s_close[code],
                    "pchg": s_pchg.get(code, 0.0),
                    "signal": sig,
                    "timeframe": "日線"
                })
        except Exception as e:
            if DEBUG_MODE:
                print(f"   ⚠️ {code} 處理失敗: {str(e)[:50]}")
            continue
    
    print(f"\n✅ 日線掃描完成！發現 {len(daily_results)} 個背離訊號。")
    return daily_results


# ============================================================
# 📊 周線背離掃描
# ============================================================

def scan_weekly_divergences(candidates, df_close, df_high, df_low,
                            name_map, s_close, s_pchg):
    """
    周線 RSI 背離掃描（獨立函數）
    
    使用 ISO 周次分組建構周線資料（非 resample('W-FRI')）。
    每週的交易日根據實際日曆周次歸類，確保假日週正確處理。
    
    Args:
        candidates: 股票代碼列表
        df_close/df_high/df_low: 日線 OHLC DataFrame
        name_map: 股票名稱對照表
        s_close: 最新收盤價 Series
        s_pchg: 最新漲跌幅 Series
    
    Returns:
        list of dict: 周線背離訊號列表
    """
    print(f"\n📊 周線 RSI 背離掃描 (ISO 周次分組)...")
    
    weekly_results = []
    total = len(candidates)
    
    for i, code in enumerate(candidates):
        if (i + 1) % 50 == 0:
            print(f"   Weekly Progress: {i + 1}/{total}...", end="\r")
        
        try:
            price_close = df_close[code].dropna()
            price_high = df_high[code].dropna()
            price_low = df_low[code].dropna()
            
            common_idx = price_close.index.intersection(price_high.index).intersection(price_low.index)
            if len(common_idx) < 100:
                continue
            
            pc = price_close.loc[common_idx]
            ph = price_high.loc[common_idx]
            pl = price_low.loc[common_idx]
            
            # 用 ISO 周次分組轉周線
            weekly_close = daily_to_weekly(pc, agg='last')
            weekly_high = daily_to_weekly(ph, agg='max')
            weekly_low = daily_to_weekly(pl, agg='min')
            
            if len(weekly_close) < 30:
                continue
            
            signals = check_divergences_for_stock(
                weekly_close, weekly_high, weekly_low,
                rsi_period=RSI_PERIOD,
                max_bars_ago=0  # 只取本週確認的
            )
            
            for sig in signals:
                weekly_results.append({
                    "code": code,
                    "name": name_map.get(code, code),
                    "price": s_close[code],
                    "pchg": s_pchg.get(code, 0.0),
                    "signal": sig,
                    "timeframe": "周線"
                })
        except Exception as e:
            if DEBUG_MODE:
                print(f"   ⚠️ {code} 周線處理失敗: {str(e)[:50]}")
            continue
    
    print(f"\n✅ 周線掃描完成！發現 {len(weekly_results)} 個背離訊號。")
    return weekly_results


# ============================================================
# 🚀 主篩選流程
# ============================================================

def run_screener():
    """主篩選流程"""
    print("🚀 啟動 RSI 背離篩選系統 v3.1 (TradingView Pivot + ISO 周線)...")
    print(f"   📋 RSI={RSI_PERIOD} | Pivot L={PIVOT_LB_LEFT} R={PIVOT_LB_RIGHT} | Range={RANGE_LOWER}~{RANGE_UPPER}")
    
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
    df_volume = data.get('volume')
    
    if df_close is None or df_high is None or df_low is None:
        print("❌ 缺少必要資料 (close/high/low).")
        return
    
    # 前向填充缺失值
    df_close = df_close.ffill()
    df_high = df_high.ffill()
    df_low = df_low.ffill()
    
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
    
    # Filter 3: 趨勢向上 (MA200 10日斜率 > 0)
    def calc_ma_slope(ma_series, window=10):
        def linear_slope(y):
            if len(y) < window or y.isna().any():
                return np.nan
            x = np.arange(len(y))
            return np.polyfit(x, y, 1)[0]
        return ma_series.rolling(window).apply(linear_slope, raw=False)
    
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
    # 第二階段：日線 RSI 背離掃描
    # ========================================
    daily_candidates = scan_daily_divergences(
        candidates, df_close, df_high, df_low,
        name_map, s_close, s_pchg
    )
    
    # ========================================
    # 第三階段：周線 RSI 背離掃描
    # ========================================
    weekly_candidates = []
    if ENABLE_WEEKLY:
        weekly_candidates = scan_weekly_divergences(
            candidates, df_close, df_high, df_low,
            name_map, s_close, s_pchg
        )
    
    # ========================================
    # 輸出報告
    # ========================================
    all_candidates = daily_candidates + weekly_candidates
    
    TYPE_LABELS = {
        'bull': ('💎', 'Regular Bullish', '底背離'),
        'hidden_bull': ('🔹', 'Hidden Bullish', '隱藏底背離'),
        'bear': ('🔴', 'Regular Bearish', '頂背離'),
        'hidden_bear': ('🔸', 'Hidden Bearish', '隱藏頂背離'),
    }
    
    if all_candidates:
        msg = f"📊 **RSI 背離篩選** (TradingView Pivot)\n📅 {date_str}\n\n"
        
        for tf_label, tf_list in [("📈 【日線】", daily_candidates), ("📊 【周線】", weekly_candidates)]:
            if not tf_list:
                continue
            
            msg += f"{tf_label}\n"
            
            by_type = {}
            for x in tf_list:
                t = x['signal']['type']
                by_type.setdefault(t, []).append(x)
            
            for div_type in ['bull', 'hidden_bull', 'bear', 'hidden_bear']:
                items = by_type.get(div_type, [])
                if not items:
                    continue
                
                emoji, eng_label, cn_label = TYPE_LABELS[div_type]
                msg += f"\n{emoji} {cn_label} ({eng_label}) × {len(items)}\n"
                
                for x in items:
                    sig = x['signal']
                    sign = "+" if x['pchg'] >= 0 else ""
                    msg += f"  {emoji} {x['code']} {x['name']}"
                    msg += f" | {x['price']:.1f}({sign}{x['pchg']:.1f}%)"
                    msg += f" | RSI: {sig['rsi_prev']:.0f}→{sig['rsi_curr']:.0f}"
                    msg += f" | Price: {sig['price_prev']:.1f}→{sig['price_curr']:.1f}\n"
            
            msg += "\n"
        
        send_tg_msg(msg)
        print("\n📢 報告已發送至 Telegram。")
        
        # 存檔到 CSV
        df_result = pd.DataFrame([
            {
                'code': x['code'],
                'name': x['name'],
                'timeframe': x['timeframe'],
                'div_type': x['signal']['type'],
                'price': x['price'],
                'pchg': x['pchg'],
                'rsi_curr': x['signal']['rsi_curr'],
                'rsi_prev': x['signal']['rsi_prev'],
                'price_curr': x['signal']['price_curr'],
                'price_prev': x['signal']['price_prev'],
                'date_pivot': x['signal']['date_pivot'].strftime('%Y-%m-%d'),
                'date_confirm': x['signal']['date_confirm'].strftime('%Y-%m-%d'),
                'bars_ago': x['signal']['bars_ago'],
            }
            for x in all_candidates
        ])
        
        csv_filename = os.path.join(project_root, 'logs', f'rsi_divergence_{date_str}.csv')
        os.makedirs(os.path.dirname(csv_filename), exist_ok=True)
        df_result.to_csv(csv_filename, index=False, encoding='utf-8-sig')
        print(f"✅ 結果已存檔至 {csv_filename}")
    else:
        print("\n🍂 今日無符合 RSI 背離的股票。")
        send_tg_msg(f"📊 **RSI 背離篩選**\n📅 {date_str}\n\n今日無符合標準的標的。")


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
