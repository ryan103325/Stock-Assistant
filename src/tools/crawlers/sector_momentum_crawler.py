# -*- coding: utf-8 -*-
"""
CMoney 族群資金動能數據爬蟲

爬取四個維度的族群數據:
1. 資金流向 (成交比重)
2. 融資增減
3. 融券增減
4. 券資比

使用 Selenium 處理動態網頁
"""

import os
import time
import pandas as pd
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

# 路徑設定
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TOOLS_DIR = os.path.dirname(SCRIPT_DIR)
SRC_DIR = os.path.dirname(TOOLS_DIR)
DATA_DIR = os.path.join(SRC_DIR, "data_core")
MARKET_META_DIR = os.path.join(DATA_DIR, "market_meta")

# 確保目錄存在
os.makedirs(MARKET_META_DIR, exist_ok=True)

# URLs
URLS = {
    # 法人走向
    "inst_total": "https://www.cmoney.tw/finance/f00019.aspx?o=1&o2=4",    # 三大法人合計
    "foreign": "https://www.cmoney.tw/finance/f00019.aspx",                # 外資買超
    "trust": "https://www.cmoney.tw/finance/f00019.aspx?o=1&o2=2",         # 投信買超
    "dealer": "https://www.cmoney.tw/finance/f00019.aspx?o=1&o2=3",        # 自營商
    # 資金融資券
    "fund_flow": "https://www.cmoney.tw/finance/f00018.aspx?o=3&o2=1",     # 資金流向
    "margin": "https://www.cmoney.tw/finance/f00020.aspx?o=1&o2=1",        # 融資增減
    "short": "https://www.cmoney.tw/finance/f00020.aspx?o=1&o2=2",         # 融券增減
    "short_margin_ratio": "https://www.cmoney.tw/finance/f00020.aspx?o=1&o2=3"  # 券資比
}

# 集團股過濾
EXCLUDE_KEYWORD = "集團"


def setup_driver():
    """設定 Selenium WebDriver (Selenium 4.x)"""
    options = Options()
    options.add_argument('--headless=new')  # 新版無頭模式
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-blink-features=AutomationControlled')  # 避免被偵測
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    # 禁用日誌
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    
    try:
        # Selenium 4.x 會自動下載和管理 ChromeDriver
        print("   正在啟動 Chrome (自動下載 ChromeDriver)...")
        driver = webdriver.Chrome(options=options)
        print("   ✓ Chrome 啟動成功")
        return driver
    except Exception as e:
        print(f"❌ 無法啟動 Chrome WebDriver: {e}")
        print("\n可能的解決方案:")
        print("1. 確認已安裝 Chrome 瀏覽器")
        print("2. 更新 Selenium: pip install --upgrade selenium")
        print("3. 手動安裝 ChromeDriver: https://chromedriver.chromium.org/")
        return None


def fetch_table_data(driver, url, table_type):
    """
    抓取單一頁面的表格資料
    
    Args:
        driver: Selenium WebDriver
        url: 目標網址
        table_type: 資料類型 (fund_flow/margin/short/short_margin_ratio)
    
    Returns:
        list: 表格資料列表
    """
    print(f"\n📡 正在抓取 {table_type} 資料...")
    print(f"   URL: {url}")
    
    try:
        driver.get(url)
        
        # 等待表格載入 (最多等待15秒)
        wait = WebDriverWait(driver, 15)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "table")))
        
        # 等待表格中有實際資料 (等待 tbody 中有 tr)
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr")))
        except:
            pass  # 有些表格沒有 tbody
        
        # 額外等待確保 JavaScript 執行完成
        time.sleep(5)  # 增加到5秒
        
        # 取得頁面 HTML
        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        
        # 尋找主要資料表格
        tables = soup.find_all('table')
        if not tables:
            print(f"   ⚠️ 未找到表格")
            return {'headers': [], 'data': []}
        
        # 找到有最多資料列的表格
        main_table = None
        max_rows = 0
        for table in tables:
            rows = table.find_all('tr')
            if len(rows) > max_rows:
                max_rows = len(rows)
                main_table = table
        
        if not main_table or max_rows < 2:
            print(f"   ⚠️ 找不到有效表格")
            return {'headers': [], 'data': []}
        
        # 提取表頭
        headers = []
        header_row = main_table.find('tr')
        if header_row:
            for th in header_row.find_all(['th', 'td']):
                headers.append(th.get_text(strip=True))
        
        print(f"   表頭: {headers[:10]}...")
        
        # 提取資料列
        data_rows = []
        rows = main_table.find_all('tr')[1:]  # 跳過表頭
        
        for row in rows:
            cells = [td.get_text(strip=True) for td in row.find_all(['td', 'th'])]
            if cells and any(cells):  # 過濾空列
                data_rows.append(cells)
        
        print(f"   ✓ 抓取到 {len(data_rows)} 筆資料")
        
        # 驗證資料完整性
        if len(data_rows) > 0:
            print(f"   第一筆資料: {data_rows[0][:5]}...")
        
        return {
            'headers': headers,
            'data': data_rows
        }
        
    except Exception as e:
        print(f"   ❌ 抓取失敗: {e}")
        import traceback
        traceback.print_exc()
        return {'headers': [], 'data': []}


def parse_fund_flow_data(raw_data):
    """解析資金流向資料"""
    if not raw_data['data']:
        return pd.DataFrame()
    
    # 實際欄位: 分類, 收盤價, 日漲跌, 日漲幅(%), 日成交金額(百萬), 近一日資金流向(百萬), 近一日成交金額增幅(%)
    df = pd.DataFrame(raw_data['data'])
    
    if len(df.columns) >= 7:
        df.columns = ['SectorName', 'ClosePrice', 'DailyChange', 'DailyChangePct', 'TurnoverAmount', 'FundFlow', 'TurnoverChangePct'] + list(df.columns[7:])
        # 選取需要的欄位: 族群名稱, 漲跌幅, 成交金額增幅(當作成交比重變化), 資金流向
        df = df[['SectorName', 'DailyChangePct', 'TurnoverChangePct', 'FundFlow']]
        df.columns = ['SectorName', 'PriceChange', 'TurnoverChange', 'FundFlow']
    else:
        print(f"   ⚠️ 資金流向欄位數量不符: {len(df.columns)}, 預期>=7")
        return pd.DataFrame()
    
    # 過濾集團股
    df = df[~df['SectorName'].str.contains(EXCLUDE_KEYWORD, na=False)]
    
    return df


def parse_margin_data(raw_data):
    """解析融資增減資料"""
    if not raw_data['data']:
        return pd.DataFrame()
    
    df = pd.DataFrame(raw_data['data'])
    
    # 實際欄位: 分類, 融資餘額, 融資增減(張), 融劵餘額, 融劵增減(張), 資劵比
    if len(df.columns) >= 3:
        df.columns = ['SectorName', 'MarginBalance', 'MarginChange'] + list(df.columns[3:])
        df = df[['SectorName', 'MarginBalance', 'MarginChange']]
    else:
        print(f"   ⚠️ 融資欄位數量不符: {len(df.columns)}, 預期>=3")
        return pd.DataFrame()
    
    # 過濾集團股
    df = df[~df['SectorName'].str.contains(EXCLUDE_KEYWORD, na=False)]
    
    return df


def parse_short_data(raw_data):
    """解析融券增減資料"""
    if not raw_data['data']:
        return pd.DataFrame()
    
    df = pd.DataFrame(raw_data['data'])
    
    # 實際欄位: 分類, 融資餘額, 融資增減(張), 融劵餘額, 融劵增減(張), 資劵比
    # 我們要的是融券(第4,5欄)
    if len(df.columns) >= 5:
        df.columns = ['SectorName', 'MarginBalance', 'MarginChange', 'ShortBalance', 'ShortChange'] + list(df.columns[5:])
        df = df[['SectorName', 'ShortBalance', 'ShortChange']]
    else:
        print(f"   ⚠️ 融券欄位數量不符: {len(df.columns)}, 預期>=5")
        return pd.DataFrame()
    
    # 過濾集團股
    df = df[~df['SectorName'].str.contains(EXCLUDE_KEYWORD, na=False)]
    
    return df


def parse_short_margin_ratio_data(raw_data):
    """解析券資比資料"""
    if not raw_data['data']:
        return pd.DataFrame()
    
    df = pd.DataFrame(raw_data['data'])
    
    # 實際欄位: 分類, 融資餘額, 融資增減(張), 融劵餘額, 融劵增減(張), 資劵比
    # 我們要的是資券比(第6欄,但這個頁面可能按券資比排序,需要計算變化)
    if len(df.columns) >= 6:
        df.columns = ['SectorName', 'MarginBalance', 'MarginChange', 'ShortBalance', 'ShortChange', 'ShortMarginRatio'] + list(df.columns[6:])
        df = df[['SectorName', 'ShortMarginRatio']]
    else:
        print(f"   ⚠️ 券資比欄位數量不符: {len(df.columns)}, 預期>=6")
        return pd.DataFrame()
    
    # 過濾集團股
    df = df[~df['SectorName'].str.contains(EXCLUDE_KEYWORD, na=False)]
    
    return df


def parse_institutional_data(raw_data, inst_type):
    """
    解析法人買超資料
    
    實際頁面結構: 分類, 外資, 投信, 自營商, 合計
    
    Args:
        raw_data: 原始資料
        inst_type: 法人類型 (inst_total/foreign/trust/dealer)
    
    Returns:
        DataFrame
    """
    if not raw_data['data']:
        return pd.DataFrame()
    
    df = pd.DataFrame(raw_data['data'])
    
    # 法人頁面欄位: 分類, 外資, 投信, 自營商, 合計
    if len(df.columns) >= 5:
        df.columns = ['SectorName', 'Foreign', 'Trust', 'Dealer', 'Total'] + list(df.columns[5:])
        
        # 根據法人類型選擇對應欄位
        col_map = {
            'inst_total': 'Total',
            'foreign': 'Foreign', 
            'trust': 'Trust',
            'dealer': 'Dealer'
        }
        
        target_col = col_map.get(inst_type, 'Total')
        
        # 只保留族群名稱和目標欄位
        df = df[['SectorName', target_col]].copy()
        df.columns = ['SectorName', f'{inst_type}_amount']
        
        # 轉換為數值
        df[f'{inst_type}_amount'] = pd.to_numeric(
            df[f'{inst_type}_amount'].astype(str).str.replace(',', ''), 
            errors='coerce'
        ).fillna(0)
        
    else:
        print(f"   ⚠️ 法人買超欄位數量不符: {len(df.columns)}, 預期>=5")
        return pd.DataFrame()
    
    # 過濾集團股
    df = df[~df['SectorName'].str.contains(EXCLUDE_KEYWORD, na=False)]
    
    return df


def merge_all_data(fund_flow_df, margin_df, short_df, ratio_df,
                   inst_total_df=None, foreign_df=None, trust_df=None, dealer_df=None):
    """合併所有資料"""
    print("\n🔗 合併資料...")
    
    # 找出所有非空的 DataFrame
    dfs = [fund_flow_df, margin_df, short_df, ratio_df]
    
    # 加入法人資料
    if inst_total_df is not None and not inst_total_df.empty:
        dfs.append(inst_total_df)
    if foreign_df is not None and not foreign_df.empty:
        dfs.append(foreign_df)
    if trust_df is not None and not trust_df.empty:
        dfs.append(trust_df)
    if dealer_df is not None and not dealer_df.empty:
        dfs.append(dealer_df)
    
    non_empty_dfs = [df for df in dfs if df is not None and not df.empty]
    
    if not non_empty_dfs:
        print("   ⚠️ 所有資料都是空的")
        return pd.DataFrame()
    
    # 以第一個非空的 DataFrame 為基礎
    result = non_empty_dfs[0].copy()
    
    # 合併其他 DataFrame
    for df in non_empty_dfs[1:]:
        result = result.merge(df, on='SectorName', how='outer')
    
    # 新增日期欄位
    result.insert(0, 'Date', datetime.now().strftime('%Y-%m-%d'))
    
    print(f"   ✓ 合併完成,共 {len(result)} 個族群")
    
    return result


def main():
    """主程式"""
    print("🚀 CMoney 族群資金動能爬蟲啟動...")
    print(f"   時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 設定 WebDriver
    driver = setup_driver()
    if not driver:
        return
    
    try:
        # 抓取法人走向 (4 個維度)
        print("\n" + "=" * 50)
        print("📊 抓取法人走向資料...")
        print("=" * 50)
        inst_total_raw = fetch_table_data(driver, URLS['inst_total'], 'inst_total')
        foreign_raw = fetch_table_data(driver, URLS['foreign'], 'foreign')
        trust_raw = fetch_table_data(driver, URLS['trust'], 'trust')
        dealer_raw = fetch_table_data(driver, URLS['dealer'], 'dealer')
        
        # 抓取資金融資券 (4 個維度)
        print("\n" + "=" * 50)
        print("📊 抓取資金融資券資料...")
        print("=" * 50)
        fund_flow_raw = fetch_table_data(driver, URLS['fund_flow'], 'fund_flow')
        margin_raw = fetch_table_data(driver, URLS['margin'], 'margin')
        short_raw = fetch_table_data(driver, URLS['short'], 'short')
        ratio_raw = fetch_table_data(driver, URLS['short_margin_ratio'], 'short_margin_ratio')
        
        # 解析資料
        print("\n📊 解析資料...")
        
        # 法人資料
        inst_total_df = parse_institutional_data(inst_total_raw, 'inst_total')
        foreign_df = parse_institutional_data(foreign_raw, 'foreign')
        trust_df = parse_institutional_data(trust_raw, 'trust')
        dealer_df = parse_institutional_data(dealer_raw, 'dealer')
        
        # 資金融資券資料
        fund_flow_df = parse_fund_flow_data(fund_flow_raw)
        margin_df = parse_margin_data(margin_raw)
        short_df = parse_short_data(short_raw)
        ratio_df = parse_short_margin_ratio_data(ratio_raw)
        
        # 📊 診斷摘要 — 確認各維度資料完整性
        print("\n📊 各維度資料量摘要:")
        for name, df in [
            ("三大法人", inst_total_df), ("外資", foreign_df),
            ("投信", trust_df), ("自營商", dealer_df),
            ("資金流向", fund_flow_df), ("融資增減", margin_df),
            ("融券增減", short_df), ("券資比", ratio_df)
        ]:
            count = len(df) if df is not None and not df.empty else 0
            status = "✅" if count > 0 else "❌"
            print(f"   {status} {name}: {count} 筆")
        
        # 合併資料
        final_df = merge_all_data(
            fund_flow_df, margin_df, short_df, ratio_df,
            inst_total_df, foreign_df, trust_df, dealer_df
        )
        
        # 儲存 CSV
        today = datetime.now().strftime('%Y%m%d')
        output_file = os.path.join(MARKET_META_DIR, f"sector_momentum_{today}.csv")
        final_df.to_csv(output_file, index=False, encoding='utf-8-sig')
        
        print(f"\n✅ 完成!")
        print(f"   檔案: {output_file}")
        print(f"   族群數: {len(final_df)}")
        print(f"   欄位數: {len(final_df.columns)}")
        print(f"\n前5筆資料:")
        print(final_df.head().to_string())
        
    except Exception as e:
        print(f"\n❌ 執行失敗: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        driver.quit()
        print("\n🔚 瀏覽器已關閉")


if __name__ == "__main__":
    main()
