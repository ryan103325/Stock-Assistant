import subprocess
import os
import sys
import time
from datetime import datetime

# 設定路徑
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(CURRENT_DIR))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")

# 📅 季度維護任務
# 目的: 更新季度財務資料 (EPS/ROE)
TASKS_QUARTERLY = [
    ("季度資料更新 (EPS/ROE)", os.path.join(SRC_DIR, "tools", "data_pipeline", "update_quarterly.py")),
]

def run_script(name, path):
    print(f"\n🚀 正在執行: {name} ({os.path.basename(path)})...")
    if not os.path.exists(path):
        print(f"❌ 找不到檔案: {path}")
        return
        
    try:
        result = subprocess.run([sys.executable, path], check=False)
        if result.returncode == 0:
            print(f"✅ {name} 完成。")
        else:
            print(f"❌ {name} 失敗 (Exit Code: {result.returncode})")
    except Exception as e:
        print(f"❌ 執行錯誤: {e}")

def main():
    print("==========================================")
    print("      📅 季度維護排程")
    print("      (此流程不檢查交易日,強制執行)")
    print("==========================================")
    
    # 檢查季度
    now = datetime.now()
    if now.month in [1, 4, 7, 10]:
        print(f"\n[季度檢查] 當月為季度更新月 ({now.month}月)")
        for name, path in TASKS_QUARTERLY:
            run_script(name, path)
    else:
        print(f"\n[季度檢查] 非季度更新月 ({now.month}月),跳過 EPS/ROE 更新。")
        print("季度更新月份: 1月, 4月, 7月, 10月")
        
    print("\n🎉 維護工作執行完畢！")
    time.sleep(5)

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8')
    main()
