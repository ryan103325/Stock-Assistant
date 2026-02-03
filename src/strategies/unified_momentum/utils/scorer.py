# -*- coding: utf-8 -*-
"""
族群資金動能策略 V2.0 - 評分引擎
"""

# 篩選門檻（硬編碼，避免導入問題）
MIN_ACTIVE_STOCKS = 2
MIN_UP_RATIO = 0.50
MIN_MEDIAN_CHANGE = 0.5
MIN_AVG_VOLUME_RATIO = 1.0
MIN_TOTAL_SCORE = 40



def calculate_score(metrics):
    """
    計算族群評分（0-100分）
    
    Args:
        metrics: SectorMetrics 字典
        
    Returns:
        dict: 包含 total_score, breakdown, mode, signals
    """
    signals = []
    
    # ========== A. 族群同步性（35分）==========
    # A1. 上漲一致性（15分）
    up_ratio = metrics.get('up_ratio', 0)
    if up_ratio >= 0.85:
        a1 = 15
    elif up_ratio >= 0.75:
        a1 = 12
    elif up_ratio >= 0.65:
        a1 = 9
    elif up_ratio >= 0.50:
        a1 = 5
    else:
        a1 = 0
    
    # A2. 漲幅強度（10分）
    median = metrics.get('median_change', 0)
    if median >= 3.0:
        a2 = 10
    elif median >= 2.0:
        a2 = 7
    elif median >= 1.0:
        a2 = 4
    elif median >= 0:
        a2 = 1
    else:
        a2 = 0
    
    # A3. 活躍參與度（10分）
    active = metrics.get('active_stocks', 0)
    if active >= 6:
        a3 = 10
    elif active >= 5:
        a3 = 8
    elif active >= 4:
        a3 = 6
    elif active >= 3:
        a3 = 4
    elif active >= 2:
        a3 = 2
    else:
        a3 = 0
    
    sync_score = a1 + a2 + a3
    
    if up_ratio >= 0.75:
        signals.append("族群同步")
    
    # ========== B. 資金動能（30分）==========
    # B1. 資金集中（15分）
    fund_flow = metrics.get('fund_flow', 0)
    turnover_change = metrics.get('turnover_change', 0)
    
    if fund_flow > 0:
        b1 = 15
        signals.append("資金集中")
    elif turnover_change > 20:
        b1 = 10
        signals.append("量能放大")
    else:
        b1 = 0
    
    # B2. 量能放大（15分）
    vol_ratio = metrics.get('avg_volume_ratio', 1.0)
    surge_ratio = metrics.get('surge_ratio', 0)
    
    if vol_ratio >= 1.5:
        b2_vol = 10
    elif vol_ratio >= 1.3:
        b2_vol = 7
    elif vol_ratio >= 1.1:
        b2_vol = 4
    else:
        b2_vol = 0
    
    if surge_ratio >= 0.5:
        b2_surge = 5
    elif surge_ratio >= 0.3:
        b2_surge = 3
    else:
        b2_surge = 0
    
    b2 = b2_vol + b2_surge
    momentum_score = b1 + b2
    
    # ========== C. 融資融券訊號（25分）==========
    # C1. 融資進場（15分）
    margin = metrics.get('margin_change', 0)
    if margin > 0:
        c1 = 15
        signals.append("融資進場")
    else:
        c1 = 0
    
    # C2. 空頭回補（10分）
    short = metrics.get('short_change', 0)
    if short < 0:
        c2 = 10
        signals.append("空頭回補")
        # 若同時融資增加，加成
        if margin > 0:
            c2 += 5  # 多空轉換加分（但最多仍是 25）
    else:
        c2 = 0
    
    margin_score = min(c1 + c2, 25)  # 上限 25
    
    # ========== D. 價格位置（10分）==========
    strong_ratio = metrics.get('strong_close_ratio', 0)
    if strong_ratio >= 0.70:
        position_score = 10
    elif strong_ratio >= 0.60:
        position_score = 7
    elif strong_ratio >= 0.50:
        position_score = 4
    else:
        position_score = 0
    
    # ========== 總分與模式判定 ==========
    total_score = sync_score + momentum_score + margin_score + position_score
    
    # 模式分類
    if margin_score >= 15 and sync_score >= 20:
        mode = "主流強勢型"
    elif margin_score >= 15 and sync_score < 20:
        mode = "軋空反彈型"
    elif sync_score >= 25:
        mode = "同步上漲型"
    else:
        mode = "觀望"
    
    return {
        'total_score': round(total_score, 1),
        'breakdown': {
            'sync_score': sync_score,
            'momentum_score': momentum_score,
            'margin_score': margin_score,
            'position_score': position_score
        },
        'mode': mode,
        'signals': signals
    }


def filter_sectors(scored_sectors, min_score=None):
    """
    篩選符合條件的族群
    
    Args:
        scored_sectors: 已評分的族群列表 [{'metrics': ..., 'score': ...}, ...]
        min_score: 最低分數門檻（None 則使用配置）
        
    Returns:
        list: 篩選後的族群（按分數降序）
    """
    if min_score is None:
        min_score = MIN_TOTAL_SCORE
    
    filtered = []
    
    for sector in scored_sectors:
        metrics = sector['metrics']
        score = sector['score']
        
        # 門檻1: 成員股數 >= 2
        if metrics.get('active_stocks', 0) < MIN_ACTIVE_STOCKS:
            continue
        
        # 門檻2: 上漲比例 >= 50%
        if metrics.get('up_ratio', 0) < MIN_UP_RATIO:
            continue
        
        # 門檻3: 中位數漲幅 >= 0.5%
        if metrics.get('median_change', 0) < MIN_MEDIAN_CHANGE:
            continue
        
        # 門檻4: 平均量比 >= 1.0
        if metrics.get('avg_volume_ratio', 0) < MIN_AVG_VOLUME_RATIO:
            continue
        
        # 門檻5: 評分 >= min_score
        if score.get('total_score', 0) < min_score:
            continue
        
        filtered.append(sector)
    
    # 按分數排序
    filtered.sort(key=lambda x: x['score']['total_score'], reverse=True)
    
    print(f"📋 篩選結果: {len(filtered)} 個族群通過")
    return filtered


if __name__ == "__main__":
    # 測試
    print("=== 測試 scorer ===")
    
    test_metrics = {
        'sector_name': 'AI伺服器',
        'total_stocks': 12,
        'active_stocks': 8,
        'active_ratio': 0.67,
        'up_count': 7,
        'up_ratio': 0.875,
        'median_change': 2.3,
        'avg_change': 2.8,
        'avg_volume_ratio': 1.45,
        'surge_ratio': 0.625,
        'strong_close_ratio': 0.75,
        'fund_flow': 12500,
        'margin_change': 350,
        'short_change': -80,
        'turnover_change': 35.5
    }
    
    score = calculate_score(test_metrics)
    print(f"總分: {score['total_score']}")
    print(f"細項: {score['breakdown']}")
    print(f"模式: {score['mode']}")
    print(f"訊號: {score['signals']}")
