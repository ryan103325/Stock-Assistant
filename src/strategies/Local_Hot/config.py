# -*- coding: utf-8 -*-
"""
統一動能策略配置
"""

# 階段一：活躍股票池
TOP_N_RANK = 150                  # 成交值前 N 名（用於分析）
TOP_50_RANK = 50                  # Top 50 熱門股（用於排序加權）

# 階段二：族群評分門檻
MIN_TOTAL_SCORE = 40              # 最低總分門檻
OUTPUT_TOP_N = 5                  # 輸出前 N 個族群

# 動態分類參數
MAX_DIFF_THRESHOLD = 3.0          # 最大漲幅差異（%）
