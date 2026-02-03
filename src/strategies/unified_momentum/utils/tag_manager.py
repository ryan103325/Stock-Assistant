# -*- coding: utf-8 -*-
"""
統一動能策略 - 標籤管理器
處理 CMoney 標籤 + 動態補全
"""

import os
import pandas as pd

# 路徑設定
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
UNIFIED_DIR = os.path.dirname(SCRIPT_DIR)
STRATEGIES_DIR = os.path.dirname(UNIFIED_DIR)
SRC_DIR = os.path.dirname(STRATEGIES_DIR)
DATA_CORE_DIR = os.path.join(SRC_DIR, "data_core")
MARKET_META_DIR = os.path.join(DATA_CORE_DIR, "market_meta")


def load_cmoney_tags():
    """
    載入 CMoney 標籤資料
    
    Returns:
        dict: {stock_code: [tag1, tag2, ...]}
    """
    cmoney_file = os.path.join(MARKET_META_DIR, "cmoney_all_tags.csv")
    
    if not os.path.exists(cmoney_file):
        print(f"❌ 找不到 CMoney 標籤檔案: {cmoney_file}")
        return {}
    
    try:
        df = pd.read_csv(cmoney_file, dtype=str, encoding='utf-8-sig')
        
        # 建立映射：股票代碼 → 標籤列表
        mapping = {}
        for _, row in df.iterrows():
            code = str(row.get('StockCode', '')).strip()
            tag = str(row.get('TagName', '')).strip()
            
            if code and tag and tag != 'nan':
                if code not in mapping:
                    mapping[code] = []
                if tag not in mapping[code]:
                    mapping[code].append(tag)
        
        print(f"📋 載入 CMoney 標籤: {len(mapping)} 支股票")
        return mapping
        
    except Exception as e:
        print(f"❌ 載入 CMoney 標籤錯誤: {e}")
        return {}


def load_master_tags():
    """
    載入 master_stock_tags.csv 作為備用標籤來源
    
    Returns:
        dict: {stock_code: {'MainGroup': [...], 'SubTags': [...]}}
    """
    master_file = os.path.join(MARKET_META_DIR, "master_stock_tags.csv")
    
    if not os.path.exists(master_file):
        print(f"⚠️ 找不到 master_stock_tags.csv")
        return {}
    
    try:
        df = pd.read_csv(master_file, dtype=str, encoding='utf-8-sig')
        
        mapping = {}
        for _, row in df.iterrows():
            code = str(row.get('Code', '')).strip()
            if not code:
                continue
            
            main_group = str(row.get('MainGroup', '')).strip()
            sub_tags = str(row.get('SubTags', '')).strip()
            
            mapping[code] = {
                'MainGroup': [g.strip() for g in main_group.split(',') if g.strip() and g.strip() != 'nan'],
                'SubTags': [t.strip() for t in sub_tags.split(',') if t.strip() and t.strip() != 'nan']
            }
        
        return mapping
        
    except Exception as e:
        print(f"⚠️ 載入 master_stock_tags 錯誤: {e}")
        return {}


def calculate_sector_median(stock_df, sector_stocks):
    """
    計算族群的中位數漲幅
    
    Args:
        stock_df: 個股資料 DataFrame
        sector_stocks: 該族群的股票代碼列表
    
    Returns:
        float: 中位數漲幅
    """
    sector_df = stock_df[stock_df['code'].isin(sector_stocks)]
    if sector_df.empty:
        return 0.0
    return sector_df['change'].median()


def find_best_fit_tag(stock_code, stock_change, candidate_tags, cmoney_tags, stock_df):
    """
    為股票找到最佳歸屬標籤（最佳歸屬演算法）
    
    Args:
        stock_code: 股票代碼
        stock_change: 股票漲幅
        candidate_tags: 候選標籤列表
        cmoney_tags: CMoney 標籤映射（用於計算族群中位數）
        stock_df: 個股資料 DataFrame
    
    Returns:
        str or None: 最佳標籤，若無合適則返回 None
    """
    # 反向映射：標籤 → 股票列表
    tag_to_stocks = {}
    for code, tags in cmoney_tags.items():
        for tag in tags:
            if tag not in tag_to_stocks:
                tag_to_stocks[tag] = []
            tag_to_stocks[tag].append(code)
    
    best_tag = None
    min_diff = float('inf')
    
    for tag in candidate_tags:
        # 只考慮 CMoney 中存在的標籤
        if tag not in tag_to_stocks:
            continue
        
        # 計算該標籤族群的中位數漲幅（排除當前股票）
        sector_stocks = [s for s in tag_to_stocks[tag] if s != stock_code]
        if not sector_stocks:
            continue
        
        sector_median = calculate_sector_median(stock_df, sector_stocks)
        diff = abs(stock_change - sector_median)
        
        if diff < min_diff:
            min_diff = diff
            best_tag = tag
    
    # 只有差異小於閾值才返回
    MAX_DIFF = 3.0  # 最大允許差異 3%
    if best_tag and min_diff < MAX_DIFF:
        return best_tag
    
    return None


def build_unified_mapping(stock_df, cmoney_tags):
    """
    建立統一標籤映射（CMoney + 動態補全）
    
    Args:
        stock_df: 個股資料 DataFrame
        cmoney_tags: CMoney 標籤映射 {code: [tags]}
    
    Returns:
        dict: {tag: [stock_codes]}
    """
    # 反向映射：標籤 → 股票列表
    tag_to_stocks = {}
    
    # 1. 先加入所有 CMoney 標籤
    for code, tags in cmoney_tags.items():
        for tag in tags:
            if tag not in tag_to_stocks:
                tag_to_stocks[tag] = []
            if code not in tag_to_stocks[tag]:
                tag_to_stocks[tag].append(code)
    
    # 2. 找出缺漏的股票
    all_stocks = set(stock_df['code'].tolist())
    cmoney_stocks = set(cmoney_tags.keys())
    missing_stocks = all_stocks - cmoney_stocks
    
    if missing_stocks:
        print(f"🔍 發現 {len(missing_stocks)} 支股票未在 CMoney 中，嘗試動態分類...")
        
        # 載入 master_stock_tags 作為候選來源
        master_tags = load_master_tags()
        
        assigned_count = 0
        for code in missing_stocks:
            # 取得該股票的漲幅
            stock_row = stock_df[stock_df['code'] == code]
            if stock_row.empty:
                continue
            stock_change = stock_row.iloc[0]['change']
            
            # 從 master_stock_tags 取得候選標籤
            candidate_tags = []
            if code in master_tags:
                candidate_tags.extend(master_tags[code]['MainGroup'])
                candidate_tags.extend(master_tags[code]['SubTags'])
            
            if not candidate_tags:
                continue
            
            # 找到最佳歸屬
            best_tag = find_best_fit_tag(code, stock_change, candidate_tags, cmoney_tags, stock_df)
            
            if best_tag:
                if best_tag not in tag_to_stocks:
                    tag_to_stocks[best_tag] = []
                tag_to_stocks[best_tag].append(code)
                assigned_count += 1
        
        print(f"   成功動態分類: {assigned_count} 支股票")
    
    return tag_to_stocks
