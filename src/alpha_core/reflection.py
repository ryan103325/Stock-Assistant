"""
台股新聞情緒分析 - REFLECT 反省模組
包含：K 棒型態分析、量價關係、RSI 計算、AI 反省
"""

import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from .config import HISTORY_DIR, TAIEX_PATH
from .database import SentimentDB
from .llm_client import get_reflector_client


# ==================== K 棒型態分析 ====================

def analyze_candlestick(ohlcv: Dict) -> Tuple[str, Dict]:
    """
    分析 K 棒型態
    
    Returns:
        (pattern_name, ratios_dict)
    """
    o, h, l, c = ohlcv['open'], ohlcv['high'], ohlcv['low'], ohlcv['close']
    
    # 計算各部分比例
    total_range = h - l
    if total_range == 0:
        return ("十字線", {"body": 0, "upper": 0, "lower": 0})
    
    body = abs(c - o)
    upper_shadow = h - max(o, c)
    lower_shadow = min(o, c) - l
    
    body_ratio = body / total_range
    upper_ratio = upper_shadow / total_range
    lower_ratio = lower_shadow / total_range
    
    ratios = {
        "body": round(body_ratio, 3),
        "upper": round(upper_ratio, 3),
        "lower": round(lower_ratio, 3)
    }
    
    is_bullish = c > o
    
    # 型態判斷 (參考規格書)
    if body_ratio < 0.10:
        # 十字線系列
        if lower_ratio > 0.60:
            return ("T字線", ratios)         # 🟢 多頭反轉
        elif upper_ratio > 0.60:
            return ("倒T字線", ratios)       # 🔴 空頭反轉
        else:
            return ("十字線", ratios)        # ⚠️ 方向不明
    
    elif body_ratio < 0.30:
        # 錘子線系列
        if lower_ratio > 0.40:
            return ("錘子線", ratios)        # 🟢 止跌訊號
        elif upper_ratio > 0.40:
            return ("射擊之星", ratios)      # 🔴 見頂訊號
    
    elif body_ratio > 0.70:
        # 大陽線/大陰線
        if is_bullish:
            return ("大陽線", ratios)        # 🟢 強勢看多
        else:
            return ("大陰線", ratios)        # 🔴 恐慌拋售
    
    else:
        # 中等實體
        if upper_ratio > 0.50:
            if is_bullish:
                return ("上影陽線", ratios)  # ⚠️ 上檔壓力
            else:
                return ("上影陰線", ratios)  # 🔴 空方主導
        elif lower_ratio > 0.50:
            if is_bullish:
                return ("下影陽線", ratios)  # 🟢 多方強勢
            else:
                return ("下影陰線", ratios)  # ⚠️ 可能反彈
        else:
            if is_bullish:
                return ("陽線", ratios)
            else:
                return ("陰線", ratios)
    
    return ("普通K棒", ratios)


# ==================== 量價關係 ====================

def analyze_price_volume(today: Dict, yesterday: Dict) -> str:
    """
    分析量價關係
    
    Returns:
        pattern_name (價漲量增/價漲量縮/價跌量增/價跌量縮)
    """
    price_change = (today['close'] - yesterday['close']) / yesterday['close']
    volume_change = (today['volume'] - yesterday['volume']) / yesterday['volume'] if yesterday['volume'] > 0 else 0
    
    price_up = price_change > 0.001  # 微漲算漲
    volume_up = volume_change > 0.05  # 5% 門檻
    
    if price_up and volume_up:
        return "價漲量增"    # 🟢 健康上漲
    elif price_up and not volume_up:
        return "價漲量縮"    # ⚠️ 上漲無力
    elif not price_up and volume_up:
        return "價跌量增"    # 🔴 恐慌拋售
    else:
        return "價跌量縮"    # ⚠️ 洗盤可能


# ==================== RSI 計算 ====================

def calculate_rsi(closes: pd.Series, period: int = 14) -> float:
    """
    計算 RSI (TradingView ta.rsi 一致版本)
    
    Returns:
        RSI value (0-100)
    """
    if len(closes) < period + 1:
        return 50.0  # 資料不足，返回中性值
    
    delta = closes.diff()
    gains = delta.where(delta > 0, 0.0).fillna(0)
    losses = (-delta).where(delta < 0, 0.0).fillna(0)
    
    alpha = 1 / period
    rma_gain = gains.ewm(alpha=alpha, adjust=False).mean()
    rma_loss = losses.ewm(alpha=alpha, adjust=False).mean()
    
    # 避免除以零
    last_loss = rma_loss.iloc[-1]
    if last_loss == 0:
        return 100.0 if rma_gain.iloc[-1] > 0 else 50.0
    
    rs = rma_gain.iloc[-1] / last_loss
    rsi = 100 - (100 / (1 + rs))
    
    return round(rsi, 2)


def classify_rsi_zone(rsi: float) -> str:
    """RSI 區間分類"""
    if rsi > 70:
        return "STRONG_BULLISH"
    elif rsi >= 60:
        return "BULLISH"
    elif rsi >= 40:
        return "NEUTRAL"
    elif rsi >= 30:
        return "BEARISH"
    else:
        return "STRONG_BEARISH"


def detect_rsi_divergence(closes: pd.Series, rsi_series: pd.Series, lookback: int = 5) -> str:
    """
    偵測 RSI 背離
    
    Args:
        closes: 收盤價序列
        rsi_series: RSI 序列
        lookback: 回看期數
    
    Returns:
        NONE / BULLISH_DIVERGENCE / BEARISH_DIVERGENCE
    """
    if len(closes) < lookback + 1 or len(rsi_series) < lookback + 1:
        return "NONE"
    
    recent_closes = closes.iloc[-lookback:]
    recent_rsi = rsi_series.iloc[-lookback:]
    
    # 底背離: 價格創新低 + RSI 不創新低
    price_made_lower_low = recent_closes.iloc[-1] == recent_closes.min()
    rsi_didnt_make_lower_low = recent_rsi.iloc[-1] > recent_rsi.min()
    
    if price_made_lower_low and rsi_didnt_make_lower_low:
        return "BULLISH_DIVERGENCE"
    
    # 頂背離: 價格創新高 + RSI 不創新高
    price_made_higher_high = recent_closes.iloc[-1] == recent_closes.max()
    rsi_didnt_make_higher_high = recent_rsi.iloc[-1] < recent_rsi.max()
    
    if price_made_higher_high and rsi_didnt_make_higher_high:
        return "BEARISH_DIVERGENCE"
    
    return "NONE"


# ==================== 資料讀取 ====================

def read_stock_csv(ticker: str, date: str) -> Optional[Dict]:
    """讀取個股 K 棒資料"""
    if ticker == "TAIEX":
        file_path = TAIEX_PATH
    else:
        file_path = os.path.join(HISTORY_DIR, f"{ticker}.csv")
    
    if not os.path.exists(file_path):
        return None
    
    try:
        df = pd.read_csv(file_path)
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.set_index('Date').sort_index()
        
        target_date = pd.to_datetime(date)
        
        if target_date in df.index:
            row = df.loc[target_date]
            return {
                'date': date,
                'open': row['Open'],
                'high': row['High'],
                'low': row['Low'],
                'close': row['Close'],
                'volume': row['Volume']
            }
        return None
    except Exception as e:
        print(f"⚠️ 讀取 {ticker} 失敗: {e}")
        return None


def get_closes_series(ticker: str, end_date: str, periods: int = 20) -> pd.Series:
    """取得收盤價序列 (用於 RSI 計算)"""
    if ticker == "TAIEX":
        file_path = TAIEX_PATH
    else:
        file_path = os.path.join(HISTORY_DIR, f"{ticker}.csv")
    
    if not os.path.exists(file_path):
        return pd.Series()
    
    try:
        df = pd.read_csv(file_path)
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.set_index('Date').sort_index()
        
        end_dt = pd.to_datetime(end_date)
        df = df[df.index <= end_dt]
        
        return df['Close'].tail(periods)
    except:
        return pd.Series()


# ==================== 正確性判斷 ====================

def evaluate_correctness(predicted_label: str, predicted_score: float, actual_change_pct: float) -> Tuple[bool, str]:
    """
    判斷預測是否正確
    
    Returns:
        (is_correct, error_category)
    """
    # 預測方向
    if predicted_score > 0.2:
        predicted_direction = "BULLISH"
    elif predicted_score < -0.2:
        predicted_direction = "BEARISH"
    else:
        predicted_direction = "NEUTRAL"
    
    # 實際方向
    if actual_change_pct > 0.5:
        actual_direction = "BULLISH"
    elif actual_change_pct < -0.5:
        actual_direction = "BEARISH"
    else:
        actual_direction = "NEUTRAL"
    
    # 判斷
    if predicted_direction == actual_direction:
        return (True, None)
    elif predicted_direction == "NEUTRAL" or actual_direction == "NEUTRAL":
        return (True, None)  # 中性不算錯
    else:
        # 分類錯誤類型
        if predicted_direction == "BULLISH" and actual_direction == "BEARISH":
            return (False, "FALSE_POSITIVE")  # 預測看多，實際看空
        elif predicted_direction == "BEARISH" and actual_direction == "BULLISH":
            return (False, "FALSE_NEGATIVE")  # 預測看空，實際看多
        else:
            return (False, "DIRECTION_MISMATCH")


# ==================== AI 反省 ====================

async def ai_reflect(prediction: Dict, analysis: Dict, llm_client) -> Dict:
    """讓 AI 產生反省"""
    
    # 載入反省 Prompt
    prompt_path = os.path.join(os.path.dirname(__file__), "prompts", "reflector_system.txt")
    with open(prompt_path, 'r', encoding='utf-8') as f:
        system_prompt = f.read()
    
    user_prompt = f"""
## 預測資料
- 股票: {prediction.get('ticker')}
- 預測情緒: {prediction.get('sentiment_label')} ({prediction.get('sentiment_score')})
- 相關新聞: {prediction.get('title', 'N/A')}

## 今日實際表現
- 漲跌幅: {analysis.get('price_change_pct', 0):.2f}%
- K 棒型態: {analysis.get('candle_pattern')}
- 量價關係: {analysis.get('pv_pattern')}
- RSI(14): {analysis.get('rsi_value')} ({analysis.get('rsi_zone')})
- RSI 背離: {analysis.get('rsi_divergence')}

## 判斷結果
- 預測正確: {'是' if analysis.get('was_correct') else '否'}
- 錯誤分類: {analysis.get('error_category', '無')}

請分析預測與實際表現的差異，並給出反省與改進建議。
"""
    
    result = await llm_client.generate(system_prompt, user_prompt)
    
    if result and isinstance(result, dict):
        return result
    else:
        return {
            "is_accurate": analysis.get('was_correct', False),
            "reflection_notes": "AI 反省生成失敗"
        }


# ==================== 主流程 ====================

async def reflect_daily(target_date: str = None):
    """
    每日反省主流程
    
    Args:
        target_date: 反省日期 (預設今天)
    """
    print("=" * 50)
    print("🔍 REFLECT - 技術面反省")
    print("=" * 50)
    
    if target_date is None:
        target_date = datetime.now().strftime("%Y-%m-%d")
    
    print(f"📅 反省日期: {target_date}")
    
    db = SentimentDB()
    llm = get_reflector_client()
    
    with db as db_conn:
        db_conn.create_tables()
        predictions = db_conn.get_today_predictions(target_date)
    
    if not predictions:
        print("⚠️ 今日沒有預測資料")
        return
    
    print(f"📊 找到 {len(predictions)} 檔股票的預測")
    
    # 找到前一個交易日
    prev_date = (pd.to_datetime(target_date) - timedelta(days=1)).strftime("%Y-%m-%d")
    
    reflections_saved = 0
    
    for pred in predictions:
        ticker = pred['ticker']
        print(f"\n🔎 分析: {ticker}...")
        
        # 1. 讀取今日 K 棒
        today_ohlcv = read_stock_csv(ticker, target_date)
        if not today_ohlcv:
            print(f"   ⚠️ 無今日資料")
            continue
        
        # 2. 讀取昨日 K 棒
        yesterday_ohlcv = read_stock_csv(ticker, prev_date)
        if not yesterday_ohlcv:
            # 嘗試往前找
            for i in range(2, 5):
                alt_date = (pd.to_datetime(target_date) - timedelta(days=i)).strftime("%Y-%m-%d")
                yesterday_ohlcv = read_stock_csv(ticker, alt_date)
                if yesterday_ohlcv:
                    break
        
        if not yesterday_ohlcv:
            print(f"   ⚠️ 無前日資料")
            continue
        
        # 3. 計算技術指標
        candle_pattern, ratios = analyze_candlestick(today_ohlcv)
        pv_pattern = analyze_price_volume(today_ohlcv, yesterday_ohlcv)
        
        closes = get_closes_series(ticker, target_date, periods=30)
        rsi_value = calculate_rsi(closes, period=14)
        rsi_zone = classify_rsi_zone(rsi_value)
        
        # RSI 序列 (用於背離偵測)
        rsi_series = pd.Series([calculate_rsi(closes.iloc[:i+1], 14) for i in range(len(closes))])
        rsi_divergence = detect_rsi_divergence(closes, rsi_series, lookback=5)
        
        # 4. 計算漲跌幅
        price_change_pct = (today_ohlcv['close'] - yesterday_ohlcv['close']) / yesterday_ohlcv['close'] * 100
        volume_change_pct = (today_ohlcv['volume'] - yesterday_ohlcv['volume']) / yesterday_ohlcv['volume'] * 100 if yesterday_ohlcv['volume'] > 0 else 0
        
        # 5. 判斷正確性
        was_correct, error_category = evaluate_correctness(
            pred['sentiment_label'], 
            pred['sentiment_score'], 
            price_change_pct
        )
        
        analysis = {
            'price_change_pct': price_change_pct,
            'volume_change_pct': volume_change_pct,
            'candle_pattern': candle_pattern,
            'pv_pattern': pv_pattern,
            'rsi_value': rsi_value,
            'rsi_zone': rsi_zone,
            'rsi_divergence': rsi_divergence,
            'was_correct': was_correct,
            'error_category': error_category,
            **ratios
        }
        
        # 6. AI 反省 (只有錯誤時)
        reflection_text = ""
        lesson_learned = ""
        
        if not was_correct:
            print(f"   ❌ 預測錯誤，進行 AI 反省...")
            reflection = await ai_reflect(dict(pred), analysis, llm)
            reflection_text = str(reflection)
            lesson_learned = reflection.get('reflection_notes', '')[:500]
        else:
            print(f"   ✅ 預測正確")
        
        # 7. 存入資料庫
        with db as db_conn:
            db_conn.insert_reflection({
                'date': target_date,
                'ticker': ticker,
                'predicted_label': pred['sentiment_label'],
                'predicted_score': pred['sentiment_score'],
                'open_price': today_ohlcv['open'],
                'high_price': today_ohlcv['high'],
                'low_price': today_ohlcv['low'],
                'close_price': today_ohlcv['close'],
                'volume': today_ohlcv['volume'],
                'price_change_pct': price_change_pct,
                'volume_change_pct': volume_change_pct,
                'body_ratio': ratios['body'],
                'upper_shadow_ratio': ratios['upper'],
                'lower_shadow_ratio': ratios['lower'],
                'candle_pattern': candle_pattern,
                'pv_pattern': pv_pattern,
                'rsi_value': rsi_value,
                'rsi_zone': rsi_zone,
                'rsi_divergence': rsi_divergence,
                'was_correct': 1 if was_correct else 0,
                'error_category': error_category,
                'reflection_text': reflection_text,
                'lesson_learned': lesson_learned
            })
            reflections_saved += 1
    
    print(f"\n📊 REFLECT 完成:")
    print(f"   反省紀錄: {reflections_saved} 筆")
