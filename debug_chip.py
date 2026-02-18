"""Debug v8：用 Selenium 點選融資融券選項，觀察 AJAX 載入後的 table"""
import time
import sys
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
import re

def make_driver():
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_experimental_option('useAutomationExtension', False)
    d = webdriver.Chrome(options=options)
    d.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument',
        {'source': 'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'})
    return d

stock_id = sys.argv[1] if len(sys.argv) > 1 else '2330'
driver = make_driver()
driver.get('https://goodinfo.tw/tw')
time.sleep(3)

try:
    url = f'https://goodinfo.tw/tw/ShowBuySaleChart.asp?STOCK_ID={stock_id}&CHT_CAT2=MARGIN'
    driver.get(url)
    time.sleep(5)
    
    # 找頁面上的 select 元素（下拉選單）
    selects = driver.find_elements(By.TAG_NAME, 'select')
    print(f"找到 {len(selects)} 個 select 元素")
    for i, sel in enumerate(selects):
        options_els = sel.find_elements(By.TAG_NAME, 'option')
        opts = [(o.get_attribute('value'), o.text) for o in options_els[:10]]
        print(f"  select[{i}] id={sel.get_attribute('id')}: {opts}")
    
    # 找含有「融資」的 option
    for sel in selects:
        options_els = sel.find_elements(By.TAG_NAME, 'option')
        for opt in options_els:
            if '融資' in opt.text and '餘額' in opt.text:
                print(f"\n找到融資融券選項: value={opt.get_attribute('value')}, text={opt.text}")
                # 選擇這個選項
                from selenium.webdriver.support.ui import Select
                Select(sel).select_by_value(opt.get_attribute('value'))
                time.sleep(5)
                print("選擇後等待 5 秒...")
                
                soup = BeautifulSoup(driver.page_source, 'lxml')
                for t in soup.find_all('table', id=True):
                    tid = t.get('id')
                    rows = t.find_all('tr')
                    if len(rows) > 3:
                        print(f"\n  id={tid}: {len(rows)} rows")
                        for j, row in enumerate(rows[:5]):
                            cells = row.find_all(['td','th'])
                            texts = [c.get_text(strip=True) for c in cells]
                            if texts and any(texts):
                                print(f"    row[{j}]: {texts[:12]}")
                break
    
    # 也試試直接找 URL 參數
    print("\n=== 試不同 URL 參數 ===")
    test_urls = [
        f'https://goodinfo.tw/tw/ShowBuySaleChart.asp?STOCK_ID={stock_id}&CHT_CAT2=MARGIN&CHT_CAT=MARGIN_BALANCE',
        f'https://goodinfo.tw/tw/ShowBuySaleChart.asp?STOCK_ID={stock_id}&CHT_CAT2=MARGIN&CHT_CAT=CREDIT',
        f'https://goodinfo.tw/tw/ShowBuySaleChart.asp?STOCK_ID={stock_id}&CHT_CAT2=MARGIN&CHT_CAT=MARGIN',
    ]
    for test_url in test_urls:
        driver.get(test_url)
        time.sleep(3)
        soup = BeautifulSoup(driver.page_source, 'lxml')
        # 找 fsbDetail
        fsb = soup.find('table', id='fsbDetail')
        if fsb:
            rows = fsb.find_all('tr')
            print(f"\n  {test_url.split('CHT_CAT=')[1]}: fsbDetail {len(rows)} rows")
            for j, row in enumerate(rows[:5]):
                cells = row.find_all(['td','th'])
                texts = [c.get_text(strip=True) for c in cells]
                if texts and any(texts):
                    print(f"    row[{j}]: {texts[:12]}")

finally:
    driver.quit()
