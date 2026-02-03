# 測試腳本
import sys
sys.path.insert(0, 'src/strategies/unified_momentum')
from utils.data_loader import load_stock_data, load_sector_cmoney_data, load_sector_member_mapping
from utils.cmoney_scorer import process_cmoney_rankings
from utils.cmoney_html import generate_cmoney_report_html

# 載入資料
stock_df = load_stock_data('2026-01-23', top_n=150)
cmoney_df = load_sector_cmoney_data()
sector_mapping = load_sector_member_mapping()

# 計算評分
results = process_cmoney_rankings(cmoney_df, sector_mapping, stock_df)

# 輸出結果
print('=== 評分結果 ===')
print(f"三維度: {len(results['multi_dimension'])}")
print(f"資金流向: {len(results['fund_flow'])}")
print(f"融資增減: {len(results['margin'])}")
print(f"券資比: {len(results['ratio'])}")

if results['fund_flow']:
    print()
    print('資金流向 Top 3:')
    for item in results['fund_flow'][:3]:
        sector = item['sector']
        score = item['score']['final_score']
        fund = item['data'].get('fund_flow', 0)
        top3 = item.get('top3', [])
        print(f"  {sector}: {score:.0f}分 | {fund:.1f}億")
        if top3:
            for s in top3:
                print(f"    - {s['code']} {s['name']} +{s['change']:.2f}%")

if results['margin']:
    print()
    print('融資增減 Top 3:')
    for item in results['margin'][:3]:
        sector = item['sector']
        score = item['score']['final_score']
        change = item['data'].get('margin_change', 0)
        pct = item['data'].get('change_pct', 0)
        print(f"  {sector}: {score:.0f}分 | +{change:,.0f}張 (+{pct:.2f}%)")

if results['ratio']:
    print()
    print('券資比 Top 3:')
    for item in results['ratio'][:3]:
        sector = item['sector']
        score = item['score']['final_score']
        ratio = item['data'].get('short_margin_ratio', 0)
        print(f"  {sector}: {score:.0f}分 | {ratio:.2f}%")

# 測試 HTML 生成
html = generate_cmoney_report_html(results, '2026-01-23')
print(f"\nHTML 長度: {len(html)}")

# 儲存 HTML
with open('src/strategies/unified_momentum/output/test_report.html', 'w', encoding='utf-8') as f:
    f.write(html)
print("HTML 已儲存到 output/test_report.html")
