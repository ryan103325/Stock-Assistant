import subprocess
import os
import sys
import time
import requests
from datetime import datetime

# 設定路徑
# 設定路徑
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(CURRENT_DIR))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")

# 定義任務清單
# 1. 每日更新任務 (有交易日才做)
DAILY_TASKS = [
    ("資料更新", os.path.join(SRC_DIR, "core", "Pipeline_data.py")),
    # ("資料庫清理", os.path.join(SRC_DIR, "tools", "clean_db.py")), # 已整合至 Pipeline，移除
    ("計算指標", os.path.join(SRC_DIR, "core", "optimize_matrix.py")),
    ("策略報告", os.path.join(SRC_DIR, "reports", "00981a.py")),
    ("RSI 底背離篩選", os.path.join(SRC_DIR, "core", "RSI_screener.py")),
    ("資金流向 & 族群快篩", os.path.join(SRC_DIR, "core", "Flow_screener.py")),
]

# 2. 常駐或固定任務 (無論是否交易日都可執行)
ALWAYS_TASKS = [
    ("啟動Bot", os.path.join(SRC_DIR, "vis", "技術分析圖.py")) # 獨立視窗
]

def check_is_trading_day():
    """ 檢查今日是否為交易日 (透過 FinMind API) """
    print("📅 確認今日是否為交易日...")
    try:
        today_str = datetime.now().strftime('%Y-%m-%d')
        img_url = "https://api.finmindtrade.com/api/v4/data"
        params = {
            "dataset": "TaiwanStockPrice",
            "data_id": "TAIEX",
            "start_date": today_str,
            "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNS0xMi0xNiAxMzo0MTo1NSIsInVzZXJfaWQiOiJyeWFuOTAxMjIzIiwiaXAiOiIzOS4xNS40MC4xODcifQ.LS0WippJM4l5AOG6k8nIltzwcfXTSrGola56jMSMggU" # Public Token
        }
        res = requests.get(img_url, params=params, timeout=5)
        if res.status_code == 200:
            data = res.json().get('data', [])
            if data and data[-1]['date'] == today_str:
                print(f"✅ 今日 ({today_str}) 為交易日，小秘書努力工作中...")
                return True
    except:
        pass
    
    # 若 API 失敗或無資料，假設為非交易日 (保守)
    # 但若是週五週六？這裡主要擋掉「完全無資料」的日子
    # User 邏輯：有資料 -> 做；沒資料 -> 取消
    print("💤 今日無市場資料 (非交易日或尚未收盤)，每日更新行程取消。")
    return False

def run_script(name, path):
    print(f"\n🚀 正在執行: {name} ({os.path.basename(path)})...")
    try:
        # 特殊處理: 如果是Bot，開啟新視窗獨立執行 (避免卡住主流程)
        if "Bot" in name or "技術分析圖" in path:
            print(f"⚠️ 這是常駐程式，將開啟新視窗執行...")
            # 使用 cmd /k 讓視窗在程式結束(或崩潰)後保留，方便查看錯誤日誌
            # 直接調用 cmd.exe，避免 shell=True 的 start 語法問題
            subprocess.Popen(
                ["cmd", "/k", sys.executable, path], 
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
            print(f"✅ {name} 已在背景啟動。")
            return

        # 一般腳本: 等待執行完畢
        result = subprocess.run([sys.executable, path], check=False)
        if result.returncode == 0:
            print(f"✅ {name} 完成。")
        else:
            print(f"❌ {name} 失敗 (Exit Code: {result.returncode})")
    except Exception as e:
        print(f"❌ 執行錯誤: {e}")

def main():
    print("==========================================")
    print("      🛠️ 手動執行每日全套流程")
    print("==========================================")
    
    # 1. 判斷交易日
    is_trading_day = check_is_trading_day()
    
    # 2. 執行每日任務 (若為交易日)
    if is_trading_day:
        for name, path in DAILY_TASKS:
            if os.path.exists(path):
                run_script(name, path)
            else:
                print(f"⚠️ 找不到檔案: {path}")
    else:
        print("⏸️ 跳過每日資料更新與分析流程。")

    # 3. 執行常駐任務 (Bot)
    # User 提到「有些程式碼是要在一周結束執行的」，Bot 算是隨時可用的工具
    print("\n------------------------------------------")
    print("🤖 準備啟動常駐工具...")
    for name, path in ALWAYS_TASKS:
        if os.path.exists(path):
            run_script(name, path)
        else:
            print(f"⚠️ 找不到檔案: {path}")
            
    print("\n🎉 所有工作執行完畢！(視窗將在 10 秒後關閉)")
    time.sleep(10)

if __name__ == "__main__":
    # 強制 UTF-8 輸出
    sys.stdout.reconfigure(encoding='utf-8')
    main()
