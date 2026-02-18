"""測試 - 精簡輸出版"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import os
os.environ['PYTHONIOENCODING'] = 'utf-8'

from fundamental_master.data_collection.goodinfo_scraper import GoodinfoScraper
from fundamental_master.utils.config import Config
from bs4 import BeautifulSoup
import re, time

s = GoodinfoScraper(headless=True)
s._setup_driver()
s._warmup_cookies()

url = f'{Config.GOODINFO_BASE_URL}/StockFinDetail.asp?STOCK_ID=2330&RPT_CAT=IS_M_QUAR'
s._wait_and_get_page(url, wait_selector='table')
time.sleep(2)

def count_quarters():
    soup = BeautifulSoup(s.driver.page_source, 'lxml')
    table = soup.find('table', id='tblFinDetail')
    if not table:
        return 0, []
    rows = table.find_all('tr')
    h0 = rows[0].find_all(['th', 'td']) if rows else []
    qs = [c.get_text(strip=True) for c in h0[1:] if re.match(r'^\d{4}Q\d$', c.get_text(strip=True))]
    return len(qs), qs

n1, q1 = count_quarters()
print(f'BEFORE={n1}')

# 嘗試用 JS 直接改 select 然後呼叫 ChgFinSheet
s.driver.execute_script("""
    var sel = document.getElementById('QRY_TIME');
    if (sel && sel.options.length >= 8) {
        sel.selectedIndex = 7;
        if (typeof ChgFinSheet === 'function') {
            ChgFinSheet();
        }
    }
""")
time.sleep(3)

# 等頁面 reload（ChgFinSheet 可能會 submit form）
try:
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.by import By
    WebDriverWait(s.driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, 'table#tblFinDetail'))
    )
    time.sleep(1)
except:
    pass

n2, q2 = count_quarters()
print(f'AFTER={n2}')
print(f'Q_LIST={q2}')

s.driver.quit()
print('DONE')
