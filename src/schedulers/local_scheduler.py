import schedule
import time
import subprocess
import sys
import os
from datetime import datetime

# 設定路徑 (使用相對路徑確保移動後仍有效)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__)) # src/runners
PROJECT_ROOT = os.path.dirname(os.path.dirname(CURRENT_DIR)) # Root

# 定義執行檔路徑
SCRIPT_DAY = os.path.join(CURRENT_DIR, "run_day.py")
SCRIPT_NIGHT = os.path.join(CURRENT_DIR, "run_night.py")
SCRIPT_WEEKLY = os.path.join(PROJECT_ROOT, "src", "reports", "00981aW.py")

def run_task(name, script_path):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n⏰ [{now}] 啟動任務: {name}")
    print(f"   檔案: {script_path}")
    
    if not os.path.exists(script_path):
        print(f"❌ 找不到檔案: {script_path}")
        return

    try:
        # 使用 subprocess.run 執行，並繼承環境變數 (.env)
        result = subprocess.run([sys.executable, script_path], check=False)
        if result.returncode == 0:
            print(f"✅ {name} 執行完成。")
        else:
            print(f"⚠️ {name} 執行結束 (Exit Code: {result.returncode})")
    except Exception as e:
        print(f"❌ 執行發生錯誤: {e}")

def job_day():
    run_task("🌞 下午場 (每日更新 & 篩選)", SCRIPT_DAY)

def job_night():
    run_task("🌙 晚場 (籌碼報告)", SCRIPT_NIGHT)

def job_weekly():
    run_task("📊 週策略報告 (00981aW)", SCRIPT_WEEKLY)

def main():
    print("=================================================")
    print("🚀 TG助手 本地排程系統 (Local Scheduler)")
    print(f"📂 專案根目錄: {PROJECT_ROOT}")
    print("=================================================")
    print("排程設定:")
    print("   🌞 每日 14:35 -> run_day.py")
    print("   🌙 每日 18:05 -> run_night.py")
    print("   📊 週五 18:30 -> 00981aW.py")
    print("=================================================")
    print("正在等待任務... (按 Ctrl+C 停止)")

    # 設定時間表 (依照用戶習慣)
    schedule.every().day.at("14:35").do(job_day)
    schedule.every().day.at("18:05").do(job_night)
    schedule.every().friday.at("18:30").do(job_weekly)

    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    # 強制 stdout 使用 utf-8 避免中文亂碼
    sys.stdout.reconfigure(encoding='utf-8')
    main()
