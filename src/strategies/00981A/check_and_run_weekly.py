"""
檢查是否為本週最後交易日，若是則執行週報 (00981aW.py)
用於 step_strategies_00981A.yml workflow
"""
import os
import sys
import subprocess
from datetime import datetime, timedelta

import requests

def is_last_trading_day_of_week(target_date=None):
    """
    檢查 target_date (預設昨天) 是否為該週最後一個交易日
    """
    if target_date is None:
        target_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    # 取得該週的日期範圍 (週一到週日)
    target_dt = datetime.strptime(target_date, '%Y-%m-%d')
    monday = target_dt - timedelta(days=target_dt.weekday())
    sunday = monday + timedelta(days=6)
    
    token = os.getenv("FINMIND_TOKEN", "")
    try:
        url = "https://api.finmind.tw/api/v4/data"
        params = {
            "dataset": "TaiwanStockPrice",
            "data_id": "0050",
            "start_date": monday.strftime('%Y-%m-%d'),
            "end_date": sunday.strftime('%Y-%m-%d'),
            "token": token
        }
        resp = requests.get(url, params=params, timeout=15)
        data = resp.json().get("data", [])
        dates = sorted(set(d["date"] for d in data))
    except Exception as e:
        print(f"⚠️ 無法查詢交易日清單: {e}，改用週五判斷")
        return target_dt.weekday() == 4
    
    if not dates:
        return False
    
    last_trading_day = max(dates)
    is_last = target_date == last_trading_day
    if is_last:
        print(f"📅 {target_date} 是本週最後交易日，將執行週報")
    else:
        print(f"📅 {target_date} 不是本週最後交易日（最後交易日: {last_trading_day}），跳過週報")
    return is_last


if __name__ == "__main__":
    force = "--force" in sys.argv
    
    if not is_last_trading_day_of_week():
        print("📅 非本週最後交易日，跳過週報")
        sys.exit(0)
    
    print("🚀 執行週報...")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    weekly_script = os.path.join(script_dir, "00981aW.py")
    
    cmd = [sys.executable, weekly_script]
    if force:
        cmd.append("--force")
    
    result = subprocess.run(cmd, check=False)
    sys.exit(result.returncode)
