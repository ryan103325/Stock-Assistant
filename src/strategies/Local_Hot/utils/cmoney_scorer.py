# -*- coding: utf-8 -*-
"""
CMoney 8 維度族群評分模組

評分維度：
法人走向：
1. 三大法人合計
2. 外資買超
3. 投信買超
4. 自營商買超

資金融資券：
1. 資金流向
2. 融資增減
3. 融券增減
4. 券資比

評分公式：
最終分數 = 基礎分 (100 - (排名-1)*5) × top100 比例
"""

import pandas as pd

# 評分參數
BASE_SCORE = 100  # 滿分
RANK_DECAY = 5    # 每名遞減分數
MAX_RANK = 20     # 最大排名


def get_sector_stocks(sector_name: str, sector_mapping: dict) -> list:
    """
    彈性取得族群成分股（處理「概念股_」前綴問題）
    """
    if sector_name in sector_mapping:
        return sector_mapping[sector_name]
    
    if sector_name.startswith('概念股_'):
        clean_name = sector_name.replace('概念股_', '')
        if clean_name in sector_mapping:
            return sector_mapping[clean_name]
    
    prefixed_name = f'概念股_{sector_name}'
    if prefixed_name in sector_mapping:
        return sector_mapping[prefixed_name]
    
    for key in sector_mapping:
        if sector_name in key or key in sector_name:
            return sector_mapping[key]
    
    return []


def calculate_rank_score(rank: int) -> float:
    """計算排名基礎分數"""
    if rank < 1:
        rank = 1
    if rank > MAX_RANK:
        rank = MAX_RANK
    
    return BASE_SCORE - (rank - 1) * RANK_DECAY


def calculate_top100_ratio(sector_stocks: list, top100_stocks: list) -> float:
    """計算族群的 Top100 成分股比例"""
    if not sector_stocks:
        return 0.0
    
    sector_set = set(str(s) for s in sector_stocks)
    top100_set = set(str(s) for s in top100_stocks)
    
    overlap = sector_set & top100_set
    return len(overlap) / len(sector_set)


def get_top3_gainers(sector_stocks: list, stock_df: pd.DataFrame) -> list:
    """取得該族群在 Top100 中漲幅前 3 的成分股"""
    if stock_df.empty or not sector_stocks:
        return []
    
    sector_set = set(str(s) for s in sector_stocks)
    
    mask = (
        stock_df['code'].astype(str).isin(sector_set) &
        stock_df['is_top100']
    )
    candidates = stock_df[mask].copy()
    
    if candidates.empty:
        return []
    
    candidates = candidates.sort_values('change', ascending=False)
    top3 = candidates.head(3)
    
    result = []
    for _, row in top3.iterrows():
        result.append({
            'code': str(row['code']),
            'name': str(row.get('name', '')),
            'change': round(float(row['change']), 2)
        })
    
    return result


def score_dimension(rank: int, top100_ratio: float, dimension: str) -> dict:
    """通用評分函數"""
    base_score = calculate_rank_score(rank)
    final_score = base_score * top100_ratio
    
    return {
        'dimension': dimension,
        'rank': rank,
        'base_score': round(base_score, 1),
        'top100_ratio': round(top100_ratio, 3),
        'final_score': round(final_score, 1)
    }


def process_cmoney_rankings(cmoney_df: pd.DataFrame, sector_mapping: dict, stock_df: pd.DataFrame) -> dict:
    """
    處理 CMoney 資料並計算 8 維度評分（分為法人走向和資金融資券）
    
    Returns:
        dict: {
            'institutional': {
                'inst_total': [...],
                'foreign': [...],
                'trust': [...],
                'dealer': [...]
            },
            'fund_margin': {
                'fund_flow': [...],
                'margin': [...],
                'short': [...],
                'ratio': [...]
            }
        }
    """
    if cmoney_df.empty:
        return {
            'institutional': {'inst_total': [], 'foreign': [], 'trust': [], 'dealer': []},
            'fund_margin': {'fund_flow': [], 'margin': [], 'short': [], 'ratio': []}
        }
    
    top100_stocks = stock_df[stock_df['is_top100']]['code'].astype(str).tolist() if not stock_df.empty else []
    
    results = {
        'institutional': {'inst_total': [], 'foreign': [], 'trust': [], 'dealer': []},
        'fund_margin': {'fund_flow': [], 'margin': [], 'short': [], 'ratio': []}
    }
    
    def process_dim(sort_col, dim_name, data_extractor, ascending=False):
        """處理單一維度"""
        if sort_col not in cmoney_df.columns:
            return []
        
        dim_df = cmoney_df[cmoney_df[sort_col].notna()].copy()
        # 轉換為數值
        dim_df[sort_col] = pd.to_numeric(dim_df[sort_col].astype(str).str.replace(',', ''), errors='coerce')
        dim_df = dim_df[dim_df[sort_col].notna() & (dim_df[sort_col] != 0)]
        dim_df = dim_df.sort_values(sort_col, ascending=ascending).head(20)
        
        dim_results = []
        for rank, (_, row) in enumerate(dim_df.iterrows(), 1):
            sector_name = row['SectorName']
            sector_stocks = get_sector_stocks(sector_name, sector_mapping)
            top100_ratio = calculate_top100_ratio(sector_stocks, top100_stocks)
            score = score_dimension(rank, top100_ratio, dim_name)
            top3 = get_top3_gainers(sector_stocks, stock_df)
            
            dim_results.append({
                'sector': sector_name,
                'score': score,
                'data': data_extractor(row),
                'top3': top3
            })
        
        dim_results.sort(key=lambda x: x['score']['final_score'], reverse=True)
        return dim_results
    
    # === 法人走向 ===
    inst_types = ['inst_total', 'foreign', 'trust', 'dealer']
    inst_names = {'inst_total': '三大法人', 'foreign': '外資', 'trust': '投信', 'dealer': '自營商'}
    
    for inst_type in inst_types:
        amount_col = f'{inst_type}_amount'
        if amount_col in cmoney_df.columns:
            def make_extractor(it):
                def extractor(row):
                    amt = row.get(f'{it}_amount', 0)
                    return {
                        'buy_amount': float(str(amt).replace(',', '') or 0) if amt else 0
                    }
                return extractor
            
            results['institutional'][inst_type] = process_dim(
                amount_col, inst_type, make_extractor(inst_type)
            )
    
    # === 資金融資券 ===
    
    # 資金流向
    if 'FundFlow' in cmoney_df.columns:
        results['fund_margin']['fund_flow'] = process_dim(
            'FundFlow', 'fund_flow',
            lambda row: {
                'fund_flow': float(str(row.get('FundFlow', 0)).replace(',', '') or 0) / 100,
                'price_change': float(str(row.get('PriceChange', 0)).replace('%', '').replace(',', '') or 0),
                'turnover_change': float(str(row.get('TurnoverChange', 0)).replace('%', '').replace(',', '') or 0)
            }
        )
    
    # 融資增減
    if 'MarginChange' in cmoney_df.columns:
        results['fund_margin']['margin'] = process_dim(
            'MarginChange', 'margin',
            lambda row: {
                'margin_change': float(str(row.get('MarginChange', 0)).replace(',', '') or 0),
                'margin_balance': float(str(row.get('MarginBalance', 0)).replace(',', '') or 0),
                'change_pct': 0
            }
        )
    
    # 融券增減
    if 'ShortChange' in cmoney_df.columns:
        results['fund_margin']['short'] = process_dim(
            'ShortChange', 'short',
            lambda row: {
                'short_change': float(str(row.get('ShortChange', 0)).replace(',', '') or 0),
                'short_balance': float(str(row.get('ShortBalance', 0)).replace(',', '') or 0)
            }
        )
    
    # 券資比
    if 'ShortMarginRatio' in cmoney_df.columns:
        results['fund_margin']['ratio'] = process_dim(
            'ShortMarginRatio', 'ratio',
            lambda row: {
                'short_margin_ratio': float(str(row.get('ShortMarginRatio', 0)).replace('%', '').replace(',', '') or 0)
            }
        )
    
    return results


if __name__ == "__main__":
    print("=== 測試 cmoney_scorer ===")
    print(f"排名1: {calculate_rank_score(1)}")
    print(f"排名10: {calculate_rank_score(10)}")
    score = score_dimension(1, 0.6, 'foreign')
    print(f"外資第1名, top100比例0.6: {score}")
