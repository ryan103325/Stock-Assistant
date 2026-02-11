# -*- coding: utf-8 -*-
"""
族群資金動能策略 V2.0 - 族群分析器
"""

import pandas as pd
import numpy as np


def calculate_sector_metrics(sector_name, member_codes, stock_df, cmoney_row=None):
    """
    計算單一族群的完整統計指標
    
    Args:
        sector_name: 族群名稱
        member_codes: 成員股票代碼列表
        stock_df: 個股快照資料（來自 load_stock_data）
        cmoney_row: CMoney 該族群的資料 (pd.Series, 可選)
        
    Returns:
        dict: SectorMetrics 結構
    """
    # 篩選成員股（進榜的）
    member_df = stock_df[stock_df['code'].isin(member_codes)]
    
    total_stocks = len(member_codes)
    active_stocks = len(member_df)
    active_ratio = active_stocks / total_stocks if total_stocks > 0 else 0
    
    # 計算 Top 50 數量
    top50_count = int(member_df['is_top50'].sum()) if 'is_top50' in member_df.columns else 0
    
    # 預設值
    metrics = {
        'sector_name': sector_name,
        'total_stocks': total_stocks,
        'active_stocks': active_stocks,
        'active_ratio': active_ratio,
        'top50_count': top50_count,
        
        # 漲跌同步性
        'up_count': 0,
        'up_ratio': 0,
        'down_count': 0,
        'median_change': 0,
        'avg_change': 0,
        'max_change': 0,
        'min_change': 0,
        
        # 量能動能
        'avg_volume_ratio': 1.0,
        'surge_count': 0,
        'surge_ratio': 0,
        
        # 價格位置
        'strong_close_count': 0,
        'strong_close_ratio': 0,
        
        # CMoney 資金數據
        'fund_flow': 0,
        'turnover_change': 0,
        'margin_change': 0,
        'short_change': 0,
        'cmoney_price_change': 0,
        
        # 成員股列表
        'member_stocks': []
    }
    
    if active_stocks == 0:
        # 即使沒有進榜股票，仍需填入 CMoney 數據
        if cmoney_row is not None:
            metrics['fund_flow'] = float(cmoney_row.get('FundFlow', 0) or 0)
            metrics['turnover_change'] = float(cmoney_row.get('TurnoverChange', 0) or 0)
            metrics['margin_change'] = float(cmoney_row.get('MarginChange', 0) or 0)
            metrics['short_change'] = float(cmoney_row.get('ShortChange', 0) or 0)
            metrics['cmoney_price_change'] = float(cmoney_row.get('PriceChange', 0) or 0)
        return metrics
    
    # 漲跌同步性
    up_count = int(member_df['is_up'].sum())
    metrics['up_count'] = up_count
    metrics['up_ratio'] = up_count / active_stocks
    metrics['down_count'] = active_stocks - up_count
    metrics['median_change'] = float(member_df['change'].median())
    metrics['avg_change'] = float(member_df['change'].mean())
    metrics['max_change'] = float(member_df['change'].max())
    metrics['min_change'] = float(member_df['change'].min())
    
    # 量能動能
    metrics['avg_volume_ratio'] = float(member_df['volume_ratio'].mean())
    surge_count = int((member_df['volume_ratio'] > 1.5).sum())
    metrics['surge_count'] = surge_count
    metrics['surge_ratio'] = surge_count / active_stocks
    
    # 價格位置
    strong_close_count = int(member_df['is_strong_close'].sum())
    metrics['strong_close_count'] = strong_close_count
    metrics['strong_close_ratio'] = strong_close_count / active_stocks
    
    # CMoney 資金數據
    if cmoney_row is not None:
        metrics['fund_flow'] = float(cmoney_row.get('FundFlow', 0) or 0)
        metrics['turnover_change'] = float(cmoney_row.get('TurnoverChange', 0) or 0)
        metrics['margin_change'] = float(cmoney_row.get('MarginChange', 0) or 0)
        metrics['short_change'] = float(cmoney_row.get('ShortChange', 0) or 0)
        metrics['cmoney_price_change'] = float(cmoney_row.get('PriceChange', 0) or 0)
    
    # 成員股列表（按漲幅排序）
    member_sorted = member_df.sort_values('change', ascending=False)
    member_list = []
    for _, row in member_sorted.iterrows():
        member_list.append({
            'code': row['code'],
            'name': row.get('name', ''),
            'close': row['close'],
            'change': row['change'],
            'volume_ratio': row['volume_ratio'],
            'is_up': row['is_up'],
            'is_strong_close': row['is_strong_close'],
            'is_top50': row.get('is_top50', False),
            'amount_rank': row.get('amount_rank', 999)
        })
    metrics['member_stocks'] = member_list
    
    return metrics


def analyze_all_sectors(stock_df, cmoney_df=None, sector_mapping=None):
    """
    批次分析所有族群
    
    Args:
        stock_df: 個股資料
        cmoney_df: CMoney 族群資料（可選）
        sector_mapping: 族群成員映射 {sector_name: [codes]}
        
    Returns:
        list: [SectorMetrics, ...]
    """
    results = []
    
    if sector_mapping is None or not sector_mapping:
        print("⚠️ 族群映射為空，無法分析")
        return results
    
    # 建立 CMoney 名稱索引
    cmoney_index = {}
    if cmoney_df is not None and not cmoney_df.empty:
        for _, row in cmoney_df.iterrows():
            name = str(row.get('SectorName', '')).strip()
            if name:
                cmoney_index[name] = row
    
    # 遍歷 sector_mapping
    for sector_name, member_codes in sector_mapping.items():
        if not member_codes:
            continue
        
        # 查找對應的 CMoney 資料
        cmoney_row = cmoney_index.get(sector_name, None)
        
        # 計算指標
        metrics = calculate_sector_metrics(
            sector_name, 
            member_codes, 
            stock_df, 
            cmoney_row=cmoney_row
        )
        results.append(metrics)
    
    print(f"📊 分析完成: {len(results)} 個族群")
    if cmoney_index:
        matched = sum(1 for r in results if r.get('fund_flow', 0) != 0)
        print(f"   CMoney 資料匹配: {matched} 個族群")
    return results


if __name__ == "__main__":
    # 簡單測試
    print("=== 測試 sector_analyzer ===")
    
    # 模擬資料
    test_stock_df = pd.DataFrame([
        {'code': '2330', 'close': 600, 'change': 2.5, 'volume_ratio': 1.5, 'is_up': True, 'is_strong_close': True},
        {'code': '3711', 'close': 100, 'change': 3.0, 'volume_ratio': 2.0, 'is_up': True, 'is_strong_close': True},
    ])
    
    test_cmoney_row = pd.Series({
        'SectorName': '半導體',
        'FundFlow': 1000,
        'TurnoverChange': 20,
        'MarginChange': 500,
        'ShortChange': -100,
        'PriceChange': 2.5
    })
    
    metrics = calculate_sector_metrics('半導體', ['2330', '3711', '2303'], test_stock_df, test_cmoney_row)
    print(f"族群: {metrics['sector_name']}")
    print(f"進榜: {metrics['active_stocks']}/{metrics['total_stocks']}")
    print(f"上漲比例: {metrics['up_ratio']:.1%}")
    print(f"中位數漲幅: {metrics['median_change']:.2f}%")
