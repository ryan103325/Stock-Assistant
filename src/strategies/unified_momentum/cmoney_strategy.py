# -*- coding: utf-8 -*-
"""
CMoney 三維度族群動能策略

功能：
1. 載入 CMoney 爬蟲資料
2. 計算三維度評分（資金流向、融資增減、券資比）
3. 生成報表圖片
4. 發送 Telegram 通知
"""

import os
import sys
from datetime import datetime

# 路徑設定
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
UTILS_DIR = os.path.join(SCRIPT_DIR, "utils")
STRATEGIES_DIR = os.path.dirname(SCRIPT_DIR)
SRC_DIR = os.path.dirname(STRATEGIES_DIR)
PROJECT_ROOT = os.path.dirname(SRC_DIR)

# 載入 .env 檔案
try:
    from dotenv import load_dotenv
    env_path = os.path.join(PROJECT_ROOT, '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
except ImportError:
    pass

# 添加路徑
sys.path.insert(0, UTILS_DIR)
sys.path.insert(0, SRC_DIR)

from utils.data_loader import load_stock_data, load_sector_cmoney_data, load_sector_member_mapping
from utils.cmoney_scorer import process_cmoney_rankings
from utils.cmoney_html import generate_cmoney_report_html

# 嘗試載入 Telegram
try:
    from utils.telegram_sender import send_telegram_photo
    HAS_TELEGRAM = True
except ImportError:
    HAS_TELEGRAM = False


def generate_report_image(html_content: str, output_path: str) -> bool:
    """
    將 HTML 轉換為圖片（使用 Selenium headless Chrome）
    
    Args:
        html_content: HTML 內容
        output_path: 輸出圖片路徑
        
    Returns:
        bool: 是否成功
    """
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        import tempfile
        import time
        
        # 設定 Chrome 選項
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=850,1600')
        options.add_argument('--force-device-scale-factor=1.5')
        
        # 啟動瀏覽器
        driver = webdriver.Chrome(options=options)
        
        try:
            # 寫入臨時 HTML 檔案
            with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
                f.write(html_content)
                temp_html_path = f.name
            
            # 開啟 HTML
            driver.get(f'file:///{temp_html_path}')
            time.sleep(1)  # 等待渲染
            
            # 調整視窗高度以適應內容
            total_height = driver.execute_script("return document.body.scrollHeight")
            driver.set_window_size(850, total_height + 100)
            time.sleep(0.5)
            
            # 截圖
            driver.save_screenshot(output_path)
            print(f"✅ 報表圖片已生成: {output_path}")
            
            # 清理臨時檔案
            import os as os_temp
            os_temp.remove(temp_html_path)
            
            return True
            
        finally:
            driver.quit()
            
    except ImportError:
        print("❌ Selenium 未安裝，請執行: pip install selenium webdriver-manager")
        return False
    except Exception as e:
        print(f"❌ 生成圖片失敗: {e}")
        return False


def send_telegram_report(image_path: str, caption: str = "") -> bool:
    """
    發送報表到 Telegram
    
    Args:
        image_path: 圖片路徑
        caption: 圖片說明
        
    Returns:
        bool: 是否成功
    """
    if not HAS_TELEGRAM:
        print("⚠️ Telegram 模組未載入")
        return False
    
    try:
        result = send_telegram_photo(image_path, caption=caption)
        
        # 發送成功後刪除暫存圖片
        if result and os.path.exists(image_path):
            os.remove(image_path)
            print("🗑️ 已刪除暫存圖片")
            
        return result
        
    except Exception as e:
        print(f"❌ 發送 Telegram 失敗: {e}")
        return False


def run_cmoney_strategy(date_str: str = None, send_telegram: bool = True) -> dict:
    """
    執行 CMoney 三維度策略
    
    Args:
        date_str: 指定日期，None 則使用今天
        send_telegram: 是否發送 Telegram
        
    Returns:
        dict: 策略執行結果
    """
    print("=" * 50)
    print("🚀 CMoney 三維度族群動能策略")
    print("=" * 50)
    
    # 日期處理
    if date_str is None:
        date_str = datetime.now().strftime('%Y-%m-%d')
    
    print(f"\n📅 分析日期: {date_str}")
    
    # 1. 載入個股資料
    print("\n📊 載入個股資料...")
    stock_df = load_stock_data(date_str, top_n=150)
    
    if stock_df.empty:
        print("❌ 無法載入個股資料")
        return {'success': False, 'error': '無法載入個股資料'}
    
    # 2. 載入 CMoney 資料
    print("\n📊 載入 CMoney 資料...")
    cmoney_df = load_sector_cmoney_data(date_str)
    
    if cmoney_df.empty:
        print("❌ 無法載入 CMoney 資料")
        return {'success': False, 'error': '無法載入 CMoney 資料'}
    
    # 3. 載入族群成員映射
    print("\n📊 載入族群成員映射...")
    sector_mapping = load_sector_member_mapping()
    
    # 4. 計算三維度評分
    print("\n📊 計算三維度評分...")
    results = process_cmoney_rankings(cmoney_df, sector_mapping, stock_df)
    
    # 輸出統計
    print(f"\n📈 評分結果:")
    print(f"   三維度熱門族群: {len(results['multi_dimension'])} 個")
    print(f"   資金流向排行: {len(results['fund_flow'])} 個")
    print(f"   融資增減排行: {len(results['margin'])} 個")
    print(f"   券資比排行: {len(results['ratio'])} 個")
    
    # 5. 生成 HTML 報表
    print("\n📊 生成報表...")
    html_content = generate_cmoney_report_html(results, date_str)
    
    # 6. 生成圖片
    output_dir = os.path.join(SCRIPT_DIR, "output")
    os.makedirs(output_dir, exist_ok=True)
    
    image_filename = f"cmoney_report_{date_str.replace('-', '')}.png"
    image_path = os.path.join(output_dir, image_filename)
    
    if generate_report_image(html_content, image_path):
        # 7. 發送 Telegram
        if send_telegram:
            caption = f"📊 CMoney 族群動能報表 | {date_str}"
            send_telegram_report(image_path, caption)
    
    # 輸出詳細結果
    print("\n" + "=" * 50)
    print("📋 詳細結果")
    print("=" * 50)
    
    # 三維度熱門
    if results['multi_dimension']:
        print("\n🔥 三維度熱門族群:")
        for item in results['multi_dimension'][:3]:
            print(f"   {item['sector']} (平均 {item['avg_score']:.0f} 分)")
    
    # 資金流向 Top 3
    if results['fund_flow']:
        print("\n💰 資金流向 Top 3:")
        for item in results['fund_flow'][:3]:
            score = item['score']['final_score']
            fund = item['data'].get('fund_flow', 0)
            print(f"   {item['sector']}: {score:.0f}分 | 資金 {fund:.1f}億")
    
    # 融資增減 Top 3
    if results['margin']:
        print("\n📈 融資增減 Top 3:")
        for item in results['margin'][:3]:
            score = item['score']['final_score']
            change = item['data'].get('margin_change', 0)
            pct = item['data'].get('change_pct', 0)
            print(f"   {item['sector']}: {score:.0f}分 | +{change:,.0f}張 (+{pct:.2f}%)")
    
    # 券資比 Top 3
    if results['ratio']:
        print("\n📉 券資比 Top 3:")
        for item in results['ratio'][:3]:
            score = item['score']['final_score']
            ratio = item['data'].get('short_margin_ratio', 0)
            print(f"   {item['sector']}: {score:.0f}分 | 券資比 {ratio:.2f}%")
    
    print("\n" + "=" * 50)
    print("✅ 策略執行完成")
    print("=" * 50)
    
    return {
        'success': True,
        'date': date_str,
        'results': results,
        'image_path': image_path if os.path.exists(image_path) else None
    }


if __name__ == "__main__":
    # 測試執行
    import argparse
    
    parser = argparse.ArgumentParser(description='CMoney 三維度族群動能策略')
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
