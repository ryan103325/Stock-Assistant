"""Debug: 驗證資產負債表解析邏輯"""
import sys, re
sys.path.insert(0, '.')
from fundamental_master.data_collection.goodinfo_scraper import GoodinfoScraper
from bs4 import BeautifulSoup

s = GoodinfoScraper(headless=True)

url = 'https://goodinfo.tw/tw/StockAssetsStatus.asp?STOCK_ID=2330'
s._wait_and_get_page(url, wait_selector='table')
s._switch_to_quarterly_mode()

soup = BeautifulSoup(s.driver.page_source, 'lxml')
tbl = soup.find('table', id='tblDetail')
rows = tbl.find_all('tr')

print(f'Total rows: {len(rows)}')
for i, row in enumerate(rows[2:20]):
    cells = row.find_all(['td', 'th'])
    if len(cells) < 10:
        print(f'  Row {i+2}: only {len(cells)} cells, skipping')
        continue
    quarter = cells[0].get_text(strip=True)
    capital_txt = cells[5].get_text(strip=True) if len(cells) > 5 else 'N/A'
    bps_txt = cells[6].get_text(strip=True) if len(cells) > 6 else 'N/A'
    eq_pct_txt = cells[21].get_text(strip=True) if len(cells) > 21 else 'N/A'

    def parse(t):
        t = t.replace(',', '').replace('，', '')
        try: return float(t)
        except: return None
    
    capital = parse(capital_txt)
    bps = parse(bps_txt)
    
    status = '✅' if capital and bps else '❌'
    print(f'  Row {i+2}: quarter={quarter}, capital={capital_txt}({capital}), bps={bps_txt}({bps}), eq%={eq_pct_txt} {status}')

s.close()
