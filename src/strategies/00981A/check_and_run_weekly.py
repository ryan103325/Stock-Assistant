"""
檢查是否為本週最後交易日，若是則執行週報 (00981aW.py)
用於 step_strategies_00981A.yml workflow
"""
import os
import sys
import subprocess

# 加入 src 路徑以便 import 共用模組
SRC_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, SRC_ROOT)

from utils.trading_day_utils import is_last_trading_day_of_week


if __name__ == "__main__":
    force = "--force" in sys.argv
    
    if not force and not is_last_trading_day_of_week():
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
