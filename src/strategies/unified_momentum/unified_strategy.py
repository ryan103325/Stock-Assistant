# -*- coding: utf-8 -*-
"""
統一動能策略 (Unified Momentum Strategy)
整合族群動能與資金流向的綜合策略

核心特點：
1. CMoney 標籤 + 動態補全
2. Top 50 雙重排序（數量優先，分數次要）
3. HTML 圖片報表
"""

import os
import sys
from datetime import datetime

# 路徑設定
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STRATEGIES_DIR = os.path.dirname(SCRIPT_DIR)
SRC_DIR = os.path.dirname(STRATEGIES_DIR)
PROJECT_ROOT = os.path.dirname(SRC_DIR)

# 加入專案路徑
sys.path.insert(0, SCRIPT_DIR)
sys.path.insert(0, SRC_DIR)
sys.path.insert(0, PROJECT_ROOT)

# 載入環境變數
from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

# 載入模組
from utils.data_loader import load_stock_data, load_sector_cmoney_data
from utils.tag_manager import load_cmoney_tags, build_unified_mapping
from utils.sector_analyzer import analyze_all_sectors
from utils.scorer import calculate_score, filter_sectors
from utils.image_generator import generate_image_report
from utils.telegram_sender import send_telegram_photo


def get_latest_date():
    """取得最新交易日期（從歷史資料）"""
    history_dir = os.path.join(SRC_DIR, "data_core", "history")
    ref_file = os.path.join(history_dir, "2330.csv")
    
    if os.path.exists(ref_file):
        try:
            import pandas as pd
            df = pd.read_csv(ref_file)
            df['Date'] = pd.to_datetime(df['Date'])
            latest = df['Date'].max().strftime('%Y/%m/%d')
            return latest
        except:
            pass
    
    return datetime.now().strftime('%Y/%m/%d')


def main():
    """主程式"""
    print("🚀 統一動能策略 (Unified Momentum) 啟動...")
    print(f"   時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 1. 取得日期
    latest_date = get_latest_date()
    date_str = latest_date.replace('/', '-')
    print(f"📅 資料日期: {latest_date}")
    
    # 2. 載入資料
    print("\n📂 載入資料...")
    stock_df = load_stock_data(latest_date, top_n=150)
    if stock_df.empty:
        print("❌ 無法載入個股資料")
        return
    
    cmoney_tags = load_cmoney_tags()
    if not cmoney_tags:
        print("❌ 無法載入 CMoney 標籤")
        return
    
    # 3. 載入 CMoney 族群資金資料
    print("\n💰 載入 CMoney 族群資金資料...")
    cmoney_df = load_sector_cmoney_data(date_str)
    if cmoney_df.empty:
        print("⚠️ 無 CMoney 資料，資金流向將顯示為 0")
    
    # 4. 建立統一標籤映射（CMoney + 動態補全）
    print("\n🏷️ 建立統一標籤映射...")
    unified_mapping = build_unified_mapping(stock_df, cmoney_tags)
    print(f"   完成：{len(unified_mapping)} 個族群")
    
    # 5. 族群分析
    print("\n📊 分析族群...")
    sector_metrics_list = analyze_all_sectors(stock_df, cmoney_df=cmoney_df, sector_mapping=unified_mapping)
    
    # 5. 評分
    print("\n🎯 計算評分...")
    scored_sectors = []
    for metrics in sector_metrics_list:
        score = calculate_score(metrics)
        scored_sectors.append({
            'metrics': metrics,
            'score': score
        })
    
    # 6. 篩選與排序
    print("\n🔍 篩選與排序...")
    filtered = filter_sectors(scored_sectors, min_score=40)
    
    # Top 50 雙重排序
    sorted_sectors = sorted(
        filtered,
        key=lambda x: (
            -x['metrics'].get('top50_count', 0),  # 主要：Top 50 數量
            -x['score'].get('total_score', 0)     # 次要：基礎分數
        )
    )
    
    # 7. 顯示結果
    print(f"\n🏆 Top 5 族群:")
    if sorted_sectors:
        for i, sector in enumerate(sorted_sectors[:5]):
            metrics = sector['metrics']
            score = sector['score']
            top50 = metrics.get('top50_count', 0)
            print(f"   {i+1}. {metrics['sector_name']} [{score['total_score']:.0f}分] 💰{top50}支 Top50")
            print(f"      進榜: {metrics['active_stocks']}/{metrics['total_stocks']} | 上漲: {metrics['up_ratio']:.0%}")
    else:
        print("   無符合條件的族群")
    
    # 8. 生成圖片報表
    print("\n🎨 生成圖片報表...")
    image_path = generate_image_report(sorted_sectors, date_str)
    
    if image_path:
        # 9. 發送 Telegram
        print("\n📤 發送 Telegram...")
        caption = f"📊 統一動能策略 | {date_str}\n共 {len(sorted_sectors)} 個族群通過篩選"
        success = send_telegram_photo(image_path, caption=caption)
        
        # 只有發送成功才刪除圖片
        if success:
            try:
                if os.path.exists(image_path):
                    os.remove(image_path)
                    print(f"🗑️ 已刪除暫存圖片: {image_path}")
            except Exception as e:
                print(f"⚠️ 刪除圖片失敗: {e}")
        else:
            print(f"📁 圖片保留於: {image_path}")
    
    print("\n✅ 完成!")


if __name__ == "__main__":
    main()
