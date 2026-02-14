# -*- coding: utf-8 -*-
"""
交易日判斷共用模組 (FinMind API)

提供三個函數：
1. is_trading_day(date_str, force)   - 指定日期是否為交易日
2. is_yesterday_trading_day()        - 昨天是否為交易日（給隔天早上8點的任務用）
3. get_last_trading_day_of_week()    - 取得該週最後一個交易日
"""

import os
import sys
import time
import requests
from datetime import datetime, timedelta


def _query_trading_dates(start_date, end_date, max_retries=3):
    """
    查詢 FinMind TaiwanStockTradingDate API
    
    Args:
        start_date: 起始日期 'YYYY-MM-DD'
        end_date:   結束日期 'YYYY-MM-DD'
        max_retries: 最大重試次數
    
    Returns:
        list[str] | None: 交易日清單，API 失敗回傳 None
    """
    token = os.getenv("FINMIND_TOKEN", "")
    if not token:
        print("⚠️ 未設定 FINMIND_TOKEN 環境變數")
        return None
    
    url = "https://api.finmindtrade.com/api/v4/data"
    params = {
        "dataset": "TaiwanStockTradingDate",
        "start_date": start_date,
        "end_date": end_date,
        "token": token
    }
    
    for attempt in range(max_retries):
        try:
            res = requests.get(url, params=params, timeout=20)
            if res.status_code == 200:
                data = res.json().get('data', [])
                return [d['date'] for d in data]
            else:
                print(f"⚠️ API 回傳錯誤碼: {res.status_code}")
        except Exception as e:
            print(f"⚠️ API 連線失敗 ({attempt+1}/{max_retries}): {e}")
            time.sleep(2)
    
    return None


def is_trading_day(date_str=None, force=False):
    """
    檢查指定日期是否為交易日
    
    Args:
        date_str: 日期字串 'YYYY-MM-DD'，預設今天
        force: 強制模式（忽略檢查直接回傳 True）
    
    Returns:
        bool
    """
    if force or "--force" in sys.argv:
        print("⚠️ [Force Mode] 強制執行，跳過交易日檢查。")
        return True
    
    if date_str is None:
        date_str = datetime.now().strftime('%Y-%m-%d')
    
    print(f"📅 確認 {date_str} 是否為交易日...")
    
    # 1. 週末快速排除
    dt = datetime.strptime(date_str, '%Y-%m-%d')
    weekday = dt.weekday()
    if weekday >= 5:
        day_name = '六' if weekday == 5 else '日'
        print(f"💤 {date_str} 是週{day_name}，非交易日。")
        return False
    
    # 2. FinMind API 查詢
    dates = _query_trading_dates(date_str, date_str)
    if dates is not None:
        if date_str in dates:
            print(f"✅ {date_str} 確認為交易日 (FinMind API)。")
            return True
        else:
            print(f"💤 {date_str} 非交易日（可能是國定假日）。")
            return False
    
    # 3. Fallback: API 失敗但為平日，強制執行
    print("⚠️ 無法連線至 FinMind API，啟用備援判斷：為平日，強制執行。")
    return True


def is_yesterday_trading_day():
    """
    檢查昨天是否為交易日
    
    用途：給隔天早上 8 點跑的排程（如 daily_analysis.yml）
    邏輯：如果昨天是交易日，才執行分析
    
    Returns:
        bool
    """
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    print(f"📅 確認昨天 ({yesterday}) 是否為交易日...")
    
    dates = _query_trading_dates(yesterday, yesterday)
    if dates is not None:
        if yesterday in dates:
            print(f"✅ 昨天 ({yesterday}) 是交易日。")
            return True
        else:
            print(f"💤 昨天 ({yesterday}) 非交易日。")
            return False
    
    # Fallback: 昨天非週末就當交易日
    wd = (datetime.now() - timedelta(days=1)).weekday()
    fallback = wd < 5
    print(f"⚠️ API 失敗，備援判斷：昨天{'是' if fallback else '非'}平日。")
    return fallback


def get_last_trading_day_of_week(target_date=None):
    """
    取得 target_date 所在週的最後一個交易日
    
    用途：決定是否執行週報
    
    Args:
        target_date: 日期字串 'YYYY-MM-DD'，預設昨天
    
    Returns:
        str | None: 最後交易日字串，查無資料回傳 None
    """
    if target_date is None:
        target_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    # 取得該週的日期範圍 (週一到週日)
    target_dt = datetime.strptime(target_date, '%Y-%m-%d')
    monday = target_dt - timedelta(days=target_dt.weekday())
    sunday = monday + timedelta(days=6)
    
    dates = _query_trading_dates(
        monday.strftime('%Y-%m-%d'),
        sunday.strftime('%Y-%m-%d')
    )
    
    if dates is None:
        # Fallback: 若 API 掛，用週五判斷
        print("⚠️ 無法查詢交易日清單，改用週五判斷")
        friday = monday + timedelta(days=4)
        return friday.strftime('%Y-%m-%d')
    
    if not dates:
        return None
    
    return sorted(dates)[-1]


def is_last_trading_day_of_week(target_date=None):
    """
    檢查 target_date 是否為該週最後一個交易日
    
    Args:
        target_date: 日期字串 'YYYY-MM-DD'，預設昨天
    
    Returns:
        bool
    """
    if target_date is None:
        target_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    last_day = get_last_trading_day_of_week(target_date)
    result = (target_date == last_day)
    
    if result:
        print(f"📅 {target_date} 是本週最後交易日。")
    else:
        print(f"📅 {target_date} 不是本週最後交易日（最後交易日: {last_day}）。")
    
    return result
