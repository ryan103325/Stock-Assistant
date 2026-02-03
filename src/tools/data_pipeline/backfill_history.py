# === 歷史資料補齊腳本：使用官方 TWSE/TPEx CSV ===
# 用途：補齊 2026 年 1 月歷史資料 (個股 + 大盤)

import os
import sys
import time
import requests
import pandas as pd
from datetime import datetime
from io import StringIO
from dotenv import load_dotenv

load_dotenv()

# ================= 設定區 =================
SRC_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_FOLDER = os.path.join(SRC_ROOT, "data_core", "history")
TAIEX_FILE = os.path.join(SRC_ROOT, "data_core", "TAIEX.csv")

# 目標月份 (民國年月)
TARGET_YEAR_MONTH = "20260101"  # 西元 2026 年 1 月

# 限速設定
REQUEST_DELAY = 0.5  # 每次請求間隔 (秒)

# ================= 核心函數 =================

def fetch_twse_monthly(stock_id: str, date_yyyymmdd: str = TARGET_YEAR_MONTH) -> pd.DataFrame:
    """
    從 TWSE (證交所) 抓取單一股票的月資料
    URL: https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY?date=20260101&stockNo=2330&response=csv
    """
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    url = f"https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY"
    params = {
        "date": date_yyyymmdd,
        "stockNo": stock_id,
        "response": "csv"
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=15, verify=False)
        if resp.status_code != 200:
            return pd.DataFrame()

        
        text = resp.text
        if not text or "日期" not in text:
            return pd.DataFrame()
        
        # 解析 CSV (跳過前幾行標題)
        lines = text.strip().split('\n')
        
        # 找到包含 "日期" 的行作為 header
        header_idx = -1
        for i, line in enumerate(lines):
            if "日期" in line and "開盤價" in line:
                header_idx = i
                break
        
        if header_idx == -1:
            return pd.DataFrame()
        
        # 重建 CSV 文本
        csv_lines = lines[header_idx:]
        # 過濾掉空行和非資料行
        data_lines = [csv_lines[0]]  # header
        for line in csv_lines[1:]:
            # 資料行應該以民國年/月/日開頭
            if line.strip() and "/" in line[:15]:
                data_lines.append(line)
        
        csv_text = '\n'.join(data_lines)
        df = pd.read_csv(StringIO(csv_text))
        
        # 標準化欄位名稱
        df.columns = [c.strip().replace(' ', '') for c in df.columns]
        
        # 轉換日期 (民國年 -> 西元年)
        def convert_roc_date(roc_str):
            try:
                parts = roc_str.strip().split('/')
                year = int(parts[0]) + 1911
                month = int(parts[1])
                day = int(parts[2])
                return f"{year}-{month:02d}-{day:02d}"
            except:
                return None
        
        df['Date'] = df['日期'].apply(convert_roc_date)
        df = df.dropna(subset=['Date'])
        
        # 清理數值欄位 (移除逗號)
        def clean_number(val):
            if pd.isna(val):
                return 0.0
            s = str(val).replace(',', '').replace('--', '0').replace('X', '0')
            try:
                return float(s)
            except:
                return 0.0
        
        # 建立標準化 DataFrame
        result = pd.DataFrame({
            'Date': df['Date'],
            'Open': df['開盤價'].apply(clean_number),
            'High': df['最高價'].apply(clean_number),
            'Low': df['最低價'].apply(clean_number),
            'Close': df['收盤價'].apply(clean_number),
            'Volume': df['成交股數'].apply(clean_number),
        })
        
        # 計算 Amount
        result['Amount'] = result['Close'] * result['Volume']
        
        return result
        
    except Exception as e:
        print(f"  ❌ TWSE 錯誤: {e}")
        return pd.DataFrame()


def fetch_tpex_monthly(stock_id: str, date_yyyymmdd: str = TARGET_YEAR_MONTH) -> pd.DataFrame:
    """
    從 TPEx (櫃買中心) 抓取單一股票的月資料
    URL: https://www.tpex.org.tw/www/zh-tw/afterTrading/tradingStock?code=3293&date=2026/01/01&id=&response=csv
    
    TPEx CSV 格式範例:
    日 期,成交張數,成交仟元,開盤,最高,最低,收盤,漲跌,筆數
    "115/01/02","1,302","950,974","723.00","734.00","722.00","730.00","9.00","4,689"
    """
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    # 轉換日期格式
    year = date_yyyymmdd[:4]
    month = date_yyyymmdd[4:6]
    day = date_yyyymmdd[6:8]
    date_str = f"{year}/{month}/{day}"
    
    url = f"https://www.tpex.org.tw/www/zh-tw/afterTrading/tradingStock"
    params = {
        "code": stock_id,
        "date": date_str,
        "response": "csv"
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=15, verify=False)
        if resp.status_code != 200:
            return pd.DataFrame()
        
        text = resp.text
        # TPEx 用 "日 期" 或 "日期"
        if not text or ("日期" not in text and "日 期" not in text):
            return pd.DataFrame()
        
        # 解析 CSV
        lines = text.strip().split('\n')
        
        # 找到 header 行 (包含 "開盤")
        header_idx = -1
        for i, line in enumerate(lines):
            if "開盤" in line:
                header_idx = i
                break
        
        if header_idx == -1:
            return pd.DataFrame()
        
        # 取得資料行
        csv_lines = lines[header_idx:]
        data_lines = [csv_lines[0]]  # header
        for line in csv_lines[1:]:
            # 資料行以民國年開頭 (例如 "115/01/02")
            stripped = line.strip().strip('"')
            if stripped and '/' in stripped[:10] and stripped[0].isdigit():
                data_lines.append(line)
        
        if len(data_lines) <= 1:
            return pd.DataFrame()
        
        csv_text = '\n'.join(data_lines)
        df = pd.read_csv(StringIO(csv_text))
        
        # 標準化欄位名稱 (移除空格)
        df.columns = [c.strip().replace(' ', '') for c in df.columns]
        
        # 轉換民國年日期
        def convert_roc_date(roc_str):
            try:
                s = str(roc_str).strip().strip('"')
                parts = s.split('/')
                year = int(parts[0]) + 1911
                month = int(parts[1])
                day = int(parts[2])
                return f"{year}-{month:02d}-{day:02d}"
            except:
                return None
        
        # 找到日期欄位
        date_col = next((c for c in df.columns if '日期' in c), None)
        if not date_col:
            return pd.DataFrame()
        
        df['Date'] = df[date_col].apply(convert_roc_date)
        df = df.dropna(subset=['Date'])
        
        # 清理數值欄位
        def clean_number(val):
            if pd.isna(val):
                return 0.0
            s = str(val).replace(',', '').replace('"', '').replace('--', '0').replace('X', '0')
            try:
                return float(s)
            except:
                return 0.0
        
        # 找欄位 (注意 TPEx 用「成交張數」不是「成交股數」)
        open_col = next((c for c in df.columns if '開盤' in c), None)
        high_col = next((c for c in df.columns if '最高' in c), None)
        low_col = next((c for c in df.columns if '最低' in c), None)
        close_col = next((c for c in df.columns if '收盤' in c), None)
        vol_col = next((c for c in df.columns if '成交張數' in c or '成交股數' in c), None)
        
        if not all([open_col, high_col, low_col, close_col]):
            return pd.DataFrame()
        
        result = pd.DataFrame({
            'Date': df['Date'],
            'Open': df[open_col].apply(clean_number) if open_col else 0,
            'High': df[high_col].apply(clean_number) if high_col else 0,
            'Low': df[low_col].apply(clean_number) if low_col else 0,
            'Close': df[close_col].apply(clean_number) if close_col else 0,
            # 張數 * 1000 = 股數
            'Volume': df[vol_col].apply(clean_number) * 1000 if vol_col else 0,
        })
        
        result['Amount'] = result['Close'] * result['Volume']
        
        return result
        
    except Exception as e:
        print(f"  ❌ TPEx 錯誤: {e}")
        return pd.DataFrame()



def update_stock_csv(stock_id: str, new_data: pd.DataFrame) -> int:
    """
    將新資料合併到現有 CSV，返回新增的行數
    """
    file_path = os.path.join(DATA_FOLDER, f"{stock_id}.csv")
    
    if not os.path.exists(file_path):
        # 檔案不存在，直接寫入
        new_data.to_csv(file_path, index=False, float_format='%.2f')
        return len(new_data)
    
    try:
        df_old = pd.read_csv(file_path)
        existing_dates = set(df_old['Date'].astype(str).tolist())
        
        # 過濾出新日期
        new_rows = new_data[~new_data['Date'].isin(existing_dates)]
        
        if len(new_rows) == 0:
            return 0
        
        # 合併並排序
        df_merged = pd.concat([df_old, new_rows], ignore_index=True)
        df_merged = df_merged.drop_duplicates(subset=['Date'], keep='last')
        df_merged = df_merged.sort_values('Date')
        
        df_merged.to_csv(file_path, index=False, float_format='%.2f')
        return len(new_rows)
        
    except Exception as e:
        print(f"  ❌ 合併錯誤 {stock_id}: {e}")
        return 0


def update_taiex_via_finmind():
    """
    使用 FinMind 更新大盤 TAIEX 資料
    """
    print("\n📊 正在更新大盤 (TAIEX) 資料...")
    
    token = os.getenv("FINMIND_TOKEN", "")
    if not token:
        print("  ⚠️ 未設定 FINMIND_TOKEN，跳過大盤更新")
        return False
    
    try:
        url = "https://api.finmindtrade.com/api/v4/data"
        params = {
            "dataset": "TaiwanStockPrice",
            "data_id": "TAIEX",
            "start_date": "2000-01-01",
            "token": token
        }
        
        resp = requests.get(url, params=params, timeout=30)
        if resp.status_code != 200:
            print(f"  ❌ FinMind API 錯誤: {resp.status_code}")
            return False
        
        data = resp.json().get('data', [])
        if not data:
            print("  ❌ FinMind 無資料")
            return False
        
        df = pd.DataFrame(data)
        df = df[['date', 'open', 'max', 'min', 'close', 'Trading_Volume']]
        df.columns = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
        
        df.to_csv(TAIEX_FILE, index=False, encoding='utf-8')
        print(f"  ✅ 大盤資料已更新: {len(df)} 筆 (最新: {df['Date'].iloc[-1]})")
        return True
        
    except Exception as e:
        print(f"  ❌ 大盤更新失敗: {e}")
        return False


def main():
    """
    主程式：補齊所有個股歷史資料
    """
    # 強制 UTF-8 輸出
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8')
    
    print("=" * 60)
    print("📅 歷史資料補齊腳本")
    print(f"📁 資料目錄: {DATA_FOLDER}")
    print(f"📆 目標月份: 2026 年 1 月")
    print("=" * 60)
    
    # 1. 更新大盤 (TAIEX)
    update_taiex_via_finmind()
    
    # 2. 取得所有股票清單
    csv_files = [f for f in os.listdir(DATA_FOLDER) if f.endswith('.csv')]
    stock_ids = [f.replace('.csv', '') for f in csv_files]
    
    print(f"\n📋 發現 {len(stock_ids)} 檔個股資料")
    
    # 3. 逐一更新
    updated_count = 0
    failed_stocks = []
    
    for i, stock_id in enumerate(stock_ids):
        print(f"[{i+1}/{len(stock_ids)}] 處理 {stock_id}...", end=" ")
        
        # 先嘗試 TWSE
        df = fetch_twse_monthly(stock_id)
        source = "TWSE"
        
        # 若 TWSE 無資料，改用 TPEx
        if df.empty:
            df = fetch_tpex_monthly(stock_id)
            source = "TPEx"
        
        if df.empty:
            print("❌ 無資料")
            failed_stocks.append(stock_id)
        else:
            new_rows = update_stock_csv(stock_id, df)
            if new_rows > 0:
                print(f"✅ +{new_rows} 筆 ({source})")
                updated_count += 1
            else:
                print(f"⏭️ 已是最新 ({source})")
        
        # 限速
        time.sleep(REQUEST_DELAY)
    
    # 4. 總結
    print("\n" + "=" * 60)
    print("📊 補齊完成！")
    print(f"   ✅ 更新: {updated_count} 檔")
    print(f"   ❌ 失敗: {len(failed_stocks)} 檔")
    if failed_stocks:
        print(f"   失敗清單: {failed_stocks[:20]}...")
    print("=" * 60)


if __name__ == "__main__":
    main()
