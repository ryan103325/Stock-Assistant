from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import time
import os
import csv
from datetime import datetime, timedelta
import requests
from io import StringIO 
import re 
import sys 
from dotenv import load_dotenv
load_dotenv()

# 族群整合模組 (位於 src/tools/tag_generator)
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tools", "tag_generator"))
from group_mapping import (
    get_stock_groups, 
    calculate_group_weights, 
    calculate_group_stock_changes,
    get_extended_group_mapping,
    find_unclassified_tags
)

# 圖片報告生成器
from report_generator_html import generate_fund_report_image

# ==========================================
# ⚙️ 設定區
# ==========================================
tg_token = os.getenv("TELEGRAM_TOKEN", "")
tg_chat_id = os.getenv("TELEGRAM_CHAT_ID", "")

# 檢查 Token
if "你的" in tg_token:
    CAN_SEND_TG = False
    print("⚠️ 未設定 Token，將僅執行存檔，不發送通知。")
else:
    CAN_SEND_TG = True

# 設定路徑
# 設定路徑
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # src/策略庫/00981a_基金 -> src/策略庫 -> src
# Correction: current file is in src/策略庫/00981a_基金
# dirname -> src/策略庫
# dirname -> src
# So 2 dirnames is correct if file is 2 levels deep from src?
# No. src/策略庫/00981a_基金/00981a.py.
# dirname(abspath) -> src/策略庫/00981a_基金
# dirname -> src/策略庫
# dirname -> src
# So 3 dirnames needed? No, wait.
# OLD: src/reports/00981a.py. 2 levels deep.
# NEW: src/策略庫/00981a_基金/00981a.py. 3 levels deep?
# Let's count slash: src/reports/file (2 dirs). src/策略庫/00981a_基金/file (3 dirs).
# So I need one more dirname.

SRC_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DATA_FOLDER = os.path.join(SRC_ROOT, "data_core", "history")
CACHE_FILE = os.path.join(SRC_ROOT, "cache", "market_matrix.pkl")
HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fund_holdings_history.csv")
TREND_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fund_trend_log.csv")
CONCEPT_HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fund_concept_history.csv")

# 使用全域路徑設定
trend_filename = TREND_LOG
holdings_filename = HISTORY_FILE
concept_filename = CONCEPT_HISTORY_FILE

# Optimization: Check if output already exists for today
if os.path.exists(trend_filename):
    try:
        df_check = pd.read_csv(trend_filename)
        if not df_check.empty:
            last_date = str(df_check.iloc[-1]['日期'])
            today_str = datetime.now().strftime('%Y-%m-%d')
            if last_date == today_str:
                print(f"✅ [00981a] 今日 ({today_str}) 已產生報告，跳過執行。")
                sys.exit(0)
    except Exception as e:
        print(f"⚠️ 檢查舊檔失敗: {e}")

# ==========================================
# 🧠 核心演算法
# ==========================================
def analyze_flow_impact(sub_payable, red_payable, net_assets, cash, sp_ratio):
    """
    輸入:
    - sub_payable: 申購應付款 (通常為負值，代表欠投資人憑證，但手上有現金)
    - red_payable: 贖回應付款 (通常為正值，代表欠投資人現金)
    - net_assets: 淨資產
    - cash: 手上現金
    - sp_ratio: 買賣動作 (負買正賣)
    """
    
    # 取絕對值以防萬一 (會計科目正負號有時不同)
    sub_val = abs(sub_payable)
    red_val = abs(red_payable)

    # 1. 計算比率
    # 申購率：新進來的錢佔淨資產多少？(超過 1% 通常就是大額)
    sub_ratio = (sub_val / net_assets) * 100
    
    # 贖回風險值：要付出去的錢佔現金多少？(超過 50% 很危險)
    # 如果現金是 0，設為無限大風險
    liquidity_risk = (red_val / cash * 100) if cash > 0 else 999 

    flow_signal = "NORMAL"
    flow_desc = "資金流向正常"

    # 2. 判斷邏輯
    # 【最優先】判斷贖回危機 (救命訊號)
    if liquidity_risk > 80:
        flow_signal = "CRISIS"
        flow_desc = "💀 流動性危機 (贖回 > 現金，被迫殺出)"
    elif liquidity_risk > 50:
        flow_signal = "WARNING"
        flow_desc = "⚠️ 贖回壓力大 (現金吃緊)"

    # 【次要】判斷申購動能 (如果有新錢進來)
    elif sub_ratio > 0.8: # 門檻可自行調整，通常 0.8%~1% 算顯著
        if sp_ratio < -0.2:
            flow_signal = "PARTY"
            flow_desc = "🚀 資金派對 (散戶湧入 + 經理人加碼)"
        elif sp_ratio > 0.5:
            flow_signal = "DUMP"
            flow_desc = "📉 趁機倒貨 (收到申購款卻在賣股)"
        else:
            flow_signal = "SUPPORT"
            flow_desc = "🐢 潛在買盤 (新資金待進場)"
            
    return flow_signal, flow_desc, sub_ratio

def get_comprehensive_alert(fund_data):
    """
    輸入 fund_data 字典，包含:
    net_assets, cash, settlement, stock_value, futures_nominal,
    sub_payable (申購), red_payable (贖回)
    """
    # 1. 解壓縮數據
    net = fund_data['net_assets']
    cash = fund_data['cash']
    settlement = fund_data['settlement']
    stock = fund_data['stock_value']
    futures = fund_data.get('futures_nominal', 0)
    sub_pay = fund_data.get('sub_payable', 0)
    red_pay = fund_data.get('red_payable', 0)

    if net == 0: return { "Final_Alert": "⚠️ 數據異常", "Total_Exposure": 0, "SP_Ratio": 0, "Flow_Desc": "N/A" }

    # 2. 計算關鍵指標
    total_exposure = ((stock + futures) / net) * 100  # 總曝險
    sp_ratio = (settlement / net) * 100               # 動作 (負買正賣)
    
    # 呼叫上面的流向分析
    flow_sig, flow_desc, sub_ratio = analyze_flow_impact(sub_pay, red_pay, net, cash, sp_ratio)

    # 3. 🛡️ 最終警示判定邏輯 (分層判斷)
    alert_survival = ""
    alert_momentum = ""
    alert_operation = ""
    
    # (A) 生存層級 (Survival)
    if flow_sig == "CRISIS":
        alert_survival = f"💀 {flow_desc}"
    elif flow_sig == "WARNING":
        alert_survival = f"⚠️ {flow_desc}"
        
    # (B) 動能層級 (Momentum)
    if flow_sig == "PARTY":
        alert_momentum = flow_desc  # flow_desc 已含 emoji
    elif flow_sig == "DUMP":
        alert_momentum = flow_desc
    elif flow_sig == "SUPPORT":
        alert_momentum = flow_desc
    else:
        # 如果沒有特殊動能，顯示 Normal 嗎？或是空？
        # User wants "Momentum and Operation levels to be listed".
        # If normal, maybe "➡️ 資金流向正常"
        if flow_sig == "NORMAL":
            alert_momentum = "➡️ 資金流向正常"

    # (C) 操作層級 (Operation)
    # 積極看多區
    if total_exposure > 100:
        alert_operation = "🔴 全力進攻 (槓桿/追價)"
    elif total_exposure > 92 and sp_ratio < -0.5:
        alert_operation = "🔴 強力買進 (高持股續買)"
    
    # 獲利了結區
    elif total_exposure > 90 and sp_ratio > 0.5:
        alert_operation = "🟠 高檔獲利了結 (見好就收)"
    
    # 抄底區
    elif total_exposure < 88 and sp_ratio < -0.5:
        alert_operation = "🟢 低檔佈局 (抄底/回補)"
        
    # 防禦區
    elif total_exposure < 82:
        alert_operation = "🔵 防禦避險 (現金為王)"
    elif total_exposure < 88 and sp_ratio > 0.5:
        alert_operation = "🔵 保守減碼 (看壞後市)"
        
    # 觀望區
    else:
        alert_operation = "⚪ 觀望/續抱 (盤整)"

    # 4. 決定最終標題 (Header) - 取最嚴重的
    if alert_survival:
        final_header = alert_survival
    elif "🚀" in alert_momentum or "📉" in alert_momentum:
        final_header = alert_momentum
    else:
        final_header = alert_operation

    # 4. 回傳完整分析包
    return {
        "Final_Alert": final_header,     # 標題
        "Survival": alert_survival,      # 生存層級
        "Momentum": alert_momentum,      # 動能層級
        "Operation": alert_operation,    # 操作層級
        "Total_Exposure": total_exposure,
        "SP_Ratio": sp_ratio,
        "Flow_Desc": flow_desc           
    }

# ==========================================
# 🧠 存檔函式
# ==========================================
def save_data_with_overwrite(file_path, new_df, date_col='日期', max_rows=50):
    target_date = str(new_df.iloc[0][date_col])
    final_df = new_df 

    if os.path.exists(file_path):
        try:
            old_df = pd.read_csv(file_path, dtype={date_col: str})
            if target_date in old_df[date_col].values:
                print(f"   ℹ️ 發現舊資料 ({target_date})，覆蓋更新...")
                old_df = old_df[old_df[date_col] != target_date]
                mode_msg = "覆蓋更新"
            else:
                print(f"   ℹ️ 新增資料 ({target_date})...")
                mode_msg = "新增資料"
            final_df = pd.concat([old_df, new_df], ignore_index=True)
        except Exception as e:
            print(f"⚠️ 讀檔失敗，重建檔案: {e}")
            final_df = new_df
            mode_msg = "重建檔案"
    else:
        mode_msg = "建立新檔"

    # 裁切至最近 max_rows 筆
    if max_rows and len(final_df) > max_rows:
        before_count = len(final_df)
        final_df = final_df.tail(max_rows).reset_index(drop=True)
        print(f"   ✂️ 資料裁切: {before_count} → {len(final_df)} 筆 (保留最近 {max_rows} 筆)")

    try:
        final_df.to_csv(file_path, index=False, encoding='utf-8-sig')
        return mode_msg
    except PermissionError:
        print("\n❌ 無法寫入檔案！請關閉 Excel！")
        return None

def send_telegram_message(message):
    if not CAN_SEND_TG: return
    try:
        url = f"https://api.telegram.org/bot{tg_token}/sendMessage"
        payload = {"chat_id": tg_chat_id, "text": message}
        resp = requests.post(url, json=payload)
        if resp.status_code == 200: print("✅ TG 發送成功")
        else: print(f"❌ TG 發送失敗: {resp.text}")
    except Exception as e: print(f"❌ TG 錯誤: {e}")

def send_telegram_photo(photo_path, caption=""):
    """Telegram 發送圖片"""
    if not CAN_SEND_TG: return
    try:
        url = f"https://api.telegram.org/bot{tg_token}/sendPhoto"
        with open(photo_path, 'rb') as photo:
            files = {'photo': photo}
            data = {'chat_id': tg_chat_id, 'caption': caption}
            resp = requests.post(url, files=files, data=data)
        if resp.status_code == 200: 
            print("✅ TG 圖片發送成功")
        else: 
            print(f"❌ TG 圖片發送失敗: {resp.text}")
    except Exception as e: 
        print(f"❌ TG 圖片錯誤: {e}")

def check_trading_day():
    """檢查今日是否為交易日 (FinMind TaiwanStockTradingDate)"""
    print("📅 [FinMind] 確認交易日中...")
    today_str = datetime.now().strftime('%Y-%m-%d')
    token = os.getenv("FINMIND_TOKEN", "")
    
    if not token:
        print("⚠️ 未設定 FINMIND_TOKEN，改用平日判斷")
        if datetime.now().weekday() >= 5:
            print(f"🛑 週末停止執行。")
            return False
        return True
    
    try:
        url = "https://api.finmindtrade.com/api/v4/data"
        params = {
            "dataset": "TaiwanStockTradingDate",
            "start_date": today_str,
            "end_date": today_str,
            "token": token
        }
        resp = requests.get(url, params=params, timeout=20)
        data = resp.json()
        dates = [d['date'] for d in data.get('data', [])]
        if today_str in dates:
            print(f"✅ 是交易日: {today_str}")
            return True
        else:
            print(f"💤 非交易日: {today_str}")
            return False
    except Exception as e:
        print(f"⚠️ API 查詢失敗: {e}")
        if datetime.now().weekday() >= 5:
            print(f"🛑 週末停止執行。")
            return False
        print("⚠️ 查無資料但為平日，強制執行。")
        return True

def get_taiex_change():
    """讀取大盤漲跌幅 (TAIEX.csv)"""
    print("📈 [Local] 讀取大盤變化 (TAIEX.csv)...")
    try:
        taiex_path = os.path.join(SRC_ROOT, "data_core", "TAIEX.csv")
        if os.path.exists(taiex_path):
            df = pd.read_csv(taiex_path)
            if len(df) >= 2:
                last = df.iloc[-1]
                prev = df.iloc[-2]
                pct_change = ((last['Close'] - prev['Close']) / prev['Close']) * 100
                print(f"✅ 大盤漲跌: {pct_change:.2f}% (Date: {last['Date']})")
                return pct_change
            else:
                print("⚠️ TAIEX.csv 資料不足兩筆")
        else:
            print("⚠️ 找不到 TAIEX.csv")
        return 0.0
    except Exception as e:
        print(f"⚠️ 大盤讀取錯誤: {e}")
        return 0.0

# ==========================================
# 🚀 主程式
# ==========================================

# 策略 1: 使用 FinMind 檢查交易日
today = datetime.now().strftime("%Y-%m-%d")
force_mode = "--force" in sys.argv

if not force_mode:
    if not check_trading_day():
        print("😴 非交易日，跳過執行。")
        sys.exit(0)
else:
    print("⚠️ [Force Mode] 強制執行，跳過交易日檢查。")

taiex_roi = get_taiex_change()

options = webdriver.ChromeOptions()
options.add_argument('--headless')
# Suppress logs
options.add_argument('--log-level=3')
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

try:
    print("🚀 啟動瀏覽器...")
    driver.maximize_window()
    url = "https://www.ezmoney.com.tw/ETF/Fund/Info?fundCode=49YTW"
    driver.get(url)

    wait = WebDriverWait(driver, 15)
    print("⏳ 前往頁面...")
    portfolio_btn = wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "基金投資組合")))
    portfolio_btn.click()
    time.sleep(3) 

    target_date = datetime.now().strftime('%Y-%m-%d')
    try:
        date_el = driver.find_element(By.XPATH, "//*[contains(text(), '資料日期')]")
        match = re.search(r'(\d{4}/\d{2}/\d{2})', date_el.text)
        if match: target_date = match.group(1).replace('/', '-')
        print(f"📅 資料日期: {target_date}")
    except: pass

    net_assets_value = 0
    try:
        nav_el = driver.find_element(By.XPATH, "//td[contains(text(),'淨資產')]/following-sibling::td")
        clean_nav = nav_el.text.replace('NTD', '').replace(',', '').strip()
        net_assets_value = float(clean_nav)
        print(f"💰 淨資產: {net_assets_value:,.0f}")
    except: print("⚠️ 無法抓取淨資產。")

    for i in range(3):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)

    print("📥 解析表格...")
    dfs = pd.read_html(StringIO(driver.page_source))
    summary_dfs = []
    holdings_df = None

    for index, df in enumerate(dfs):
        cols = str(df.columns)
        print(f"   🔍 Table {index} Columns: {cols}") # Debug Print
        
        if "項目" in cols and "權重" in cols:
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(-1)
            summary_dfs.append(df)
        elif ("股票名稱" in cols and "股數" in cols) or ("股票名稱" in cols and "權重" in cols):
            holdings_df = df.copy()
            if isinstance(holdings_df.columns, pd.MultiIndex): holdings_df.columns = holdings_df.columns.get_level_values(-1)
        elif len(df) > 20 and holdings_df is None:
            # Fallback: Assume the long table is the holdings table
            print("   ⚠️ 找不到標準欄位，嘗試使用「長表格」作為持股清單...")
            holdings_df = df.copy()
            if isinstance(holdings_df.columns, pd.MultiIndex): holdings_df.columns = holdings_df.columns.get_level_values(-1)

    # ---------------------------
    # 任務 A: 資金水位
    # ---------------------------
    if summary_dfs:
        try:
            summary_df = pd.concat(summary_dfs, ignore_index=True)
            col_item = [c for c in summary_df.columns if "項目" in str(c)][0]
            col_weight = [c for c in summary_df.columns if "權重" in str(c)][0]
            col_amt = [c for c in summary_df.columns if "金額" in str(c)][0]
            
            def clean_val(val):
                return float(str(val).replace('%','').replace('NTD','').replace(',','').strip() or 0)
            summary_df['clean_weight'] = summary_df[col_weight].apply(clean_val)
            summary_df['clean_amt'] = summary_df[col_amt].apply(clean_val)
            def get_data(keyword):
                rows = summary_df[summary_df[col_item].astype(str).str.contains(keyword, regex=False, na=False)]
                if not rows.empty: return rows.iloc[0]['clean_weight'], rows.iloc[0]['clean_amt']
                return 0.0, 0.0

            stock_pct, stock_amt = get_data("股票")
            cash_pct, cash_amt = get_data("現金")
            futures_pct, futures_amt = get_data("期貨(名目本金)")
            receivable_pct, receivable_amt = get_data("應收付證券款")
            # 原始 "申贖應付款" 金額
            raw_subs_amt = get_data("申贖應付款")[1] 
            raw_subs_pct = get_data("申贖應付款")[0]

            # 拆解 申購(負) 與 贖回(正)
            # 申購應付款 (通常為負值, 代表欠投資人憑證)
            sub_payable = raw_subs_amt if raw_subs_amt < 0 else 0
            # 贖回應付款 (通常為正值, 代表欠投資人現金)
            red_payable = raw_subs_amt if raw_subs_amt > 0 else 0

            fund_data = {
                'net_assets': net_assets_value if net_assets_value > 0 else (stock_amt / (stock_pct/100) if stock_pct > 0 else 0),
                'cash': cash_amt,
                'settlement': receivable_amt,
                'stock_value': stock_amt,
                'futures_nominal': futures_amt,
                'sub_payable': sub_payable,
                'red_payable': red_payable
            }

            # 使用新模組分析
            alert_data = get_comprehensive_alert(fund_data)
            
            final_header = alert_data['Final_Alert']
            alert_sur = alert_data['Survival']
            alert_mom = alert_data['Momentum']
            alert_op = alert_data['Operation']
            
            total_exp = alert_data['Total_Exposure']
            sp = alert_data['SP_Ratio']
            flow_desc = alert_data['Flow_Desc']

            msg_trend = f"📊 【資金水位】 ({target_date})\n"
            msg_trend += "-------------------------\n"
            msg_trend += f"🔔 **{final_header}**\n"
            
            # 顯示三層級資訊 (避免重複)
            if alert_sur:
                msg_trend += f"💀 風險 : {alert_sur}\n"
            
            # 只有當 header 不是動能訊號時才顯示流向
            if final_header != alert_mom:
                msg_trend += f"🌊 流向 : {alert_mom}\n"
            msg_trend += f"🎮 操作 : {alert_op}\n"
            
            msg_trend += "-------------------------\n"
            msg_trend += f"📈 股票 : {stock_pct:>6.2f} %\n"
            msg_trend += f"💵 現金 : {cash_pct:>6.2f} %\n"
            msg_trend += f"⚖️ 應收付 : {receivable_pct:>6.2f} %\n"
            msg_trend += f"💳 申贖款 : {raw_subs_pct:>6.2f} %\n"
            msg_trend += f"🎲 期貨 : {futures_pct:>6.2f} %\n"
            msg_trend += f"• 總曝險 : {total_exp:.2f} %\n"
            
            print(msg_trend)

            new_trend_data = {
                '日期': [target_date],
                '股票': [stock_pct],
                '現金': [cash_pct],
                '期貨': [futures_pct],
                '應收付': [receivable_pct],
                '申贖應付款': [raw_subs_pct],
                '淨資產': [fund_data['net_assets']],
                '總曝險': [total_exp],
                # 計算其他欄位以維持 CSV 格式
                '股票權重': [stock_pct], # 近似值
                '期貨影響': [futures_pct], # 近似值
                'SP值': [sp],
                'ECP值': [cash_pct + receivable_pct],
                '操作警示': [final_header],
                '動作訊號': [flow_desc], # 用 Flow Desc 取代舊 Action
                '姿態訊號': ["新制"],     # 標記
                '大盤漲跌': [taiex_roi]
            }
            new_trend_df = pd.DataFrame(new_trend_data)
            status = save_data_with_overwrite(trend_filename, new_trend_df, date_col='日期')
            
            if status:
                print(f"✅ 資金水位已{status}")
                # [圖片報告取代] send_telegram_message(msg_trend)

        except Exception as e: print(f"⚠️ 資金處理錯誤: {e}")

    # ---------------------------
    # 任務 B: 持股明細 (含股票代號)
    # ---------------------------
    if holdings_df is not None:
        try:
            col_name = [c for c in holdings_df.columns if "股票名稱" in str(c)][0]
            col_shares = [c for c in holdings_df.columns if "股數" in str(c)][0]
            col_weight = [c for c in holdings_df.columns if "持股權重" in str(c) or "比例" in str(c)][0]
            col_id = [c for c in holdings_df.columns if "股票代號" in str(c)][0]
            
            holdings_df = holdings_df.dropna(subset=[col_name]).head(60)
            output_df = holdings_df[[col_id, col_name, col_shares, col_weight]].copy()
            output_df.columns = ['股票代號', '股票名稱', '股數', '持股權重']
            output_df.insert(0, '日期', target_date)
            
            status = save_data_with_overwrite(holdings_filename, output_df, date_col='日期')
            
            if status:
                print(f"📋 持股明細已{status}")
                
                history_df = pd.read_csv(holdings_filename).dropna(subset=['日期'])
                all_dates = sorted(history_df['日期'].unique())
                if len(all_dates) >= 2:
                    date_new, date_old = all_dates[-1], all_dates[-2]
                    df_new = history_df[history_df['日期'] == date_new]
                    df_old = history_df[history_df['日期'] == date_old]

                    # 🌟 建立代號對照表 (新舊資料合併查表)
                    id_map = pd.concat([
                        df_new[['股票名稱', '股票代號']], 
                        df_old[['股票名稱', '股票代號']]
                    ]).drop_duplicates().set_index('股票名稱')['股票代號'].to_dict()

                    def clean(x): 
                        try: return float(str(x).replace(',', ''))
                        except: return 0
                    d_new = dict(zip(df_new['股票名稱'], df_new['股數'].apply(clean)))
                    d_old = dict(zip(df_old['股票名稱'], df_old['股數'].apply(clean)))
                    
                    new_in = set(d_new.keys()) - set(d_old.keys())
                    msg1 = f"🆕 【新進榜】\n"
                    if new_in:
                        for n in new_in: 
                            sid = id_map.get(n, "")
                            # 顯示格式: 名稱(代號)
                            msg1 += f"✨ {n}({sid}) | {int(d_new[n]/1000):,} 張\n"
                    else: msg1 += "無。\n"
                    
                    changes = []
                    # 建立新舊權重對照表
                    weight_map_new = {}
                    weight_map_old = {}
                    
                    for _, row in df_new.iterrows():
                        try:
                            wt = float(str(row['持股權重']).replace('%', '').replace(',', ''))
                        except:
                            wt = 0
                        weight_map_new[row['股票名稱']] = wt
                    
                    for _, row in df_old.iterrows():
                        try:
                            wt = float(str(row['持股權重']).replace('%', '').replace(',', ''))
                        except:
                            wt = 0
                        weight_map_old[row['股票名稱']] = wt
                    
                    # 讀取收盤價函數
                    def get_close_price(stock_code):
                        """從 history 目錄讀取收盤價"""
                        try:
                            price_file = os.path.join(DATA_FOLDER, f'{stock_code}.csv')
                            if os.path.exists(price_file):
                                price_df = pd.read_csv(price_file)
                                if not price_df.empty and 'Close' in price_df.columns:
                                    return float(price_df.iloc[-1]['Close'])
                        except:
                            pass
                        return 0
                    
                    for n in set(d_new.keys()) | set(d_old.keys()):
                        diff = d_new.get(n, 0) - d_old.get(n, 0)
                        if diff != 0:
                            wt_new = weight_map_new.get(n, 0)
                            wt_old = weight_map_old.get(n, 0)
                            wt_change = wt_new - wt_old
                            # 金額 = 收盤價 × 股數差異
                            stock_code = id_map.get(n, '')
                            close_price = get_close_price(stock_code)
                            amount = abs(close_price * diff)
                            changes.append({
                                'name': n,
                                'code': stock_code,
                                'diff': diff,
                                'weight': wt_new,
                                'weight_change': wt_change,
                                'amount': amount
                            })
                    
                    # 按權重變化排序（絕對值）
                    changes.sort(key=lambda x: abs(x['weight_change']), reverse=True)
                    
                    # 分離增持和減持
                    increases = [c for c in changes if c['diff'] > 0]
                    decreases = [c for c in changes if c['diff'] < 0]
                    
                    # 計算連續天數 (用 history_map)
                    def get_streak(name, direction='buy'):
                        """計算連續買進/賣出天數"""
                        if len(all_dates) < 3:
                            return 0
                        streak = 0
                        sorted_d = sorted(all_dates)
                        
                        # 建立該股票的歷史資料
                        stock_history = {}
                        for _, row in history_df[history_df['股票名稱'] == name].iterrows():
                            try:
                                sh = float(str(row['股數']).replace(',', ''))
                            except:
                                sh = 0
                            stock_history[row['日期']] = sh
                        
                        check_val = stock_history.get(sorted_d[-1], 0)
                        for i in range(len(sorted_d)-2, -1, -1):
                            prev_val = stock_history.get(sorted_d[i], 0)
                            if direction == 'buy':
                                if check_val > prev_val and prev_val > 0:
                                    streak += 1
                                    check_val = prev_val
                                else:
                                    break
                            else:  # sell
                                if check_val < prev_val:
                                    streak += 1
                                    check_val = prev_val
                                else:
                                    break
                        return streak + 1 if streak > 0 else 0
                    
                    msg2 = "━━━━━━━━━━━━━━\n"
                    msg2 += "🔥【變動排行】\n"
                    msg2 += "━━━━━━━━━━━━━━\n\n"
                    
                    # 增持 TOP 5
                    msg2 += "📈 增持 TOP 5\n"
                    for item in increases[:5]:
                        n, sid = item['name'], item['code']
                        diff, wt = item['diff'], item['weight']
                        streak = get_streak(n, 'buy')
                        streak_txt = f" | 連續加碼 {streak} 天 🔥" if streak >= 2 else ""
                        large_txt = " 🔥" if abs(diff) > 3000000 else ""  # 3000張
                        msg2 += f"🔴 {n} ({sid}): +{int(diff/1000):,} 張 | 權重 {wt:.2f}%{streak_txt}{large_txt}\n"
                    
                    msg2 += "\n📉 減持 TOP 3\n"
                    for item in decreases[:3]:
                        n, sid = item['name'], item['code']
                        diff, wt = item['diff'], item['weight']
                        streak = get_streak(n, 'sell')
                        streak_txt = f" | 連續減碼 {streak} 天 ⚠️" if streak >= 3 else ""
                        msg2 += f"🟢 {n} ({sid}): {int(diff/1000):,} 張 | 權重 {wt:.2f}%{streak_txt}\n"

                    # [圖片報告取代] send_telegram_message(msg1)
                    time.sleep(1)
                    # [圖片報告取代] send_telegram_message(msg2)
                else: print("⚠️ 無法比對 (首筆資料)。")

                # 🌟 [新增功能] 連續買進偵測 (Streak Detection)
                if len(all_dates) >= 3:
                    try:
                        print(f"🔎 啟動連續買進偵測 (歷史資料共 {len(all_dates)} 天)...")
                        
                        # 重建快速查詢表 {name: {date: shares}}
                        history_map = {} 
                        # 只取最近 30 天資料以免過慢 (雖然應該不會)
                        recent_dates = all_dates[-30:]
                        # 轉成 List 以便 Index 回溯 (all_dates 已是 sort ver)
                        sorted_dates = sorted(list(recent_dates)) # 明確排序 (雖然 unique 後應該已排)
                        
                        # 篩選這些日期的 rows
                        sub_df = history_df[history_df['日期'].isin(sorted_dates)]
                        
                        for _, row in sub_df.iterrows():
                            nm = row['股票名稱']
                            dt = row['日期']
                            sh = 0
                            try: sh = float(str(row['股數']).replace(',', ''))
                            except: pass
                            
                            if nm not in history_map: history_map[nm] = {}
                            history_map[nm][dt] = sh
                            
                        # 開始分析 (針對今日有持股的)
                        streak_list = []
                        latest_date = sorted_dates[-1]
                        
                        for name in d_new.keys(): # d_new 是今天有持股的
                            shares_now = d_new.get(name, 0)
                            
                            current_streak = 0
                            # 回溯檢查
                            # dates: [T-N, ..., T-2, T-1, T]
                            # index: -1 is T, -2 is T-1
                            
                            # 至少要有 T-1 (index -2) 才能算 streak=1? 
                            # 不，定義：
                            # T > T-1 (連買 1 天? 不，這叫買超 1 天)
                            # T > T-1 > T-2 (連買 2 天? 還是 3 天?)
                            # 題目：連續三天買入 => T, T-1, T-2 呈現遞增
                            # Streak 定義為「連續增長次數」 + 1 ? 或者「連續增長的天數」
                            # 若 T > T-1，streak=2 (包含今天與昨天)
                            # 若 T > T-1 > T-2，streak=3
                            
                            check_val = shares_now
                            streak = 0 # 初始為 0，計算「增長次數」
                            
                            for i in range(len(sorted_dates)-2, -1, -1):
                                d_prev = sorted_dates[i]
                                shares_prev = history_map.get(name, {}).get(d_prev, 0)
                                
                                # 嚴格遞增
                                if check_val > shares_prev and shares_prev > 0:
                                    streak += 1
                                    check_val = shares_prev
                                else:
                                    break
                            
                            # streak 現在代表「連續增長次數」
                            # 最終顯示應該是 streak + 1（包含今天）
                            # 例如：T > T-1 > T-2 => streak=2，實際連買 3 天
                            actual_days = streak + 1
                            
                            if actual_days >= 3:
                                # 計算本日增加量 (for display)
                                prev_day_shares = history_map.get(name, {}).get(sorted_dates[-2], 0)
                                diff = shares_now - prev_day_shares
                                streak_list.append({
                                    'name': name,
                                    'code': id_map.get(name, ""),
                                    'streak': actual_days,  # 使用實際天數
                                    'diff': diff
                                })
                        
                        if streak_list:
                            # 排序: 天數多 > 增加張數多
                            streak_list.sort(key=lambda x: (x['streak'], x['diff']), reverse=True)
                            
                            msg3 = "🚀 【連續加碼警示】\n"
                            for item in streak_list:
                                msg3 += f"🚀 {item['name']}({item['code']}) | +{int(item['diff']/1000):,}張 (連買 {item['streak']} 天)\n"
                                
                            print("✅ 發送連續買進通知...")
                            # [圖片報告取代] send_telegram_message(msg3)
                        else:
                            print("ℹ️ 無連續 3 天買進標的。")

                    except Exception as e:
                        print(f"⚠️ 連續買進偵測錯誤: {e}")

                # ==========================================
                # 🎪 任務 C: 概念股配置分析
                # ==========================================
                try:
                    print("🎪 啟動概念股配置分析...")
                    
                    # 計算今日各族群權重
                    group_weights_today = calculate_group_weights(df_new, code_col='股票代號', weight_col='持股權重')
                    
                    # 載入昨日族群權重 (從歷史檔)
                    group_weights_yesterday = {}
                    if os.path.exists(concept_filename):
                        try:
                            concept_df = pd.read_csv(concept_filename)
                            yesterday_concept = concept_df[concept_df['日期'] == date_old]
                            for _, row in yesterday_concept.iterrows():
                                group_weights_yesterday[row['族群']] = row['權重']
                        except Exception as e:
                            print(f"⚠️ 讀取族群歷史失敗: {e}")
                    
                    # 計算變化量
                    group_changes = {}
                    all_groups = set(group_weights_today.keys()) | set(group_weights_yesterday.keys())
                    for g in all_groups:
                        today_w = group_weights_today.get(g, 0)
                        yesterday_w = group_weights_yesterday.get(g, 0)
                        change = today_w - yesterday_w
                        group_changes[g] = (today_w, change)
                    
                    # 儲存今日族群權重
                    concept_records = []
                    for g, (w, c) in group_changes.items():
                        concept_records.append({
                            '日期': target_date,
                            '族群': g,
                            '權重': round(w, 2),
                            '變化': round(c, 2)
                        })
                    if concept_records:
                        new_concept_df = pd.DataFrame(concept_records)
                        save_data_with_overwrite(concept_filename, new_concept_df, date_col='日期')
                        print(f"✅ 族群權重已儲存")
                    
                    # 計算各族群內的個股變化
                    group_stock_changes = calculate_group_stock_changes(
                        df_new, df_old,
                        code_col='股票代號', name_col='股票名稱', shares_col='股數'
                    )
                    
                    # 排序取 TOP 3 增持和 TOP 3 減持
                    sorted_groups = sorted(group_changes.items(), key=lambda x: x[1][1], reverse=True)
                    top_increases = [(g, w, c) for g, (w, c) in sorted_groups if c > 0][:3]
                    top_decreases = [(g, w, c) for g, (w, c) in sorted_groups if c < 0][-3:][::-1]  # 取最後3個反轉
                    top_decreases = sorted([(g, w, c) for g, (w, c) in sorted_groups if c < 0], key=lambda x: x[2])[:3]
                    
                    msg4 = "━━━━━━━━━━━━━━\n"
                    msg4 += "🎪【概念股配置】\n"
                    msg4 += "━━━━━━━━━━━━━━\n\n"
                    
                    # 增持 TOP 3
                    msg4 += "📈 增持 TOP 3\n"
                    for g, w, c in top_increases:
                        arrow = "↑" if c > 0.1 else "→"
                        msg4 += f"🔴 {g}：{w:.1f}% ({arrow} {abs(c):.1f}%)\n"
                        # 列出該族群主要加碼個股 (最多3檔)
                        if g in group_stock_changes:
                            top_stocks = [s for s in group_stock_changes[g] if s[2] > 0][:3]
                            if top_stocks:
                                stock_txt = "、".join([f"{s[0]} +{int(s[2]/1000):,}張" for s in top_stocks])
                                msg4 += f"   • 主要加碼：{stock_txt}\n"
                        msg4 += "\n"
                    
                    # 減持 TOP 3
                    msg4 += "📉 減持 TOP 3\n"
                    for g, w, c in top_decreases:
                        arrow = "↓" if c < -0.1 else "→"
                        msg4 += f"🟢 {g}：{w:.1f}% ({arrow} {abs(c):.1f}%)\n"
                        # 列出該族群主要減碼個股 (最多3檔)
                        if g in group_stock_changes:
                            top_stocks = [s for s in group_stock_changes[g] if s[2] < 0][:3]
                            if top_stocks:
                                stock_txt = "、".join([f"{s[0]} {int(s[2]/1000):,}張" for s in top_stocks])
                                msg4 += f"   • 主要減碼：{stock_txt}\n"
                        msg4 += "\n"
                    
                    if top_increases or top_decreases:
                        # [圖片報告取代] send_telegram_message(msg4)
                        print("✅ 概念股配置已整合到圖片報告")
                    
                    # ==========================================
                    # 🚨 任務 D: 異常偵測警示
                    # ==========================================
                    alerts = []
                    
                    # 1. 族群單日變動 > 1% → 題材熱度異常
                    for g, (w, c) in group_changes.items():
                        if c > 1.0:
                            # 找出最大推手
                            if g in group_stock_changes:
                                top_stock = group_stock_changes[g][0] if group_stock_changes[g] else None
                                if top_stock:
                                    alerts.append(f"🔥 題材熱度異常\n⚠️ {g}族群單日暴增 {c:.1f}%\n   → {top_stock[0]} +{int(top_stock[2]/1000):,}張 為最大推手")
                        elif c < -1.0:
                            alerts.append(f"❄️ 題材降溫警訊\n⚠️ {g}族群單日減少 {abs(c):.1f}%")
                    
                    # 2. 現金水位 > 6% → 防禦訊號
                    if cash_pct > 6.0:
                        alerts.append(f"🛡️ 防禦訊號\n⚠️ 現金水位偏高 ({cash_pct:.1f}%)")
                    
                    # 3. 申贖款連續為負檢測 (需要歷史資料)
                    if raw_subs_pct < 0:
                        alerts.append(f"⚠️ 資金流出訊號\n   申贖款為負 ({raw_subs_pct:.2f}%)，贖回 > 申購")
                    
                    if alerts:
                        # [圖片報告取代] 異常警示已整合到圖片報告
                        print("ℹ️ 異常警示已整合到圖片報告")
                    else:
                        print("ℹ️ 無異常警示")
                    
                except Exception as e:
                    print(f"⚠️ 概念股配置分析錯誤: {e}")

        except Exception as e:
            print(f"⚠️ 持股明細處理錯誤: {e}")

    # ==========================================
    # 🖼️ 任務 E: 生成圖片報告並發送
    # ==========================================
    try:
        print("🖼️ 正在生成圖片報告...")
        
        # 預設變數初始化（防止前面區塊因異常跳過導致變數未定義）
        if 'increases' not in dir(): increases = []
        if 'decreases' not in dir(): decreases = []
        if 'streak_list' not in dir(): streak_list = []
        if 'new_in' not in dir(): new_in = set()
        if 'd_new' not in dir(): d_new = {}
        if 'id_map' not in dir(): id_map = {}
        if 'top_increases' not in dir(): top_increases = []
        if 'top_decreases' not in dir(): top_decreases = []
        if 'group_stock_changes' not in dir(): group_stock_changes = {}
        
        # 生成 AI 總結
        ai_summary = ""
        if 'increases' in dir() and increases:
            buy_names = [x['name'] for x in increases[:2]]
            ai_summary = f"經理人今日重點加碼{'、'.join(buy_names)}"
            if 'total_exp' in dir():
                if total_exp > 95:
                    ai_summary += "，總曝險維持高檔，態度積極。"
                elif total_exp < 85:
                    ai_summary += "，總曝險偏低，操作偏保守。"
                else:
                    ai_summary += "。"
        elif 'decreases' in dir() and decreases:
            sell_names = [x['name'] for x in decreases[:2]]
            ai_summary = f"經理人今日主要減碼{'、'.join(sell_names)}，操作偏向調節。"
        else:
            ai_summary = "經理人今日操作變動不大，多空互見。"
        
        # 收集報告資料
        report_data = {
            'date': target_date,
            'water_level': {
                'final_alert': final_header if 'final_header' in dir() else '資金流向正常',
                'operation': alert_op if 'alert_op' in dir() else '',
                'stock_pct': stock_pct if 'stock_pct' in dir() else 0,
                'cash_pct': cash_pct if 'cash_pct' in dir() else 0,
                'receivable_pct': receivable_pct if 'receivable_pct' in dir() else 0,
                'subs_pct': raw_subs_pct if 'raw_subs_pct' in dir() else 0,
                'futures_pct': futures_pct if 'futures_pct' in dir() else 0,
                'total_exposure': total_exp if 'total_exp' in dir() else 0
            },
            'new_entries': [],
            'changes': {
                'increases': [],
                'decreases': []
            },
            'streak_alerts': [],
            'concept': {
                'increases': [],
                'decreases': [],
                'group_stock_changes': {}
            },
            'ai_summary': ai_summary
        }
        
        # 填入新進榜 (如果有)
        if 'new_in' in dir() and new_in and 'd_new' in dir() and 'id_map' in dir():
            report_data['new_entries'] = [
                {'name': n, 'code': id_map.get(n, ''), 'shares': d_new.get(n, 0)}
                for n in new_in
            ]
        
        # 填入變動資料 (如果有) - 以權重變化排序
        if 'increases' in dir() and increases:
            report_data['changes']['increases'] = increases[:5]
        if 'decreases' in dir() and decreases:
            report_data['changes']['decreases'] = decreases[:3]
        
        # 填入連續加碼 (如果有)
        if 'streak_list' in dir() and streak_list:
            report_data['streak_alerts'] = streak_list
        
        # 填入概念股 (如果有)
        if 'top_increases' in dir() and top_increases:
            report_data['concept']['increases'] = top_increases
        if 'top_decreases' in dir() and top_decreases:
            report_data['concept']['decreases'] = top_decreases
        if 'group_stock_changes' in dir() and group_stock_changes:
            report_data['concept']['group_stock_changes'] = group_stock_changes
        
        # 生成圖片
        image_path = generate_fund_report_image(report_data)
        
        # 發送圖片
        send_telegram_photo(image_path, f"00981A 經理人日報 - {target_date}")
        
        # 發送後刪除圖片 (節省空間)
        try:
            os.remove(image_path)
            print(f"🗑️ 已刪除暫存圖片: {image_path}")
        except:
            pass
        
    except Exception as e:
        print(f"⚠️ 圖片報告生成錯誤: {e}")
        # Fallback: 發送原本的文字訊息
        if 'msg_trend' in dir():
            send_telegram_message(msg_trend)

except Exception as e: print(f"❌ 錯誤: {e}")
finally:
    try: driver.quit()
    except: pass