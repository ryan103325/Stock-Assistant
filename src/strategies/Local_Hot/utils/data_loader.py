# -*- coding: utf-8 -*-
"""
族群資金動能策略 V2.0 - 資料載入器
"""

import os
import pandas as pd
import numpy as np
from datetime import datetime

# 路徑設定
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SECTOR_DIR = os.path.dirname(SCRIPT_DIR)
STRATEGIES_DIR = os.path.dirname(SECTOR_DIR)
SRC_DIR = os.path.dirname(STRATEGIES_DIR)
DATA_CORE_DIR = os.path.join(SRC_DIR, "data_core")
HISTORY_DIR = os.path.join(DATA_CORE_DIR, "history")
MARKET_META_DIR = os.path.join(DATA_CORE_DIR, "market_meta")


def get_trading_dates(end_date, lookback=10):
    """
    取得往前 N 個交易日的日期列表
    
    Args:
        end_date: 結束日期 (str or datetime)
        lookback: 往前天數
        
    Returns:
        list: 日期列表（由舊到新）
    """
    ref_file = os.path.join(HISTORY_DIR, "2330.csv")
    if not os.path.exists(ref_file):
        print(f"⚠️ 找不到參考檔案: {ref_file}")
        return []
    
    try:
        df = pd.read_csv(ref_file)
        df['Date'] = pd.to_datetime(df['Date'])
        
        if isinstance(end_date, str):
            end_date = pd.to_datetime(end_date.replace('/', '-'))
        
        df = df[df['Date'] <= end_date].sort_values('Date')
        dates = df['Date'].tail(lookback).dt.strftime('%Y-%m-%d').tolist()
        return dates
    except Exception as e:
        print(f"⚠️ 取得交易日曆錯誤: {e}")
        return []


def load_stock_data(date_str, top_n=150):
    """
    載入指定日期的個股行情資料並計算基礎指標
    
    Args:
        date_str: 交易日期，格式 "YYYY/MM/DD" 或 "YYYY-MM-DD"
        top_n: 取成交金額前 N 名
        
    Returns:
        pd.DataFrame: 個股快照資料
    """
    date_str = date_str.replace('/', '-')
    target_date = pd.to_datetime(date_str)
    
    # 取得交易日曆（需往前抓 6 天計算 5 日均量）
    trading_dates = get_trading_dates(target_date, lookback=6)
    if len(trading_dates) < 2:
        print("⚠️ 交易日資料不足")
        return pd.DataFrame()
    
    # 掃描所有股票檔案
    results = []
    stock_files = [f for f in os.listdir(HISTORY_DIR) if f.endswith('.csv') and f[:-4].isdigit()]
    
    for filename in stock_files:
        code = filename[:-4]
        filepath = os.path.join(HISTORY_DIR, filename)
        
        try:
            df = pd.read_csv(filepath)
            if df.empty or len(df) < 2:
                continue
            
            df['Date'] = pd.to_datetime(df['Date'])
            df = df.sort_values('Date')
            
            # 取得目標日資料
            row = df[df['Date'] == target_date]
            if row.empty:
                continue
            
            row = row.iloc[-1]
            
            # 取得前一日資料
            prev_df = df[df['Date'] < target_date].tail(1)
            if prev_df.empty:
                continue
            yesterday = prev_df.iloc[-1]
            
            # 計算 5 日均量
            recent = df[df['Date'] <= target_date].tail(6)
            if len(recent) >= 2:
                avg_volume_5d = recent['Volume'].iloc[:-1].mean()  # 不含今日
            else:
                avg_volume_5d = row['Volume']
            
            # 計算指標
            close = float(row['Close'])
            high = float(row['High'])
            low = float(row['Low'])
            volume = float(row['Volume'])
            yesterday_close = float(yesterday['Close'])
            
            # 成交金額（估算：收盤價 * 成交量）
            amount = close * volume
            
            # 漲跌幅
            change_pct = ((close - yesterday_close) / yesterday_close) * 100 if yesterday_close > 0 else 0
            
            # 量比
            volume_ratio = volume / avg_volume_5d if avg_volume_5d > 0 else 1.0
            
            # 收盤強度
            close_strength = close / high if high > 0 else 0
            
            results.append({
                'code': code,
                'close': close,
                'high': high,
                'low': low,
                'volume': volume,
                'amount': amount,
                'yesterday_close': yesterday_close,
                'change': change_pct,
                'change_pct': change_pct / 100,
                'avg_volume_5d': avg_volume_5d,
                'volume_ratio': volume_ratio,
                'close_strength': close_strength,
                'is_up': change_pct > 0,
                'is_strong_close': close_strength >= 0.90
            })
            
        except Exception as e:
            continue
    
    if not results:
        return pd.DataFrame()
    
    df_result = pd.DataFrame(results)
    
    # 按成交金額排序，取前 top_n 名
    df_result = df_result.sort_values('amount', ascending=False).head(top_n).reset_index(drop=True)
    df_result['amount_rank'] = range(1, len(df_result) + 1)
    
    # 標記 Top 100
    df_result['is_top100'] = df_result['amount_rank'] <= 100
    
    # 載入股票名稱
    try:
        tags_file = os.path.join(MARKET_META_DIR, "master_stock_tags.csv")
        if os.path.exists(tags_file):
            tags_df = pd.read_csv(tags_file, encoding='utf-8-sig')
            tags_df['Code'] = tags_df['Code'].astype(str)
            name_map = dict(zip(tags_df['Code'], tags_df['Name']))
            df_result['name'] = df_result['code'].map(name_map).fillna('')
            print(f"   股票名稱載入: {df_result['name'].notna().sum()} 支")
    except Exception as e:
        df_result['name'] = ''
        print(f"⚠️ 載入股票名稱失敗: {e}")
    
    print(f"📊 載入 {len(df_result)} 支股票資料 (Top {top_n} by 成交金額)")
    print(f"   其中 Top 100: {df_result['is_top100'].sum()} 支")
    return df_result


def load_sector_cmoney_data(date_str=None):
    """
    載入 CMoney 族群總表資料
    
    Args:
        date_str: 指定日期，None 則自動抓最新檔案
        
    Returns:
        pd.DataFrame: CMoney 族群資料
    """
    # 掃描檔案
    files = [f for f in os.listdir(MARKET_META_DIR) 
             if f.startswith("sector_momentum_") and f.endswith(".csv")]
    
    if not files:
        print("❌ 找不到 CMoney 族群資料檔案")
        return pd.DataFrame()
    
    # 按日期排序，取最新
    files.sort(reverse=True)
    
    if date_str:
        # 嘗試匹配指定日期
        date_key = date_str.replace('/', '').replace('-', '')
        matched = [f for f in files if date_key in f]
        if matched:
            target_file = matched[0]
        else:
            target_file = files[0]
    else:
        target_file = files[0]
    
    filepath = os.path.join(MARKET_META_DIR, target_file)
    print(f"📂 載入 CMoney 資料: {target_file}")
    
    try:
        df = pd.read_csv(filepath, encoding='utf-8-sig')
        
        # 過濾集團關鍵字
        df = df[~df['SectorName'].str.contains('集團', na=False)]
        
        # 標準化欄位
        for col in ['FundFlow', 'TurnoverChange', 'MarginChange', 'ShortChange', 'PriceChange']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        print(f"   族群數: {len(df)}")
        return df
        
    except Exception as e:
        print(f"❌ 載入 CMoney 資料錯誤: {e}")
        return pd.DataFrame()


def load_sector_member_mapping():
    """
    建立族群名稱 → 成員股票代碼的映射表
    使用 cmoney_all_tags.csv 作為主要來源
    
    Returns:
        dict: {sector_name: [code1, code2, ...]}
    """
    # 優先使用 CMoney 標籤
    cmoney_file = os.path.join(MARKET_META_DIR, "cmoney_all_tags.csv")
    
    if os.path.exists(cmoney_file):
        try:
            df = pd.read_csv(cmoney_file, encoding='utf-8-sig')
            
            # 建立映射：族群 → 股票列表
            mapping = {}
            
            for _, row in df.iterrows():
                tag_name = str(row.get('TagName', '')).strip()
                stock_code = str(row.get('StockCode', '')).strip()
                
                if not tag_name or not stock_code or tag_name == 'nan' or stock_code == 'nan':
                    continue
                
                if tag_name not in mapping:
                    mapping[tag_name] = []
                if stock_code not in mapping[tag_name]:
                    mapping[tag_name].append(stock_code)
            
            print(f"📋 從 cmoney_all_tags 建立 {len(mapping)} 個族群映射")
            return mapping
            
        except Exception as e:
            print(f"⚠️ 載入 cmoney_all_tags 錯誤: {e}")
    
    # 備用：使用 master_stock_tags
    tags_file = os.path.join(MARKET_META_DIR, "master_stock_tags.csv")
    
    if not os.path.exists(tags_file):
        print(f"❌ 找不到標籤總表: {tags_file}")
        return {}
    
    try:
        df = pd.read_csv(tags_file, encoding='utf-8-sig')
        
        # 建立映射：族群 → 股票列表
        mapping = {}
        
        for _, row in df.iterrows():
            code = str(row.get('Code', '')).strip()
            if not code:
                continue
            
            # 優先使用 MainGroup
            main_group = str(row.get('MainGroup', '')).strip()
            if main_group and main_group != 'nan':
                if main_group not in mapping:
                    mapping[main_group] = []
                mapping[main_group].append(code)
            
            # 使用 SubTags（CMoney 標籤，可能是逗號分隔）
            sub_tags = str(row.get('SubTags', '')).strip()
            if sub_tags and sub_tags != 'nan':
                for tag in sub_tags.split(','):
                    tag = tag.strip()
                    if tag:
                        if tag not in mapping:
                            mapping[tag] = []
                        if code not in mapping[tag]:
                            mapping[tag].append(code)
            
            # 使用 Industry（MoneyDJ 產業）
            industry = str(row.get('Industry', '')).strip()
            if industry and industry != 'nan':
                if industry not in mapping:
                    mapping[industry] = []
                if code not in mapping[industry]:
                    mapping[industry].append(code)
        
        print(f"📋 從 master_stock_tags 建立 {len(mapping)} 個族群映射")
        return mapping
        
    except Exception as e:
        print(f"❌ 載入標籤總表錯誤: {e}")
        return {}


if __name__ == "__main__":
    # 測試
    print("=== 測試 data_loader ===")
    
    # 測試交易日曆
    dates = get_trading_dates("2026-01-27", lookback=5)
    print(f"交易日: {dates}")
    
    # 測試族群映射
    mapping = load_sector_member_mapping()
    print(f"族群數: {len(mapping)}")
    if mapping:
        sample = list(mapping.items())[:3]
        for name, codes in sample:
            print(f"  {name}: {len(codes)} 支")
    
    # 測試 CMoney 資料
    cmoney_df = load_sector_cmoney_data()
    if not cmoney_df.empty:
        print(f"CMoney 族群數: {len(cmoney_df)}")
