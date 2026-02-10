"""排序所有 history CSV 的 Date 欄位"""
import os, sys, glob
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "data_core", "history")

files = glob.glob(os.path.join(DATA, "*.csv"))
fixed = 0
for i, f in enumerate(files):
    try:
        df = pd.read_csv(f)
        if 'Date' not in df.columns or len(df) < 2:
            continue
        dates = df['Date'].tolist()
        if dates != sorted(dates):
            df = df.sort_values('Date').reset_index(drop=True)
            df.to_csv(f, index=False)
            fixed += 1
    except:
        pass
    if (i+1) % 500 == 0:
        print(f"已處理 {i+1}/{len(files)}...")

print(f"✅ 完成！修正 {fixed}/{len(files)} 檔的排序")
