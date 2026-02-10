import requests
import pandas as pd
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

SRC_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_FOLDER = os.path.join(SRC_ROOT, "data_core")
TAIEX_PATH = os.path.join(DATA_FOLDER, "TAIEX.csv")

def update_taiex():
    token = os.getenv("FINMIND_TOKEN")
    if not token:
        print("❌ No FinMind Token")
        return

    url = "https://api.finmindtrade.com/api/v4/data"
    params = {
        "dataset": "TaiwanStockPrice",
        "data_id": "TAIEX",
        "start_date": "2020-07-01",
        "token": token
    }

    print("📡 Fetching TAIEX data from FinMind...")
    try:
        resp = requests.get(url, params=params)
        data = resp.json().get('data', [])
        
        if not data:
            print("❌ No data returned")
            return

        df = pd.DataFrame(data)
        # Rename columns to match standard format
        # FinMind: date, open, max, min, close, Trading_Volume
        # Target: Date, Open, High, Low, Close, Volume
        
        df = df.rename(columns={
            'date': 'Date',
            'open': 'Open',
            'max': 'High',
            'min': 'Low',
            'close': 'Close',
            'Trading_Volume': 'Volume'
        })
        
        df = df[['Date', 'Open', 'High', 'Low', 'Close', 'Volume']]
        
        # Save
        df.to_csv(TAIEX_PATH, index=False, encoding='utf-8')
        print(f"✅ TAIEX Updated: {TAIEX_PATH}")
        print(f"   Last Date: {df.iloc[-1]['Date']}")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    update_taiex()
