# === 全自動台股資料庫：嚴格交易日判斷版 (非交易日/資料未出 直接關閉) ===

import os
import sys
import time
import requests
import pandas as pd
from datetime import datetime, timedelta
from io import StringIO
from dotenv import load_dotenv
load_dotenv()

# ================= 設定區 =================
# ★★★ 你的 FinMind Token (多組輪替) ★★★
# ★★★ 你的 FinMind Token (多組輪替) ★★★
API_KEYS = [
    os.getenv("FINMIND_TOKEN", "")
]

# 資料庫路徑
# 資料庫路徑
SRC_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_FOLDER = os.path.join(SRC_ROOT, "data_core", "history")
META_FOLDER = os.path.join(SRC_ROOT, "data_core", "market_meta")

# 下載天數
HISTORY_DAYS = 2000 

# ================= 核心工具函數 =================

def ensure_folder_exists():
    if not os.path.exists(DATA_FOLDER):
        os.makedirs(DATA_FOLDER)
    if not os.path.exists(META_FOLDER):
        os.makedirs(META_FOLDER)
    print(f"📁 資料庫: {DATA_FOLDER}")
    print(f"📁 Metadata: {META_FOLDER}")

def safe_request(url, parameter):
    """ 具備重試機制的請求 (指數退避) """
    retry_count = 0
    wait_time = 30 # 初始等待
    
    while retry_count < 8: # 增加重試次數
        try:
            resp = requests.get(url, params=parameter, timeout=20)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 402 or resp.status_code == 429:
                print(f"⚠️ 觸發限制 ({resp.status_code})，第 {retry_count+1} 次重試，休息 {wait_time} 秒...")
                time.sleep(wait_time)
                
                # 指數退避: 30 -> 60 -> 120 -> 240
                wait_time *= 2
                retry_count += 1
            else:
                time.sleep(3)
                retry_count += 1
        except:
            time.sleep(3)
            retry_count += 1
    return None

def check_if_today_is_trading_day():
    """
    ★ 關鍵判斷：檢查「今天」是否有交易資料
    邏輯：直接問 FinMind 拿「今天」的大盤資料。
    - 如果拿得到 -> 代表今天是交易日且資料已更新 -> 允許執行。
    - 如果拿不到 -> 代表今天是假日，或還沒收盤 -> 禁止執行。
    """
    today_str = datetime.now().strftime('%Y-%m-%d')
    print(f"📅 系統日期：{today_str}")
    print("🔍 正在檢查今日是否為「有效交易日」且「資料已產出」...")
    
    url = "https://api.finmindtrade.com/api/v4/data"
    parameter = {
        "dataset": "TaiwanStockPrice",
        "data_id": "TAIEX",
        "start_date": today_str, # 只抓今天
        "token": API_KEYS[0] # 使用第一組 Key 檢查即可
    }
    
    data = safe_request(url, parameter)
    
    # 判斷回傳內容
    if data and "data" in data and len(data["data"]) > 0:
        # 雙重確認：回傳的日期必須真的是今天
        market_date = data["data"][-1]["date"]
        if market_date == today_str:
            print(f"✅ 確認成功！今日 ({today_str}) 是交易日，且資料已更新。")
            return True
    
    print(f"💤 檢查結果：今日 ({today_str}) 無交易資料。")
    print("   原因可能是：1. 週末/假日  2. 尚未收盤(資料未產出)")
    print("⛔ 程式將自動停止，不執行下載。")
    return False

# ================= 第一部分：爬蟲抓清單 (免Token) =================

def get_stock_list_universal():
    """ 暴力掃描 HiStock 網頁，抓取普通股清單 (排除下市/停牌股票) """
    print("\n📡 正在連接 HiStock 抓取最新股票清單...")
    # 使用包含開高低收欄位的頁面
    url = "https://histock.tw/stock/rank.aspx?m=2&d=1&p=all"
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        response = requests.get(url, headers=headers)
        response.encoding = 'utf-8'
        
        if response.status_code != 200:
            print(f"❌ 連線失敗: {response.status_code}")
            return []

        html_content = StringIO(response.text)
        dfs = pd.read_html(html_content)
        
        target_df = None
        for df in dfs:
            cols = [str(c) for c in df.columns]
            condition_a = any("代號" in c for c in cols) and any("名稱" in c for c in cols)
            
            if not condition_a and len(df) > 0:
                row0 = [str(v) for v in df.iloc[0].values]
                if any("代號" in r for r in row0):
                    df.columns = df.iloc[0]
                    df = df[1:]
                    condition_a = True
            
            if condition_a:
                target_df = df
                break
        
        if target_df is None:
            return []

        # 標準化欄位名稱
        clean_cols = []
        for c in target_df.columns:
            c_str = str(c)
            if "代號" in c_str: clean_cols.append("代號")
            elif "名稱" in c_str: clean_cols.append("名稱")
            elif "價格" in c_str: clean_cols.append("收盤")
            elif "成交值" in c_str or "成交額" in c_str: clean_cols.append("成交值")
            elif "周漲跌" in c_str or "週漲跌" in c_str: clean_cols.append("週漲跌")
            elif "開盤" in c_str: clean_cols.append("開盤")
            elif "最高" in c_str: clean_cols.append("最高")
            elif "最低" in c_str: clean_cols.append("最低")
            else: clean_cols.append(c_str)
        target_df.columns = clean_cols

        raw_codes = target_df['代號'].astype(str).tolist()
        valid_list = []
        filtered_count = 0
        suspicious_codes = []  # 振幅=0 且成交值=0 的可疑股票
        
        for idx, code in enumerate(raw_codes):
            code = code.strip()
            # 基本格式檢查：4位數字、不以0開頭
            if len(code) == 4 and not code.startswith('0') and code.isdigit():
                try:
                    row = target_df.iloc[idx]
                    
                    # 過濾 DR 股和甲特股 (名稱欄位)
                    stock_name = ""
                    if "名稱" in target_df.columns:
                        stock_name = str(row["名稱"])
                    if "DR" in stock_name or "甲特" in stock_name:
                        filtered_count += 1
                        continue
                    
                    # 取得成交值
                    trade_val = 0
                    if "成交值" in target_df.columns:
                        val_str = str(row["成交值"]).replace(",", "").replace("-", "0")
                        try:
                            trade_val = float(val_str) if val_str else 0
                        except:
                            trade_val = 0
                    
                    # 取得振幅
                    amplitude = 0
                    if "振幅" in target_df.columns:
                        amp_str = str(row["振幅"]).replace("%", "").replace(",", "").replace("-", "0")
                        try:
                            amplitude = float(amp_str) if amp_str else 0
                        except:
                            amplitude = 0
                    
                    # 振幅=0 且 成交值=0 → 需要用 FinMind 驗證
                    if trade_val == 0 and amplitude == 0:
                        suspicious_codes.append(code)
                    else:
                        valid_list.append(code)
                except:
                    valid_list.append(code)
        
        # 使用 FinMind 驗證可疑股票
        if suspicious_codes:
            print(f"🔍 發現 {len(suspicious_codes)} 檔可疑股票，正在用 FinMind 驗證...")
            token = os.getenv("FINMIND_TOKEN", "")
            today = datetime.now()
            start_date = (today - timedelta(days=30)).strftime('%Y-%m-%d')
            
            for code in suspicious_codes:
                try:
                    params = {
                        "dataset": "TaiwanStockPrice",
                        "data_id": code,
                        "start_date": start_date,
                        "token": token
                    }
                    resp = requests.get("https://api.finmindtrade.com/api/v4/data", params=params, timeout=10)
                    
                    if resp.status_code == 200:
                        data = resp.json().get('data', [])
                        if data:
                            # 取得最後交易日
                            last_trade_date = data[-1]['date']
                            last_dt = datetime.strptime(last_trade_date, '%Y-%m-%d')
                            days_since = (today - last_dt).days
                            
                            if days_since <= 10:
                                # 最近有交易，保留
                                valid_list.append(code)
                            else:
                                # 超過 10 天沒交易，視為下市
                                filtered_count += 1
                        else:
                            # FinMind 無資料，視為下市
                            filtered_count += 1
                    else:
                        # API 錯誤，保守起見保留
                        valid_list.append(code)
                    
                    time.sleep(0.5)  # 限速
                except:
                    valid_list.append(code)
            
            print(f"   ✅ 驗證完成")
        
        valid_list = sorted(list(set(valid_list)))
        print(f"✅ 成功取得清單！共 {len(valid_list)} 檔普通股 (已過濾 {filtered_count} 檔)")
        return valid_list

    except Exception as e:
        print(f"❌ 爬蟲發生錯誤: {e}")
        return []


# ================= 第二部分：FinMind 下載器 =================

# ================= 第二部分：FinMind 下載器 (多執行緒並行版) =================

def update_stock_single(stock_id, token):
    """ 單一股票更新 (輔助函式) """
    file_path = os.path.join(DATA_FOLDER, f"{stock_id}.csv")
    today_str = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=HISTORY_DAYS)).strftime('%Y-%m-%d')
    query_start_date = start_date

    # 1. 檢查是否需要更新
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                if len(lines) > 1:
                    last_line = lines[-1].strip()
                    last_date = last_line.split(',')[0]
                    if last_date == today_str: return False # 已是最新
                    if len(last_date) == 10: query_start_date = last_date
        except: pass

    # 2. 下載資料
    url = "https://api.finmindtrade.com/api/v4/data"
    parameter = {
        "dataset": "TaiwanStockPrice",
        "data_id": stock_id,
        "start_date": query_start_date,
        "token": token
    }
    
    data = safe_request(url, parameter)
    if data and "data" in data and len(data["data"]) > 0:
        df_new = pd.DataFrame(data["data"])
        df_new = df_new[['date', 'open', 'max', 'min', 'close', 'Trading_Volume']]
        df_new.columns = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
        
        # Calculate Amount immediately
        df_new['Amount'] = df_new['Close'] * df_new['Volume']
        
        # Merge
        if os.path.exists(file_path):
            try:
                df_old = pd.read_csv(file_path)
                df_final = pd.concat([df_old, df_new]).drop_duplicates(subset=['Date'], keep='last')
            except: df_final = df_new
        else:
            df_final = df_new
            
        df_final.to_csv(file_path, index=False, float_format='%.2f')
        return True
    return False

def orchestrate_update(missing_stocks):
    """ 
    單執行緒 + Token 輪替下載器 
    (解決 402 Rate Limit 問題) 
    """
    total = len(missing_stocks)
    num_keys = len(API_KEYS)
    print(f"\n🚀 啟動 FinMind 安全補漏機制")
    print(f"🔥 待補股票: {total} 檔 | 可用 Token: {num_keys} 組")
    print(f"⚡ 策略: 單執行緒輪替 Token (Round-Robin) + 安全間隔")

    updated_count = 0
    
    for i, stock_id in enumerate(missing_stocks):
        # 輪替使用 Token
        token = API_KEYS[i % num_keys]
        
        # 顯示進度
        print(f"[{i+1}/{total}] 檢查 {stock_id} (Token: ...{token[-4:]})...", end="\r")
        
        try:
            is_updated = update_stock_single(stock_id, token)
            if is_updated:
                updated_count += 1
                sys.stdout.write(f"[{i+1}/{total}] {stock_id} ✅ 更新成功      \n")
                # 成功後休息久一點 (2秒)
                time.sleep(2.0)
            else:
                # 沒資料更新，稍微休息即可 (1秒)
                time.sleep(1.0)
                
        except Exception as e:
            print(f"❌ {stock_id} 失敗: {e}")
            time.sleep(1.0)
            
    print(f"\n🎉 補漏完成！共更新 {updated_count} 檔。")

# ================= 主程式 =================
# ================= 第三部分：官方雙刀流下載器 (TWSE + TPEx) =================

def update_daily_official(valid_whitelist=None, force=False):
    """
    使用官方來源抓取「當日」所有股票行情
    1. TWSE (OpenAPI) -> 上市
    2. TPEx (Web JSON) -> 上櫃
    
    優點：只需 2 次請求即可更新全市場，避開 FinMind IP 限制。
    """
    print("\n🚀 啟動「官方雙刀流」更新模式 (TWSE + TPEx)")
    
    today_ad = datetime.now().strftime('%Y-%m-%d') # 2024-12-24
    
    # --- 1. 抓取 TWSE 上市資料 ---
    print("📡 1. 連線至證交所 (TWSE)...")
    twse_data = []
    try:
        url_twse = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
        requests.packages.urllib3.disable_warnings()
        r = requests.get(url_twse, verify=False, timeout=30)
        if r.status_code == 200:
            twse_data = r.json()
            print(f"   ✅ 取得上市資料: {len(twse_data)} 筆")
        else:
            print(f"   ❌ TWSE 下載失敗: {r.status_code}")
    except Exception as e:
        print(f"   ❌ TWSE 連線錯誤 (Skip): {e}")

    # --- 2. 抓取 TPEx 上櫃資料 (Official Open API) ---
    print("📡 2. 連線至櫃買中心 (TPEx Open API)...")
    tpex_data = []
    try:
        # User 指定的 TPEx Open API 入口: https://www.tpex.org.tw/openapi/
        # 實際資料 Endpoint: tpex_mainboard_daily_close_quotes
        url_tpex = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Accept': 'application/json'
        }
        # 關閉 SSL 驗證以防憑證問題
        r = requests.get(url_tpex, headers=headers, verify=False, timeout=20)
        
        if r.status_code == 200:
            tpex_data = r.json()
            print(f"   ✅ 取得上櫃資料: {len(tpex_data)} 筆 (來源: TPEx Open API)")
        else:
            print(f"   ❌ TPEx 下載失敗: {r.status_code}")
    except Exception as e:
        print(f"   ❌ TPEx 連線錯誤 (Skip): {e}")

    # --- 3. 整合與寫入 ---
    # --- 3. 整合與寫入 ---
    if not twse_data and not tpex_data:
        print("❌ 官方來源皆無資料，切換回 FinMind 模式...")
        return False
        
    # [Patch] 檢查資料日期是否為今日
    # 隨機抽樣檢查 TWSE 第一筆有效資料
    sample_date = ""
    if twse_data:
        try:
            d_str = twse_data[0]['Date'] # 1131226
            y = int(d_str[:3]) + 1911
            m = d_str[3:5]
            d = d_str[5:7]
            sample_date = f"{y}-{m}-{d}"
        except: pass
        
    if sample_date and sample_date != today_ad:
        if force:
            print(f"⚠️ [Force Mode] 官方資料日期 ({sample_date}) 與今日不符，但強制採納！")
        else:
            print(f"⚠️ 官方資料過期！(TWSE: {sample_date}, Today: {today_ad})")
            print("🔄 放棄官方資料，強制切換回 FinMind 補漏模式 (較慢但準確)...")
            return False

    print("💾 正在整合並寫入本地資料庫...")
    updated_count = 0
    
    # 建立要更新的資料表 (Code -> DataDict)
    # 格式統一轉為: Date, Open, High, Low, Close, Volume
    
    # 處理 TWSE
    # API: Code, Name, TradeVolume, TradeValue, OpeningPrice, HighestPrice, LowestPrice, ClosingPrice
    for row in twse_data:
        try:
            code = row['Code']
            # ★ 篩選：4碼且首位非0 (排除 ETF/權證)
            if len(code) != 4 or code.startswith('0'):
                continue

            # [Optimization] Whitelist Check
            if valid_whitelist is not None and code not in valid_whitelist:
                continue

            # 日期轉西元 (TWSE 給的是民國 1131224)
            d_str = row['Date'] # 1131224
            y = int(d_str[:3]) + 1911
            m = d_str[3:5]
            d = d_str[5:7]
            date_ad = f"{y}-{m}-{d}"
            
            # 數值處理 (去除逗號)
            vol = float(row['TradeVolume'].replace(',', ''))
            op = float(row['OpeningPrice'].replace(',', ''))
            hi = float(row['HighestPrice'].replace(',', ''))
            lo = float(row['LowestPrice'].replace(',', ''))
            cl = float(row['ClosingPrice'].replace(',', ''))
            
            # Calculate Amount
            amount = cl * vol
            
            # 存擋
            save_to_csv(code, date_ad, op, hi, lo, cl, vol, amount)
            updated_count += 1
        except:
            pass
            
    # 處理 TPEx (Open API)
    # JSON Keys: Date, SecuritiesCompanyCode, Close, Open, High, Low, TradingShares
    for row in tpex_data:
        try:
            code = row['SecuritiesCompanyCode']
            
            # ★ 篩選：4碼且首位非0 (排除 ETF/權證)
            if len(code) != 4 or code.startswith('0'):
                continue

            # [Optimization] Whitelist Check
            if valid_whitelist is not None and code not in valid_whitelist:
                continue

            # 日期轉西元 (TPEx Open API 給的是民國 1141224)
            d_str = row['Date']
            y = int(d_str[:3]) + 1911
            m = d_str[3:5]
            d = d_str[5:7]
            date_ad = f"{y}-{m}-{d}"
            
            cl = float(row['Close'])
            op = float(row['Open'])
            hi = float(row['High'])
            lo = float(row['Low'])
            vol = float(row['TradingShares']) # 已經是股數
            
            # 排除無交易 (---)
            if str(cl) == '---' or  str(op) == '---': continue

            # Calculate Amount
            amount = cl * vol

            save_to_csv(code, date_ad, op, hi, lo, cl, vol, amount)
            updated_count += 1
        except:
            pass

    print(f"✅ 官方資料更新完成！共處理 {updated_count} 檔。")
    
    # 建立已更新清單 (Set)
    updated_codes = set()
    for row in twse_data:
        updated_codes.add(row.get('Code', '').strip())
    for row in tpex_data:
        updated_codes.add(row.get('SecuritiesCompanyCode', '').strip())
        
    return updated_codes

def save_to_csv(code, date_str, op, hi, lo, cl, vol, amount=None):
    """ 將單筆資料 Append 到 CSV """
    file_path = os.path.join(DATA_FOLDER, f"{code}.csv")
    
    # 計算 Amount 如果未提供
    if amount is None:
        try:
            amount = float(cl) * float(vol)
        except:
            amount = 0.0

    # 如果檔案不存在，自動建立並寫入 Header
    if not os.path.exists(file_path):
        print(f"🆕 發現新股票: {code}，建立檔案中...")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("Date,Open,High,Low,Close,Volume,Amount\n")

    # 讀取最後一行檢查日期和資料重複
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            if len(lines) > 1:
                last_line = lines[-1].strip()
                parts = last_line.split(',')
                last_date = parts[0]
                if last_date == date_str:
                    return "SKIPPED"  # 日期完全相同，跳過
                # 防止假資料：如果 OHLCV 與最後一行完全一致（非交易日重複），也跳過
                if len(parts) >= 6:
                    try:
                        last_ohlcv = (float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4]), float(parts[5]))
                        new_ohlcv = (float(op), float(hi), float(lo), float(cl), float(vol))
                        if last_ohlcv == new_ohlcv:
                            return "SKIPPED"  # OHLCV 完全一致 = 非交易日假資料
                    except:
                        pass
    except:
        pass

    # Append 寫入
    # 格式: Date, Open, High, Low, Close, Volume, Amount
    new_line = f"{date_str},{op},{hi},{lo},{cl},{vol},{amount:.2f}\n"
    try:
        with open(file_path, 'a', encoding='utf-8') as f:
            f.write(new_line)
            f.flush()
            os.fsync(f.fileno())
        if code == "2330": print("   [DEBUG] 2330 Written & Flushed.")
        return True
    except Exception as e:
        print(f"❌ Write Error {code}: {e}")
        return False

def update_from_histock(already_updated_codes, valid_whitelist=None):
    """
    從 HiStock 抓取全市場行情 (作為第二道防線)
    valid_whitelist: 僅允許更新的股票代號集合 (Strict Filter)
    """
    print("\n📡 2. 連線至 HiStock (通用備援機制)...")
    url = "https://histock.tw/stock/rank.aspx?p=all"
    
    updated_count = 0
    new_updated_codes = set()
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }
        r = requests.get(url, headers=headers, timeout=30)
        r.encoding = 'utf-8' # HiStock is usually UTF-8
        
        if r.status_code != 200:
            print(f"   ❌ HiStock 連線失敗: {r.status_code}")
            return new_updated_codes

        # Parse HTML Table
        dfs = pd.read_html(StringIO(r.text))
        target_df = None
        for df in dfs:
            # Check cols
            cols = [str(c) for c in df.columns]
            if any("代號" in c for c in cols) and any("價格" in c for c in cols):
                target_df = df
                break
        
        if target_df is None:
            print("   ❌ 解析失敗: 找不到目標表格")
            return new_updated_codes

        # Debug: Print columns
        # print(f"   Table Columns: {target_df.columns.tolist()}")

        # Clean columns: remove spaces, newlines, and sort arrows
        clean_cols = []
        for c in target_df.columns:
            clean_cols.append(str(c).strip().replace(" ", "").replace("\n", "").replace("▼", ""))
        target_df.columns = clean_cols
        
        # Verify '代號' exists exactly
        if '代號' not in target_df.columns:
            # Try to find which column is code
            # usually col 0
            if '代號' in str(target_df.columns[0]):
                target_df.rename(columns={target_df.columns[0]: '代號'}, inplace=True)
            else:
                print(f"   ❌ 找不到 '代號' 欄位. Columns: {target_df.columns}")
                return new_updated_codes

        today_ad = datetime.now().strftime('%Y-%m-%d')
        
        processed_df = target_df[target_df['代號'].astype(str).str.len() == 4] # Filter broadly first
        
        print(f"   🔍 HiStock 抓到 {len(processed_df)} 筆資料，正在篩選與寫入...")

        for idx, row in processed_df.iterrows():
            try:
                code_raw = str(row['代號']).strip()
                # 嚴格篩選
                if len(code_raw) != 4 or code_raw.startswith('0') or not code_raw.isdigit():
                    continue
                
                # [Optimization] Whitelist Check
                if valid_whitelist is not None:
                    if code_raw not in valid_whitelist:
                        continue
                
                # Check if already updated by Official (Set check is fast)
                if code_raw in already_updated_codes:
                    continue

                # Extract Data
                # Note: HiStock uses '-' for no data?
                def parse_val(v):
                    s = str(v).replace(',', '').strip()
                    if s == '--' or s == '': return None
                    try: return float(s)
                    except: return None
                
                # Column names might differ slightly (e.g. '價格' vs '成交')
                # Strict Mapping based on User Screenshot:
                # [代號, 名稱, 價格, 漲跌, 漲跌幅, 周漲跌, 振幅, 開盤, 最高, 最低, 昨收, 成交量, 成交值(億)]
                # We need: 價格(Close), 開盤(Open), 最高(High), 最低(Low), 成交量(Volume), 成交值(億)(Amount)
                
                # Check exact keys from screenshot (after cleaning '▼')
                cl = parse_val(row.get('價格')) or parse_val(row.get('成交'))
                op = parse_val(row.get('開盤')) or cl
                hi = parse_val(row.get('最高')) or cl
                lo = parse_val(row.get('最低')) or cl
                vol_lots = parse_val(row.get('成交量'))
                amount_億 = parse_val(row.get('成交值(億)'))
                
                if cl is None: continue
                if op is None: op = cl
                if hi is None: hi = cl
                if lo is None: lo = cl
                if vol_lots is None: vol_lots = 0
                
                vol_shares = int(vol_lots * 1000)
                
                # 優先使用 HiStock 的成交值(億),如果沒有才用計算方式
                if amount_億 is not None and amount_億 > 0:
                    amount = float(amount_億) * 100000000  # 億轉換為元
                else:
                    amount = float(cl) * vol_shares  # 備用計算方式
                
                # Save
                if code_raw == "2330":
                    print(f"[DEBUG] Processing 2330: Price={cl}, Vol={vol_shares}, Amt={amount}, Date={today_ad}")
                
                status_save = save_to_csv(code_raw, today_ad, op, hi, lo, cl, vol_shares, amount)
                
                if status_save is False: 
                    # Error occurred
                    continue
                
                new_updated_codes.add(code_raw)
                
                if status_save == "SKIPPED":
                    # Skipped due to up-to-date, but track it as processed
                    continue
                    
                if code_raw == "2330":
                    print(f"[DEBUG] 2330 Save Status: {status_save}")

                updated_count += 1
                new_updated_codes.add(code_raw)
                
            except Exception as inner_e:
                print(f"Row Error {code_raw}: {inner_e}")
                continue

        print(f"   ✅ HiStock 更新完成！共補足 {updated_count} 檔。")
        
    except Exception as e:
        print(f"   ❌ HiStock 執行錯誤: {e}")
        
    return new_updated_codes

# ================= 主程式 =================
if __name__ == "__main__":
    # 強制將輸出編碼設為 utf-8 (解決 Windows Emoji 報錯)
    sys.stdout.reconfigure(encoding='utf-8')

    ensure_folder_exists()

    # Optimization: Check success marker
    SUCCESS_MARKER = os.path.join(DATA_FOLDER, ".update_success")
    if os.path.exists(SUCCESS_MARKER):
        mtime = datetime.fromtimestamp(os.path.getmtime(SUCCESS_MARKER))
        if mtime.date() == datetime.now().date():
             print(f"✅ [Pipeline] 今日 ({mtime.date()}) 資料已更新完成，跳過執行。")
             sys.exit(0)

    today_ad = datetime.now().strftime('%Y-%m-%d')
    print(f"✅ 今日日期: {today_ad}")

    # 1. 取得目標股票清單 (HiStock)
    histock_list = get_stock_list_universal()
    
    # [Consistency Fix] Filter by MoneyDJ List
    dj_codes = set()
    dj_file = os.path.join(META_FOLDER, "moneydj_industries.csv")
    if os.path.exists(dj_file):
        try:
            with open(dj_file, 'r', encoding='utf-8-sig') as f:
                lines = f.readlines()
                start_idx = 0
                if lines and "Code" in lines[0] and "Name" in lines[0]: start_idx=1
                for line in lines[start_idx:]:
                    p = line.split(',')
                    if len(p)>=1: 
                        c=p[0].strip()
                        if c: dj_codes.add(c)
            print(f"📋 MoneyDJ 清單限制: {len(dj_codes)} 檔")
            
            # Intersection
            all_stocks = sorted(list(set(histock_list) & dj_codes))
            print(f"⚠️ 過濾後目標股票: {len(all_stocks)} 檔 (原 {len(histock_list)} 檔)")
        except Exception as e:
            print(f"❌ 讀取 MoneyDJ 清單錯誤: {e}, 使用全部清單")
            all_stocks = histock_list
    else:
        print("⚠️ 無 MoneyDJ 清單，使用 HiStock 全部股票")
        all_stocks = histock_list

    print(f"📋 最終更新目標: {len(all_stocks)} 檔")

    today_str = datetime.now().strftime('%Y-%m-%d')
    print(f"📅 執行日期: {today_str}")

    # 2. ★ 優先：HiStock (User Request Preferred Source)
    print("\n🚀 啟動 Step 1: HiStock 爬蟲 (優先來源)...")
    # strict_whitelist = all_stocks (only these are allowed)
    updated_codes = update_from_histock(set(), valid_whitelist=set(all_stocks))
    
    # 3. ★ 次要：官方雙刀流 (TWSE + TPEx)
    print("\n🚀 啟動 Step 2: 官方雙刀流 (TWSE+TPEx) (補足 HiStock 缺漏)...")
    # Official function returns False if completely failed, or a set if succeeded
    force_mode = "--force" in sys.argv
    official_res = update_daily_official(valid_whitelist=set(all_stocks), force=force_mode)
    
    if official_res is not False:
        updated_codes.update(official_res)
    else:
        print("⚠️ 官方來源無任何資料 (可能為非交易日或API異常)。")

    # 4. ★ 最後防線：FinMind 補漏
    # 計算剩下沒更新的
    missing_stocks = []
    for stock in all_stocks:
        if stock not in updated_codes:
            missing_stocks.append(stock)
    
    if len(missing_stocks) > 0:
        print(f"\n⚠️ 發現 {len(missing_stocks)} 檔股票尚未更新，啟動 FinMind 補救機制...")
        # 僅顯示前 10 檔範例
        print(f"   (Pending: {missing_stocks[:10]} ...)")
        
        # 呼叫 FinMind 下載器 (orchestrate_update)
        # 注意: FinMind 需要 Token
        orchestrate_update(missing_stocks)
    else:
        print("\n🎉 完美！所有目標股票皆已透過 HiStock/官方 來源更新。")

    # 5. ★ 獨立任務：更新大盤 (TAIEX)
    print("\n📊 正在更新大盤 (TAIEX) 資料...")
    taiex_updated = False
    for token in API_KEYS:
        try:
            url = "https://api.finmindtrade.com/api/v4/data"
            p = {
                "dataset": "TaiwanStockPrice",
                "data_id": "TAIEX",
                "start_date": "2000-01-01",
                "token": token
            }
            res = requests.get(url, params=p, timeout=15)
            if res.status_code == 200:
                data = res.json().get('data', [])
                if data:
                    df = pd.DataFrame(data)
                    df = df[['date', 'open', 'max', 'min', 'close', 'Trading_Volume']]
                    df.columns = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
                    
                    csv_path = os.path.join(DATA_FOLDER, "..", "TAIEX.csv")
                    df.to_csv(csv_path, index=False, encoding='utf-8')
                    print(f"✅ 大盤資料已更新: {csv_path}")
                    taiex_updated = True
                    break
        except Exception as e:
            print(f"⚠️ 大盤更新失敗 ({token[-4:]}): {e}")
            continue
            
    if not taiex_updated:
        print("❌ 大盤資料更新失敗 (所有 Token 皆無效)")
    else:
        # Mark as success only if TAIEX (and logically others) finished
        with open(SUCCESS_MARKER, 'w') as f:
             f.write(f"Updated at {datetime.now()}")
        print("✅ 全流程完成，已建立成功標記 (.update_success)。")
