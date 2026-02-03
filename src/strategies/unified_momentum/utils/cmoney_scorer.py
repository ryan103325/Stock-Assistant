# -*- coding: utf-8 -*-
"""
CMoney 三維度族群評分模組

評分維度：
1. 資金流向 (多方)
2. 融資增減 (多方)
3. 券資比 (空方)

評分公式：
最終分數 = 基礎分 (100 - (排名-1)*5) × top100 比例
"""

import os
import pandas as pd

# 評分參數
BASE_SCORE = 100  # 滿分
RANK_DECAY = 5    # 每名遞減分數
MAX_RANK = 20     # 最大排名


def get_sector_stocks(sector_name: str, sector_mapping: dict) -> list:
    """
    彈性取得族群成分股（處理「概念股_」前綴問題）
    
    Args:
        sector_name: 族群名稱（可能帶有 概念股_ 前綴）
        sector_mapping: 族群 → 成分股映射
        
    Returns:
        list: 成分股代碼列表
    """
    # 直接匹配
    if sector_name in sector_mapping:
        return sector_mapping[sector_name]
    
    # 移除「概念股_」前綴後匹配
    if sector_name.startswith('概念股_'):
        clean_name = sector_name.replace('概念股_', '')
        if clean_name in sector_mapping:
            return sector_mapping[clean_name]
    
    # 嘗試添加「概念股_」前綴後匹配
    prefixed_name = f'概念股_{sector_name}'
    if prefixed_name in sector_mapping:
        return sector_mapping[prefixed_name]
    
    # 模糊匹配（名稱包含關係）
    for key in sector_mapping:
        if sector_name in key or key in sector_name:
            return sector_mapping[key]
    
    return []


def calculate_rank_score(rank: int) -> float:
    """
    計算排名基礎分數
    
    Args:
        rank: 排名 (1-20)
        
    Returns:
        float: 基礎分數 (5-100)
    """
    if rank < 1:
        rank = 1
    if rank > MAX_RANK:
        rank = MAX_RANK
    
    return BASE_SCORE - (rank - 1) * RANK_DECAY


def calculate_top100_ratio(sector_stocks: list, top100_stocks: list) -> float:
    """
    計算族群的 Top100 成分股比例
    
    Args:
        sector_stocks: 該族群的成分股代碼列表
        top100_stocks: Top100 成交值股票代碼列表
        
    Returns:
        float: Top100 比例 (0-1)
    """
    if not sector_stocks:
        return 0.0
    
    # 轉換為字串確保比對正確
    sector_set = set(str(s) for s in sector_stocks)
    top100_set = set(str(s) for s in top100_stocks)
    
    overlap = sector_set & top100_set
    return len(overlap) / len(sector_set)


def get_top3_gainers(sector_stocks: list, stock_df: pd.DataFrame) -> list:
    """
    取得該族群在 Top100 中漲幅前 3 的成分股
    
    Args:
        sector_stocks: 該族群的成分股代碼列表
        stock_df: 個股資料 DataFrame (需包含 code, name, change, is_top100)
        
    Returns:
        list: [{'code': '2330', 'name': '台積電', 'change': 8.5}, ...]
    """
    if stock_df.empty or not sector_stocks:
        return []
    
    # 轉換為字串
    sector_set = set(str(s) for s in sector_stocks)
    
    # 篩選：成分股 & Top100
    mask = (
        stock_df['code'].astype(str).isin(sector_set) &
        stock_df['is_top100']
    )
    candidates = stock_df[mask].copy()
    
    if candidates.empty:
        return []
    
    # 排序：按漲幅
    candidates = candidates.sort_values('change', ascending=False)
    
    # 取前 3
    top3 = candidates.head(3)
    
    result = []
    for _, row in top3.iterrows():
        result.append({
            'code': str(row['code']),
            'name': str(row.get('name', '')),
            'change': round(float(row['change']), 2)
        })
    
    return result


def score_fund_flow(rank: int, top100_ratio: float) -> dict:
    """
    資金流向評分
    
    Args:
        rank: 資金流向排名 (1-20)
        top100_ratio: top100 成分股比例
        
    Returns:
        dict: {'base_score': 100, 'final_score': 60, 'top100_ratio': 0.6}
    """
    base_score = calculate_rank_score(rank)
    final_score = base_score * top100_ratio
    
    return {
        'dimension': 'fund_flow',
        'rank': rank,
        'base_score': round(base_score, 1),
        'top100_ratio': round(top100_ratio, 3),
        'final_score': round(final_score, 1)
    }


def score_margin(rank: int, top100_ratio: float) -> dict:
    """
    融資增減評分
    
    Args:
        rank: 融資增減排名 (1-20)
        top100_ratio: top100 成分股比例
        
    Returns:
        dict: 評分結果
    """
    base_score = calculate_rank_score(rank)
    final_score = base_score * top100_ratio
    
    return {
        'dimension': 'margin',
        'rank': rank,
        'base_score': round(base_score, 1),
        'top100_ratio': round(top100_ratio, 3),
        'final_score': round(final_score, 1)
    }


def score_ratio(rank: int, top100_ratio: float) -> dict:
    """
    券資比評分
    
    Args:
        rank: 券資比排名 (1-20)
        top100_ratio: top100 成分股比例
        
    Returns:
        dict: 評分結果
    """
    base_score = calculate_rank_score(rank)
    final_score = base_score * top100_ratio
    
    return {
        'dimension': 'ratio',
        'rank': rank,
        'base_score': round(base_score, 1),
        'top100_ratio': round(top100_ratio, 3),
        'final_score': round(final_score, 1)
    }


def process_cmoney_rankings(cmoney_df: pd.DataFrame, sector_mapping: dict, stock_df: pd.DataFrame) -> dict:
    """
    處理 CMoney 資料並計算三維度評分
    
    Args:
        cmoney_df: CMoney 族群資料
        sector_mapping: 族群 → 成分股映射
        stock_df: 個股資料 (含 is_top100)
        
    Returns:
        dict: {
            'fund_flow': [{'sector': ..., 'score': ..., 'top3': ...}, ...],
            'margin': [...],
            'ratio': [...],
            'multi_dimension': [...]  # 三維度都上榜的族群
        }
    """
    if cmoney_df.empty:
        return {'fund_flow': [], 'margin': [], 'ratio': [], 'multi_dimension': []}
    
    # 取得 top100 股票列表
    top100_stocks = stock_df[stock_df['is_top100']]['code'].astype(str).tolist() if not stock_df.empty else []
    
    # 三個維度結果
    results = {
        'fund_flow': [],
        'margin': [],
        'ratio': [],
        'multi_dimension': []
    }
    
    # 追蹤每個族群在哪些維度上榜
    sector_dimensions = {}
    
    # 處理資金流向
    fund_flow_df = cmoney_df[cmoney_df['FundFlow'].notna() & (cmoney_df['FundFlow'] != 0)].copy()
    fund_flow_df = fund_flow_df.sort_values('FundFlow', ascending=False).head(20)
    
    for rank, (_, row) in enumerate(fund_flow_df.iterrows(), 1):
        sector_name = row['SectorName']
        sector_stocks = get_sector_stocks(sector_name, sector_mapping)
        top100_ratio = calculate_top100_ratio(sector_stocks, top100_stocks)
        score = score_fund_flow(rank, top100_ratio)
        top3 = get_top3_gainers(sector_stocks, stock_df)
        
        results['fund_flow'].append({
            'sector': sector_name,
            'score': score,
            'data': {
                'fund_flow': row['FundFlow'] / 100,  # 轉為億
                'price_change': row.get('PriceChange', 0),
                'turnover_change': row.get('TurnoverChange', 0)
            },
            'top3': top3
        })
        
        if sector_name not in sector_dimensions:
            sector_dimensions[sector_name] = {'fund_flow': None, 'margin': None, 'ratio': None}
        sector_dimensions[sector_name]['fund_flow'] = score
    
    # 處理融資增減
    margin_df = cmoney_df[cmoney_df['MarginChange'].notna() & (cmoney_df['MarginChange'] != 0)].copy()
    margin_df = margin_df.sort_values('MarginChange', ascending=False).head(20)
    
    for rank, (_, row) in enumerate(margin_df.iterrows(), 1):
        sector_name = row['SectorName']
        sector_stocks = get_sector_stocks(sector_name, sector_mapping)
        top100_ratio = calculate_top100_ratio(sector_stocks, top100_stocks)
        score = score_margin(rank, top100_ratio)
        top3 = get_top3_gainers(sector_stocks, stock_df)
        
        # 計算增減比例
        margin_balance = row.get('MarginBalance', 0)
        margin_change = row.get('MarginChange', 0)
        change_pct = (margin_change / margin_balance * 100) if margin_balance > 0 else 0
        
        results['margin'].append({
            'sector': sector_name,
            'score': score,
            'data': {
                'margin_change': margin_change,
                'margin_balance': margin_balance,
                'change_pct': round(change_pct, 2)
            },
            'top3': top3
        })
        
        if sector_name not in sector_dimensions:
            sector_dimensions[sector_name] = {'fund_flow': None, 'margin': None, 'ratio': None}
        sector_dimensions[sector_name]['margin'] = score
    
    # 處理券資比
    ratio_df = cmoney_df[cmoney_df['ShortMarginRatio'].notna() & (cmoney_df['ShortMarginRatio'] != 0)].copy()
    ratio_df = ratio_df.sort_values('ShortMarginRatio', ascending=False).head(20)
    
    for rank, (_, row) in enumerate(ratio_df.iterrows(), 1):
        sector_name = row['SectorName']
        sector_stocks = get_sector_stocks(sector_name, sector_mapping)
        top100_ratio = calculate_top100_ratio(sector_stocks, top100_stocks)
        score = score_ratio(rank, top100_ratio)
        top3 = get_top3_gainers(sector_stocks, stock_df)
        
        results['ratio'].append({
            'sector': sector_name,
            'score': score,
            'data': {
                'short_margin_ratio': row.get('ShortMarginRatio', 0)
            },
            'top3': top3
        })
        
        if sector_name not in sector_dimensions:
            sector_dimensions[sector_name] = {'fund_flow': None, 'margin': None, 'ratio': None}
        sector_dimensions[sector_name]['ratio'] = score
    
    # 找出三維度都上榜的族群
    for sector_name, dims in sector_dimensions.items():
        dim_count = sum(1 for v in dims.values() if v is not None)
        if dim_count >= 3:
            # 計算平均分數
            scores = [v['final_score'] for v in dims.values() if v is not None]
            avg_score = sum(scores) / len(scores)
            
            sector_stocks = get_sector_stocks(sector_name, sector_mapping)
            top3 = get_top3_gainers(sector_stocks, stock_df)
            
            results['multi_dimension'].append({
                'sector': sector_name,
                'dimensions': dims,
                'dim_count': dim_count,
                'avg_score': round(avg_score, 1),
                'top3': top3
            })
    
    # 按平均分數排序多維度族群
    results['multi_dimension'].sort(key=lambda x: x['avg_score'], reverse=True)
    
    # 按最終分數排序各維度
    for dim in ['fund_flow', 'margin', 'ratio']:
        results[dim].sort(key=lambda x: x['score']['final_score'], reverse=True)
    
    return results


if __name__ == "__main__":
    # 測試
    print("=== 測試 cmoney_scorer ===")
    
    # 測試排名分數
    print(f"排名1: {calculate_rank_score(1)}")  # 100
    print(f"排名10: {calculate_rank_score(10)}")  # 55
    print(f"排名20: {calculate_rank_score(20)}")  # 5
    
    # 測試評分
    score = score_fund_flow(1, 0.6)
    print(f"資金流向第1名, top100比例0.6: {score}")
