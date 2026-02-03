import pandas as pd
import json

# 讀取 CSV 檔案
# 請確保 'cmoney_all_tags.csv' 與此腳本位於同一目錄，或更改為絕對路徑
input_csv = 'cmoney_all_tags.csv'
output_json = 'cmoney_all_tags.json'

try:
    # 讀取數據
    df = pd.read_csv(input_csv)
    
    # 轉換為 JSON 格式 (List of Records)
    # force_ascii=False 確保中文能正確顯示，不被轉碼為 \uXXXX
    json_output = df.to_json(orient='records', force_ascii=False, indent=4)
    
    # 寫入檔案
    with open(output_json, 'w', encoding='utf-8') as f:
        f.write(json_output)
        
    print(f"轉換成功！檔案已儲存為：{output_json}")
    print(f"總筆數：{len(df)}")

except Exception as e:
    print(f"轉換發生錯誤：{e}")