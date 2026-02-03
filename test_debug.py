# 測試腳本
import sys
sys.path.insert(0, 'src/strategies/unified_momentum')

from utils.data_loader import load_stock_data, load_sector_cmoney_data
from utils.tag_manager import load_cmoney_tags, build_unified_mapping
from utils.sector_analyzer import analyze_all_sectors
from utils.scorer import calculate_score, filter_sectors

# 載入資料
stock_df = load_stock_data('2026/01/23', top_n=150)
cmoney_tags = load_cmoney_tags()
cmoney_df = load_sector_cmoney_data('2026-01-23')
unified_mapping = build_unified_mapping(stock_df, cmoney_tags)

# 分析
sector_metrics_list = analyze_all_sectors(stock_df, cmoney_df=cmoney_df, sector_mapping=unified_mapping)

# 評分
scored_sectors = []
for m in sector_metrics_list:
    score = calculate_score(m)
    scored_sectors.append({'metrics': m, 'score': score})

# 篩選
filtered = filter_sectors(scored_sectors, min_score=40)

# 排序
sorted_sectors = sorted(
    filtered,
    key=lambda x: (-x['metrics'].get('top50_count', 0), -x['score'].get('total_score', 0))
)

print('=== Top 5 族群 ===')
for i, s in enumerate(sorted_sectors[:5]):
    m = s['metrics']
    print(f"{i+1}. {m['sector_name']}")
    print(f"   fund_flow: {m['fund_flow']}")
    print(f"   margin_change: {m['margin_change']}")
    print()
