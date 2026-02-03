import subprocess
import os
import sys
import time
from datetime import datetime

# 設定路徑
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(CURRENT_DIR))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")

# 🌅 早場任務 (早上 8:00 執行)
# 目的: 抓取 RSS 新聞並進行情緒分析
TASKS = [
    ("抓取 RSS 新聞", os.path.join(SRC_DIR, "alpha_core", "main.py"), ["fetch"]),
    ("分析新聞情緒", os.path.join(SRC_DIR, "alpha_core", "main.py"), ["analyze"]),
]

def run_script(name, path, args=None):
    print(f"\n🚀 正在執行: {name} ({os.path.basename(path)})...")
    try:
        if not os.path.exists(path):
            print(f"❌ 找不到檔案: {path}")
            return
            
        cmd = [sys.executable, path]
        if args:
            cmd.extend(args)
            
        result = subprocess.run(cmd, check=False)
        if result.returncode == 0:
            print(f"✅ {name} 完成。")
        else:
            print(f"❌ {name} 失敗 (Exit Code: {result.returncode})")
    except Exception as e:
        print(f"❌ 執行錯誤: {e}")

def main():
    print("==========================================")
    print("      🌅 早場排程 (情緒分析)")
    print("      執行時間: 早上 8:00")
    print("==========================================")
    
    today_str = datetime.now().strftime('%Y-%m-%d')
    print(f"📅 執行日期: {today_str}")
    
    # 執行任務
    for task_info in TASKS:
        if len(task_info) == 3:
            name, path, args = task_info
        else:
            name, path = task_info
            args = None
            
        run_script(name, path, args=args)
            
    print("\n🎉 早場工作執行完畢！")
    time.sleep(5)

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8')
    main()
