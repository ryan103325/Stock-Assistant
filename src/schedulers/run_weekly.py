import subprocess
import os
import sys
import time

# 設定路徑
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(CURRENT_DIR))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")

# 🗓️ 週維護任務 (每週六執行)
# 目的: 更新股票標籤系統
TASKS = [
    ("CMoney 標籤爬蟲", os.path.join(SRC_DIR, "tools", "crawlers", "fetch_cmoney_tags.py")),
    ("MoneyDJ 標籤爬蟲", os.path.join(SRC_DIR, "tools", "crawlers", "fetch_moneydj_tags.py")),
    ("生成主標籤", os.path.join(SRC_DIR, "tools", "tag_generator", "generate_master_tags.py")),
]

def run_script(name, path, force=False):
    print(f"\n🚀 正在執行: {name} ({os.path.basename(path)})...")
    try:
        if not os.path.exists(path):
            print(f"❌ 找不到檔案: {path}")
            return
            
        cmd = [sys.executable, path]
        if force:
            cmd.append("--force")
            
        result = subprocess.run(cmd, check=False)
        if result.returncode == 0:
            print(f"✅ {name} 完成。")
        else:
            print(f"❌ {name} 失敗 (Exit Code: {result.returncode})")
    except Exception as e:
        print(f"❌ 執行錯誤: {e}")

def main(force=False):
    print("==========================================")
    print("      🗓️ 週維護排程 (每週六)")
    print("      目的: 更新股票標籤系統")
    print("==========================================")
    
    for name, path in TASKS:
        run_script(name, path, force=force)
            
    print("\n🎉 週維護工作執行完畢！")
    time.sleep(5)

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8')
    force_mode = "--force" in sys.argv
    main(force=force_mode)
