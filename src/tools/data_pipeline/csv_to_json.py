"""
CSV to JSON Converter for GitHub Pages Chart Website
將 src/data_core/history/*.csv 轉換為 Lightweight Charts 可用的 JSON 格式
"""
import os
import json
import pandas as pd
from pathlib import Path

# 路徑設定
BASE_DIR = Path(__file__).parent.parent.parent.parent  # TG助手 根目錄
HISTORY_DIR = BASE_DIR / "src" / "data_core" / "history"
META_DIR = BASE_DIR / "src" / "data_core" / "market_meta"
OUTPUT_DIR = BASE_DIR / "docs" / "data"

# 設定
MAX_DAYS = 500  # 最多保留幾天資料


def load_stock_names():
    """從 master_stock_tags.csv 載入股票名稱對照表"""
    name_map = {}
    csv_path = META_DIR / "master_stock_tags.csv"
    
    if csv_path.exists():
        try:
            df = pd.read_csv(csv_path, encoding='utf-8-sig')
            for _, row in df.iterrows():
                code = str(row.get('Code', '')).strip()
                name = str(row.get('Name', '')).strip()
                if code and name:
                    name_map[code] = name
            print(f"✅ 載入 {len(name_map)} 筆股票名稱")
        except Exception as e:
            print(f"⚠️ 載入股票名稱失敗: {e}")
    
    return name_map


def convert_csv_to_json(csv_path: Path, stock_name: str) -> dict | None:
    """將單一 CSV 轉換為 JSON 格式"""
    try:
        df = pd.read_csv(csv_path)
        
        # 確認必要欄位
        required = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
        if not all(col in df.columns for col in required):
            return None
        
        # 移除有缺失值的行
        df = df.dropna(subset=required)
        
        # 取最後 MAX_DAYS 筆
        df = df.tail(MAX_DAYS).copy()
        
        if df.empty:
            return None
        
        # 轉換為 Lightweight Charts 格式
        data = []
        for _, row in df.iterrows():
            vol = row['Volume']
            # 處理可能的 NaN 或無效值
            if pd.isna(vol) or vol < 0:
                vol = 0
            
            data.append({
                "time": str(row['Date']),
                "open": float(row['Open']),
                "high": float(row['High']),
                "low": float(row['Low']),
                "close": float(row['Close']),
                "volume": int(vol / 1000)  # 轉換為張數
            })
        
        return {
            "name": stock_name,
            "data": data
        }
    except Exception as e:
        print(f"⚠️ 轉換失敗 {csv_path.name}: {e}")
        return None


def main():
    print("🚀 開始轉換 CSV 到 JSON...")
    
    # 建立輸出目錄
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # 載入股票名稱
    name_map = load_stock_names()
    
    # 取得所有 CSV 檔案
    csv_files = list(HISTORY_DIR.glob("*.csv"))
    print(f"📁 找到 {len(csv_files)} 個 CSV 檔案")
    
    # 建立股票清單
    stock_list = []
    success_count = 0
    
    for csv_path in csv_files:
        stock_id = csv_path.stem  # 檔名不含副檔名
        stock_name = name_map.get(stock_id, stock_id)
        
        # 轉換
        result = convert_csv_to_json(csv_path, stock_name)
        if result:
            # 寫入 JSON
            json_path = OUTPUT_DIR / f"{stock_id}.json"
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False)
            
            # 加入清單
            stock_list.append({
                "id": stock_id,
                "name": stock_name
            })
            success_count += 1
    
    # 寫入股票清單
    stock_list.sort(key=lambda x: x['id'])
    list_path = OUTPUT_DIR / "stock_list.json"
    with open(list_path, 'w', encoding='utf-8') as f:
        json.dump(stock_list, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 轉換完成: {success_count}/{len(csv_files)} 檔")
    print(f"📄 股票清單: {list_path}")
    print(f"📂 輸出目錄: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
