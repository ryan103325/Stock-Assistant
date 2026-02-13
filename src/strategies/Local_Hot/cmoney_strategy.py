# -*- coding: utf-8 -*-
"""
CMoney 雙圖報表策略

生成兩張報表圖片：
1. 法人走向（三大法人、外資、投信、自營商）
2. 資金融資券（資金流向、融資增減、融券增減、券資比）
"""

import os
import sys
import pandas as pd
from datetime import datetime

# 載入環境變數
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# 路徑設定
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
UTILS_DIR = os.path.join(SCRIPT_DIR, "utils")
SRC_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))

sys.path.insert(0, UTILS_DIR)
sys.path.insert(0, SRC_DIR)

# 導入模組
from utils.data_loader import load_stock_data, load_sector_cmoney_data, load_sector_member_mapping
from utils.cmoney_scorer import process_cmoney_rankings
from utils.cmoney_html import generate_institutional_report_html, generate_fund_margin_report_html

# Telegram
try:
    from utils.telegram_sender import send_telegram_photo
    HAS_TELEGRAM = True
except ImportError:
    HAS_TELEGRAM = False


def generate_report_image(html_content: str, output_path: str) -> bool:
    """使用 Selenium 將 HTML 轉換為圖片"""
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        import tempfile
        import time
        
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--hide-scrollbars')
        options.add_argument('--force-device-scale-factor=2')
        
        driver = webdriver.Chrome(options=options)
        
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
                f.write(html_content)
                temp_html_path = f.name
            
            driver.get(f'file:///{temp_html_path}')
            time.sleep(1.5)
            
            driver.execute_script("""
                document.body.style.overflow = 'hidden';
                document.documentElement.style.overflow = 'hidden';
            """)
            
            total_width = driver.execute_script("return document.body.scrollWidth")
            total_height = driver.execute_script("return document.body.scrollHeight")
            
            driver.set_window_size(total_width + 100, total_height + 150)
            time.sleep(0.5)
            
            driver.save_screenshot(output_path)
            print(f"✅ 報表圖片已生成: {output_path}")
            
            os.remove(temp_html_path)
            return True
            
        finally:
            driver.quit()
            
    except Exception as e:
        print(f"❌ 生成圖片失敗: {e}")
        return False


def send_telegram_report(image_path: str, caption: str = "") -> bool:
    """發送報表到 Telegram"""
    if not HAS_TELEGRAM:
        print("⚠️ Telegram 模組未載入")
        return False
    
    try:
        result = send_telegram_photo(image_path, caption=caption)
        
        if result and os.path.exists(image_path):
            os.remove(image_path)
            print("🗑️ 已刪除暫存圖片")
            
        return result
        
    except Exception as e:
        print(f"❌ 發送 Telegram 失敗: {e}")
        return False


def run_cmoney_strategy(date_str: str = None, send_telegram: bool = True) -> dict:
    """
    執行 CMoney 雙圖報表策略
    
    Args:
        date_str: 指定日期，None 則使用今天
        send_telegram: 是否發送 Telegram
        
    Returns:
        dict: 策略執行結果
    """
    print("=" * 50)
    print("🚀 CMoney 雙圖報表策略")
    print("=" * 50)
    
    if date_str is None:
        # 自動偵測最新有效交易日（避免 Pipeline 寫入的非交易日假資料）
        try:
            ref_csv = os.path.join(SRC_DIR, "data_core", "history", "2330.csv")
            ref_df = pd.read_csv(ref_csv)
            ref_df['Date'] = pd.to_datetime(ref_df['Date'])
            ref_df = ref_df.sort_values('Date')
            # 找最後一個「收盤價與前日不同」的日期 = 真正的交易日
            ref_df['prev_close'] = ref_df['Close'].shift(1)
            valid = ref_df[ref_df['Close'] != ref_df['prev_close']]
            if not valid.empty:
                date_str = valid.iloc[-1]['Date'].strftime('%Y-%m-%d')
                print(f"📅 自動偵測最新有效交易日: {date_str}")
            else:
                date_str = ref_df.iloc[-1]['Date'].strftime('%Y-%m-%d')
        except Exception as e:
            date_str = datetime.now().strftime('%Y-%m-%d')
            print(f"⚠️ 無法自動偵測交易日 ({e})，使用今天: {date_str}")
    
    print(f"\n📅 分析日期: {date_str}")
    
    # 1. 載入個股資料
    print("\n📊 載入個股資料...")
    stock_df = load_stock_data(date_str, top_n=150)
    
    if stock_df.empty:
        print("❌ 無法載入個股資料")
        return {'success': False, 'error': '無法載入個股資料'}
    
    # 2. 執行爬蟲抓取最新 CMoney 資料
    print("\n📡 抓取 CMoney 族群資料...")
    try:
        # 動態導入爬蟲
        import importlib.util
        crawler_path = os.path.join(SRC_DIR, "tools", "crawlers", "sector_momentum_crawler.py")
        spec = importlib.util.spec_from_file_location("sector_momentum_crawler", crawler_path)
        crawler_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(crawler_module)
        
        # 執行爬蟲
        crawler_module.main()
        print("✅ CMoney 資料抓取完成")
    except Exception as e:
        print(f"⚠️ 爬蟲執行失敗: {e}")
        print("   將嘗試載入現有資料...")
    
    # 3. 載入 CMoney 資料
    print("\n📊 載入 CMoney 資料...")
    cmoney_df = load_sector_cmoney_data(date_str)
    
    if cmoney_df.empty:
        print("❌ 無法載入 CMoney 資料")
        return {'success': False, 'error': '無法載入 CMoney 資料'}
    
    # 4. 載入族群成員映射
    print("\n📊 載入族群成員映射...")
    sector_mapping = load_sector_member_mapping()
    
    # 5. 計算 8 維度評分
    print("\n📊 計算 8 維度評分...")
    results = process_cmoney_rankings(cmoney_df, sector_mapping, stock_df)
    
    # 輸出統計
    inst = results.get('institutional', {})
    fm = results.get('fund_margin', {})
    
    print(f"\n📈 評分結果:")
    print(f"   法人走向:")
    print(f"     三大法人: {len(inst.get('inst_total', []))} 個")
    print(f"     外資: {len(inst.get('foreign', []))} 個")
    print(f"     投信: {len(inst.get('trust', []))} 個")
    print(f"     自營商: {len(inst.get('dealer', []))} 個")
    print(f"   資金融資券:")
    print(f"     資金流向: {len(fm.get('fund_flow', []))} 個")
    print(f"     融資增減: {len(fm.get('margin', []))} 個")
    print(f"     融券增減: {len(fm.get('short', []))} 個")
    print(f"     券資比: {len(fm.get('ratio', []))} 個")
    
    # 6. 生成報表
    output_dir = os.path.join(SCRIPT_DIR, "output")
    os.makedirs(output_dir, exist_ok=True)
    
    date_suffix = date_str.replace('-', '')
    
    # 圖片一：法人走向
    print("\n📊 生成法人走向報表...")
    inst_html = generate_institutional_report_html(results, date_str)
    inst_image_path = os.path.join(output_dir, f"institutional_{date_suffix}.png")
    
    if generate_report_image(inst_html, inst_image_path):
        if send_telegram:
            send_telegram_report(inst_image_path, f"🏛️ 法人走向報表 | {date_str}")
    
    # 圖片二：資金融資券
    print("\n📊 生成資金融資券報表...")
    fm_html = generate_fund_margin_report_html(results, date_str)
    fm_image_path = os.path.join(output_dir, f"fund_margin_{date_suffix}.png")
    
    if generate_report_image(fm_html, fm_image_path):
        if send_telegram:
            send_telegram_report(fm_image_path, f"💰 資金融資券報表 | {date_str}")
    
    print("\n" + "=" * 50)
    print("✅ 策略執行完成")
    print("=" * 50)
    
    return {
        'success': True,
        'date': date_str,
        'results': results
    }


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='CMoney 雙圖報表策略')
    parser.add_argument('--date', type=str, default=None, help='分析日期 (YYYY-MM-DD)')
    parser.add_argument('--no-telegram', action='store_true', help='不發送 Telegram')
    
    args = parser.parse_args()
    
    result = run_cmoney_strategy(
        date_str=args.date,
        send_telegram=not args.no_telegram
    )
    
    if not result['success']:
        print(f"❌ 執行失敗: {result.get('error', '未知錯誤')}")
        sys.exit(1)
