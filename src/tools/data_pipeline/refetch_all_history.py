"""完整重新抓取所有 history 股票資料 (2020-07-01 ~ today)"""
import os, sys, glob, time, requests, pandas as pd
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv()

TOKEN = os.getenv('FINMIND_TOKEN', '')
DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'data_core', 'history')
API = 'https://api.finmindtrade.com/api/v4/data'
START = '2020-07-01'
DELAY = 6

if not TOKEN:
    print('❌ FINMIND_TOKEN not set')
    sys.exit(1)

files = glob.glob(os.path.join(DATA, '*.csv'))
stock_ids = sorted([os.path.basename(f).replace('.csv', '') for f in files])

print(f'📊 完整重新抓取 {len(stock_ids)} 檔')
print(f'📅 {START} ~ today')
print(f'⏱️  預估: {len(stock_ids) * DELAY / 3600:.1f} 小時')
print('='*60)

success, failed, deleted = 0, [], 0

for i, sid in enumerate(stock_ids):
    print(f'[{i+1}/{len(stock_ids)}] {sid}...', end=' ')
    
    try:
        r = requests.get(API, params={
            'dataset': 'TaiwanStockPrice', 'data_id': sid,
            'start_date': START, 'token': TOKEN
        }, timeout=30)
        
        if r.status_code == 429:
            print('⚠️ Rate limit')
            time.sleep(60)
            r = requests.get(API, params={
                'dataset': 'TaiwanStockPrice', 'data_id': sid,
                'start_date': START, 'token': TOKEN
            }, timeout=30)
        
        data = r.json().get('data', [])
        
        if not data:
            fp = os.path.join(DATA, f'{sid}.csv')
            if os.path.exists(fp):
                os.remove(fp)
                deleted += 1
                print('🗑️ Deleted')
            else:
                print('❌ No data')
            failed.append(sid)
            continue
        
        df = pd.DataFrame(data)
        df = df.rename(columns={
            'date': 'Date', 'open': 'Open', 'max': 'High',
            'min': 'Low', 'close': 'Close', 'Trading_Volume': 'Volume'
        })
        df['Amount'] = df['Close'].astype(float) * df['Volume'].astype(float)
        df = df[['Date', 'Open', 'High', 'Low', 'Close', 'Volume', 'Amount']]
        df = df.drop_duplicates('Date', keep='last').sort_values('Date')
        
        fp = os.path.join(DATA, f'{sid}.csv')
        df.to_csv(fp, index=False, float_format='%.2f')
        
        print(f'✅ {len(df)} rows')
        success += 1
        
    except Exception as e:
        print(f'❌ {e}')
        failed.append(sid)
    
    if i < len(stock_ids) - 1:
        time.sleep(DELAY)
    
    if (i+1) % 100 == 0:
        print(f'\n--- {i+1}/{len(stock_ids)} ({success} ok, {len(failed)} failed) ---\n')

print('\n' + '='*60)
print(f'✅ {success} | 🗑️ {deleted} | ❌ {len(failed) - deleted}')
print('='*60)
