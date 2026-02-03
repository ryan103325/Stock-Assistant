
import os
import subprocess
import sys
import datetime

# ==========================================
# 📅 季度更新腳本
# ==========================================
# 功能: 執行 MoneyDJ 概念股與細產業爬蟲
# 建議頻率: 每 3 個月執行一次 (或手動執行)
# ==========================================

def run_script(script_name):
    print(f"\n==================================================")
    print(f"🚀 Running {os.path.basename(script_name)}...")
    print(f"==================================================")
    try:
        cmd = [sys.executable, script_name]
        subprocess.run(cmd, check=True)
        print(f"✅ {os.path.basename(script_name)} 完成。")
        return True
    except subprocess.CalledProcessError:
        print(f"❌ {os.path.basename(script_name)} 失敗。")
        return False
    except Exception as e:
        print(f"❌ 錯誤: {e}")
        return False

def main():
    print("🗓️ 啟動季度資料更新 (Concept & Industry Scheduler)...")
    print(f"📅 執行日期: {datetime.datetime.now().strftime('%Y-%m-%d')}")
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    # tools/ is inside src/
    # If this script is in src/, tools is in tools/
    tools_dir = os.path.join(base_dir, "tools")
    
    # 1. MoneyDJ 概念股
    script_concepts = os.path.join(tools_dir, "fetch_moneydj_concepts.py")
    if os.path.exists(script_concepts):
        run_script(script_concepts)
    else:
        print(f"⚠️ 找不到 {script_concepts}")

    # 2. MoneyDJ 細產業
    script_industries = os.path.join(tools_dir, "fetch_moneydj_industries.py")
    if os.path.exists(script_industries):
        run_script(script_industries)
    else:
        print(f"⚠️ 找不到 {script_industries}")
        
    print("\n🎉 季度更新完成！")

if __name__ == "__main__":
    main()
