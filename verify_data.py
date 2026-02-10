import os, glob, pandas as pd, sys
sys.stdout.reconfigure(encoding='utf-8')

DATA = r'src\data_core\history'
files = glob.glob(os.path.join(DATA, '*.csv'))

total = len(files)
has_latest = 0
starts_correct = 0
new_ipo = 0

for f in files:
    try:
        df = pd.read_csv(f)
        if 'Date' not in df.columns or len(df) == 0:
            continue
        
        start = df.iloc[0]['Date']
        end = df.iloc[-1]['Date']
        
        if end >= '2026-02-10':
            has_latest += 1
        if start == '2020-07-01':
            starts_correct += 1
        elif start > '2020-07-01':
            new_ipo += 1
    except:
        pass

print(f'Total files: {total}')
print(f'Has 2026-02-10 or later: {has_latest}')
print(f'Starts 2020-07-01: {starts_correct}')
print(f'New IPO (starts after 2020-07-01): {new_ipo}')
print(f'Missing latest data: {total - has_latest}')

# Check TAIEX
df_t = pd.read_csv(r'src\data_core\TAIEX.csv')
print(f'\nTAIEX: {df_t.iloc[0]["Date"]} ~ {df_t.iloc[-1]["Date"]} ({len(df_t)} rows)')
