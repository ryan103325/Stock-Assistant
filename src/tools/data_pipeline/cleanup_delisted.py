# === 清理 history 資料夾中的下市股票 CSV ===
# 用途：移動不在有效清單中的股票資料到 _archived 資料夾

import os
import sys
import shutil
from datetime import datetime

# 動態載入 Pipeline_data 的函數
SRC_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(SRC_ROOT, "tools", "data_pipeline"))

DATA_FOLDER = os.path.join(SRC_ROOT, "data_core", "history")
ARCHIVE_FOLDER = os.path.join(SRC_ROOT, "data_core", "history_archived")


def main():
    """
    清理下市股票 CSV (移動到 archived 資料夾)
    """
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8')
    
    print("=" * 60)
    print("🧹 清理下市股票 CSV")
    print(f"📁 資料目錄: {DATA_FOLDER}")
    print("=" * 60)
    
    # 1. 取得有效股票清單
    print("\n📡 取得目前有效股票清單...")
    try:
        from Pipeline_data import get_stock_list_universal
        valid_stocks = set(get_stock_list_universal())
    except Exception as e:
        print(f"❌ 無法取得股票清單: {e}")
        return
    
    if len(valid_stocks) == 0:
        print("❌ 有效清單為空，取消執行")
        return
    
    print(f"✅ 有效股票: {len(valid_stocks)} 檔")
    
    # 2. 掃描 history 資料夾
    csv_files = [f for f in os.listdir(DATA_FOLDER) if f.endswith('.csv')]
    existing_stocks = set(f.replace('.csv', '') for f in csv_files)
    
    print(f"📂 history 資料夾: {len(existing_stocks)} 檔")
    
    # 3. 找出需要封存的股票
    to_archive = existing_stocks - valid_stocks
    print(f"🗑️ 需要封存: {len(to_archive)} 檔")
    
    if len(to_archive) == 0:
        print("\n✅ 沒有需要清理的檔案！")
        return
    
    # 4. 建立封存資料夾
    if not os.path.exists(ARCHIVE_FOLDER):
        os.makedirs(ARCHIVE_FOLDER)
        print(f"📁 建立封存資料夾: {ARCHIVE_FOLDER}")
    
    # 5. 移動檔案
    moved_count = 0
    for stock_id in sorted(to_archive):
        src_path = os.path.join(DATA_FOLDER, f"{stock_id}.csv")
        dst_path = os.path.join(ARCHIVE_FOLDER, f"{stock_id}.csv")
        
        if os.path.exists(src_path):
            shutil.move(src_path, dst_path)
            moved_count += 1
            print(f"  📦 {stock_id}.csv -> archived/")
    
    # 6. 總結
    print("\n" + "=" * 60)
    print("🧹 清理完成！")
    print(f"   ✅ 已移動: {moved_count} 檔")
    print(f"   📁 封存位置: {ARCHIVE_FOLDER}")
    print("=" * 60)


if __name__ == "__main__":
    main()
