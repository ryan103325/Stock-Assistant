import subprocess
import os
import sys
import time
import requests
import asyncio
import json
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
load_dotenv()

# 設定路徑
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(CURRENT_DIR))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
CACHE_DIR = os.path.join(PROJECT_ROOT, "logs")

# 加入 src 路徑以便 import 共用模組
sys.path.insert(0, SRC_DIR)
from utils.trading_day_utils import (
    is_trading_day as check_is_trading_day,
    is_yesterday_trading_day as check_yesterday_is_trading_day,
    is_last_trading_day_of_week,
)

# 確保 cache 目錄存在
os.makedirs(CACHE_DIR, exist_ok=True)

# 🌆 每日統一排程 (晚上 19:00 執行)
# 步驟 1-2: 順序執行
SEQUENTIAL_TASKS = [
    ("資料更新 (價量)", os.path.join(SRC_DIR, "tools", "data_pipeline", "Pipeline_data.py")),
    ("計算指標", os.path.join(SRC_DIR, "tools", "data_pipeline", "optimize_matrix.py")),
]

# 步驟 3-5: 並行執行 (訊息順序: 3, 4, 5)
PARALLEL_TASKS = [
    (3, "RSI 底背離篩選", os.path.join(SRC_DIR, "strategies", "RSI", "RSI_screener.py")),
    (4, "族群資金動能", os.path.join(SRC_DIR, "strategies", "Local_Hot", "run_unified_momentum.py")),
    (5, "籌碼策略報告 (00981A)", os.path.join(SRC_DIR, "strategies", "00981A", "00981a.py")),
]

# 步驟 7: 情緒分析反思 (靜默執行,不包含在訊息中)
# 使用 module_mode=True 以支援 relative import
REFLECTION_TASK = (0, "情緒分析反思", "src.alpha_core.main", ["reflect"], True)

# 步驟 8: Bot (僅本地執行)
BOT_TASK = ("啟動 Telegram Bot", os.path.join(SRC_DIR, "charts", "technical_analysis_chart.py"))

# 交易日判斷已移至 utils.trading_day_utils

def run_script_sync(task_info, force=False):
    """同步執行單一腳本並返回結果"""
    module_mode = False
    if len(task_info) == 5:
        order, name, path, args, module_mode = task_info
    elif len(task_info) == 4:
        order, name, path, args = task_info
    elif len(task_info) == 3:
        order, name, path = task_info
        args = None
    else:
        name, path = task_info
        order = 0
        args = None
    
    print(f"\n🚀 正在執行: {name}...")
    
    result = {
        "order": order,
        "name": name,
        "success": False,
        "message": "",
        "output": ""
    }
    
    try:
        if module_mode:
            cmd = [sys.executable, "-m", path]
        else:
            if not os.path.exists(path):
                result["message"] = f"找不到檔案: {path}"
                print(f"❌ {result['message']}")
                return result
            cmd = [sys.executable, path]
        if args:
            cmd.extend(args)
        if force:
            cmd.append("--force")
            
        process = subprocess.run(cmd, check=False, capture_output=True, text=True, encoding='utf-8', cwd=PROJECT_ROOT)
        
        result["output"] = process.stdout
        
        if process.returncode == 0:
            result["success"] = True
            result["message"] = "完成"
            print(f"✅ {name} 完成。")
        else:
            result["message"] = f"失敗 (Exit Code: {process.returncode})"
            print(f"❌ {name} {result['message']}")
            if process.stderr:
                print(f"   錯誤: {process.stderr[:200]}")
            elif process.stdout:
                # 若無 stderr 但有 stdout，顯示最後 500 字以便除錯
                print(f"   錯誤 (Stdout): {process.stdout[-500:]}")
                
    except Exception as e:
        result["message"] = f"執行錯誤: {str(e)}"
        print(f"❌ {result['message']}")
    
    return result

def save_result_to_cache(result):
    """將結果保存到快取"""
    cache_file = os.path.join(CACHE_DIR, f"task_{result['order']}_{datetime.now().strftime('%Y%m%d')}.json")
    try:
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ 無法保存快取: {e}")

def send_telegram_message(message):
    """發送 Telegram 訊息"""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if not bot_token or not chat_id:
        print("⚠️ 未設定 Telegram Bot Token 或 Chat ID,跳過訊息發送")
        return False
    
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }
        response = requests.post(url, json=data, timeout=10)
        if response.status_code == 200:
            print("✅ Telegram 訊息發送成功")
            return True
        else:
            print(f"❌ Telegram 訊息發送失敗: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Telegram 訊息發送錯誤: {e}")
        return False

def format_results_message(results):
    """格式化結果訊息"""
    today = datetime.now().strftime('%Y-%m-%d %H:%M')
    message = f"<b>📊 每日分析報告</b>\n{today}\n\n"
    
    success_count = sum(1 for r in results if r['success'])
    total_count = len(results)
    
    message += f"<b>執行狀態: {success_count}/{total_count} 成功</b>\n\n"
    
    # 按照指定順序排序 (3, 4, 6, 5, 7)
    for result in results:
        icon = "✅" if result['success'] else "❌"
        message += f"{icon} {result['name']}: {result['message']}\n"
    
    return message

def main(force=False):
    print("==========================================")
    print("      🌆 每日統一排程 (晚上 19:00)")
    print("==========================================")
    
    # 1. 全域交易日檢查
    if not check_is_trading_day(force=force):
        print("⏸️ 非交易日,略過每日流程。")
        time.sleep(5)
        return

    # 2. 偵測是否為 GitHub Actions 環境
    is_github_actions = os.getenv("GITHUB_ACTIONS") == "true"
    # is_friday 已被 is_last_trading_day_of_week() 取代
    
    all_results = []
    
    # 3. 執行順序任務 (步驟 1-2) — GitHub 上由 data_sync 處理，跳過
    if is_github_actions:
        print("\n" + "="*50)
        print("☁️ GitHub Actions: 跳過資料更新/指標計算 (data_sync 已執行)")
        print("="*50)
    else:
        print("\n" + "="*50)
        print("階段 1: 順序執行 (資料更新 → 指標計算)")
        print("="*50)
        
        for task in SEQUENTIAL_TASKS:
            result = run_script_sync(task, force=force)
            if not result['success']:
                print(f"\n❌ 關鍵任務失敗: {result['name']}")
                print("⏸️ 中止後續流程")
                return
    
    # 4. 並行執行任務 (步驟 3-6)
    print("\n" + "="*50)
    print("階段 2: 並行執行 (策略篩選 + 報告)")
    print("="*50)
    
    parallel_results = []
    
    tasks_to_run = PARALLEL_TASKS.copy()
    
    # 使用 ThreadPoolExecutor 並行執行
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(run_script_sync, task, force): task for task in tasks_to_run}
        
        for future in as_completed(futures):
            result = future.result()
            parallel_results.append(result)
            save_result_to_cache(result)
    
    # 按照指定順序排序結果 (3, 4, 5)
    parallel_results.sort(key=lambda x: x['order'])
    all_results.extend(parallel_results)
    
    # 週報已移至 step_strategies_00981A.yml 中執行（跟隨日報之後）
    
    # 5. [已停用] 發送整合訊息 (各策略已各自發送圖片報告)
    # print("\n" + "="*50)
    # print("階段 3: 發送整合報告")
    # print("="*50)
    
    # if all_results:
    #     message = format_results_message(all_results)
    #     send_telegram_message(message)
    
    # 6. 情緒分析反思 — 已移至獨立 workflow (step_news_reflect.yml, 16:00)
    # 本地端仍可手動執行: python -m src.alpha_core.main reflect
    
    # 7. 啟動 Bot (僅本地環境)
    if not is_github_actions:
        print("\n" + "="*50)
        print("階段 5: 啟動 Telegram Bot (本地)")
        print("="*50)
        
        name, path = BOT_TASK
        print(f"\n🚀 正在執行: {name} ({os.path.basename(path)})...")
        print(f"⚠️ 這是常駐程式,將開啟新視窗執行...")
        subprocess.Popen(
            ["cmd", "/k", sys.executable, path], 
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
        print(f"✅ {name} 已在背景啟動。")
    else:
        print("\n☁️ GitHub Actions 環境,跳過 Bot 啟動")
            
    print("\n🎉 每日工作執行完畢！")
    if not is_github_actions:
        print("(視窗將在 10 秒後關閉)")
        time.sleep(10)

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8')
    force_mode = "--force" in sys.argv
    main(force=force_mode)
