# -*- coding: utf-8 -*-
"""
生成分層標籤總表 (master_stock_tags.csv) - 整合版
資料來源：CMoney (Category + Concept) + MoneyDJ (補充)

輸出格式（新版）：
- Code: 股票代碼
- Name: 股票名稱
- MainGroup: 主族群（整合後，可多個）
- SubTags: 次標籤（CMoney原始）
- Industry: 產業別（MoneyDJ）
- GroupSize: 各主族群的股票數量
"""
import os
import sys
import pandas as pd
from collections import Counter

# === 路徑設定 ===
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))  # src
DATA_DIR = os.path.join(SRC_DIR, "data_core")  # src/data_core
MARKET_META_DIR = os.path.join(DATA_DIR, "market_meta")

# group_mapping.py 現在與本檔案在同一目錄，不需要 sys.path 設定


# 輸入檔案
CMONEY_FILE = os.path.join(MARKET_META_DIR, "cmoney_all_tags.csv")
MONEYDJ_FILE = os.path.join(MARKET_META_DIR, "moneydj_industries.csv")

# 輸出檔案
OUTPUT_FILE = os.path.join(MARKET_META_DIR, "master_stock_tags.csv")


def load_cmoney():
    """載入 CMoney 資料 (Category + Concept)"""
    stock_tags = {}
    
    if not os.path.exists(CMONEY_FILE):
        print(f"⚠️ 找不到 {CMONEY_FILE}")
        return stock_tags
    
    df = pd.read_csv(CMONEY_FILE, dtype={'StockCode': str})
    
    for _, row in df.iterrows():
        code = str(row['StockCode']).strip()
        tag_name = str(row['TagName']).strip()
        
        if code not in stock_tags:
            stock_tags[code] = {"name": "", "tags": set()}
        
        # 從 CMoney 取名稱
        stock_name = str(row.get('StockName', '')).strip()
        if stock_name and not stock_tags[code]["name"]:
            stock_tags[code]["name"] = stock_name
        
        stock_tags[code]["tags"].add(tag_name)
    
    print(f"✅ CMoney: {len(stock_tags)} 檔")
    return stock_tags


def load_moneydj():
    """載入 MoneyDJ 產業資料（作為補充）"""
    stock_data = {}
    
    if not os.path.exists(MONEYDJ_FILE):
        print(f"⚠️ 找不到 {MONEYDJ_FILE}")
        return stock_data
    
    # MoneyDJ 是變長 CSV，手動解析
    with open(MONEYDJ_FILE, 'r', encoding='utf-8-sig') as f:
        lines = f.readlines()
    
    start_idx = 1 if lines and "Code" in lines[0] else 0
    
    for line in lines[start_idx:]:
        if not line.strip():
            continue
        parts = line.strip().split(',')
        if len(parts) < 3:
            continue
        
        code = parts[0].strip()
        name = parts[1].strip()
        tags = [p.strip() for p in parts[2:] if p.strip()]
        
        stock_data[code] = {"name": name, "tags": set(tags)}
    
    print(f"✅ MoneyDJ: {len(stock_data)} 檔")
    return stock_data


def integrate_tags_to_groups(raw_tags: set) -> tuple:
    """
    將原始標籤整合成主族群
    
    Args:
        raw_tags: CMoney 原始標籤集合
        
    Returns:
        (main_groups, sub_tags): 主族群集合, 次標籤集合
    """
    from group_mapping import GROUP_MAPPING, auto_classify_tag
    
    main_groups = set()
    sub_tags = set()
    
    for tag in raw_tags:
        # 檢查這個標籤屬於哪個主族群
        matched = False
        for group_name, keywords in GROUP_MAPPING.items():
            # 處理新版結構（dict）和舊版結構（list）
            kw_list = keywords.get("keywords", []) if isinstance(keywords, dict) else keywords
            if tag in kw_list:
                main_groups.add(group_name)
                sub_tags.add(tag)
                matched = True
                break
        
        # 如果沒匹配到，嘗試自動分類
        if not matched:
            suggested_groups = auto_classify_tag(tag, use_ai=False)
            for suggested in suggested_groups:
                if suggested not in ["傳產其他", "科技其他", "其他"]:
                    main_groups.add(suggested)
            sub_tags.add(tag)  # 不管有沒有匹配，原始標籤都保留
    
    return main_groups, sub_tags


def get_final_groups(cmoney_tags: set, moneydj_industries: set, stock_code: str = "") -> tuple:
    """
    完整的族群分類邏輯（多層 Fallback）
    
    優先順序：
    1. CMoney 標籤 → GROUP_MAPPING 對照
    2. CMoney 標籤 → AUTO_MATCH_KEYWORDS 關鍵字匹配
    3. MoneyDJ 產業 → MONEYDJ_INDUSTRY_MAPPING 對照表
    4. MoneyDJ 產業 → AUTO_MATCH_KEYWORDS 關鍵字匹配
    5. 最後標記為「未分類」（但會在報告中顯示）
    
    Args:
        cmoney_tags: CMoney 原始標籤集合
        moneydj_industries: MoneyDJ 產業別集合
        stock_code: 股票代碼（用於除錯）
        
    Returns:
        (main_groups, sub_tags): 主族群集合, 次標籤集合
    """
    from group_mapping import classify_by_moneydj_industry, auto_classify_tag
    
    main_groups = set()
    sub_tags = set()
    
    # ==========================================
    # 階段 1: 處理 CMoney 標籤
    # ==========================================
    if cmoney_tags:
        main_groups, sub_tags = integrate_tags_to_groups(cmoney_tags)
    
    # ==========================================
    # 階段 2: 如果沒有族群，處理 MoneyDJ 產業
    # ==========================================
    if not main_groups and moneydj_industries:
        # 2.1 使用 MoneyDJ 產業對照表
        main_groups = classify_by_moneydj_industry(moneydj_industries)
        
        # 2.2 如果對照表也沒匹配到，嘗試關鍵字匹配
        if not main_groups:
            for industry in moneydj_industries:
                suggested_groups = auto_classify_tag(industry, use_ai=False)
                for suggested in suggested_groups:
                    # 只接受明確的分類，排除「其他」類
                    if suggested not in ["傳產其他", "科技其他", "其他"]:
                        main_groups.add(suggested)
        
        # 2.3 如果還是沒有，至少根據產業名稱給個大分類
        if not main_groups:
            industry_text = " ".join(moneydj_industries).lower()
            
            # 判斷是否為科技類
            tech_keywords = ["半導體", "電子", "ic", "光電", "電腦", "通訊", "網路", "資訊"]
            if any(kw in industry_text for kw in tech_keywords):
                main_groups.add("科技其他")
            # 判斷是否為金融類
            elif any(kw in industry_text for kw in ["金融", "銀行", "保險", "證券"]):
                main_groups.add("金融")
            # 判斷是否為航運類
            elif any(kw in industry_text for kw in ["航運", "海運", "空運", "物流"]):
                main_groups.add("航運")
            # 其他傳統產業
            else:
                main_groups.add("傳產其他")
    
    # ==========================================
    # 階段 3: 最後兜底（完全無資料）
    # ==========================================
    if not main_groups:
        main_groups.add("未分類")
    
    return main_groups, sub_tags


def analyze_classification_quality(output_rows: list) -> dict:
    """
    分析分類品質
    
    Args:
        output_rows: 輸出的資料列表
        
    Returns:
        統計資訊字典
    """
    total = len(output_rows)
    
    # 統計各種情況
    has_cmoney = sum(1 for r in output_rows if r["SubTags"])
    has_moneydj = sum(1 for r in output_rows if r["Industry"])
    has_main_group = sum(1 for r in output_rows if r["MainGroup"])
    
    # 統計分類來源
    cmoney_only = sum(1 for r in output_rows if r["SubTags"] and not r["Industry"])
    moneydj_only = sum(1 for r in output_rows if r["Industry"] and not r["SubTags"])
    both = sum(1 for r in output_rows if r["SubTags"] and r["Industry"])
    
    # 統計族群類型
    unclassified = sum(1 for r in output_rows if "未分類" in r["MainGroup"])
    fallback_tech = sum(1 for r in output_rows if r["MainGroup"] == "科技其他")
    fallback_traditional = sum(1 for r in output_rows if r["MainGroup"] == "傳產其他")
    precise = total - unclassified - fallback_tech - fallback_traditional
    
    return {
        "total": total,
        "has_cmoney": has_cmoney,
        "has_moneydj": has_moneydj,
        "has_main_group": has_main_group,
        "cmoney_only": cmoney_only,
        "moneydj_only": moneydj_only,
        "both": both,
        "unclassified": unclassified,
        "fallback_tech": fallback_tech,
        "fallback_traditional": fallback_traditional,
        "precise": precise
    }


def main():
    print("🚀 開始生成分層標籤總表（整合版）...")
    
    # 1. 載入資料來源
    cmoney_data = load_cmoney()
    moneydj_data = load_moneydj()
    
    # 2. 合併股票代碼
    all_codes = set(cmoney_data.keys()) | set(moneydj_data.keys())
    print(f"📊 總計: {len(all_codes)} 檔股票")
    
    # 3. 整理輸出（第一輪：生成基本資料）
    output_rows = []
    
    for code in sorted(all_codes):
        # 取得股名（優先 CMoney，其次 MoneyDJ）
        name = cmoney_data.get(code, {}).get("name", "") or moneydj_data.get(code, {}).get("name", "")
        
        # CMoney 原始標籤
        raw_tags = cmoney_data.get(code, {}).get("tags", set())
        
        # MoneyDJ 產業別
        industries = set(moneydj_data.get(code, {}).get("tags", set()))
        
        # ✨ 使用完整分類邏輯（整合 CMoney + MoneyDJ）
        main_groups, sub_tags = get_final_groups(raw_tags, industries, code)
        
        # 轉換回 sorted list 以便輸出
        industries_sorted = sorted(industries)
        
        if not name and not main_groups and not industries:
            continue
        
        output_rows.append({
            "Code": code,
            "Name": name,
            "MainGroup": ", ".join(sorted(main_groups)) if main_groups else "",  # ✨ 主族群
            "SubTags": ", ".join(sorted(sub_tags)) if sub_tags else "",          # 次標籤
            "Industry": ", ".join(industries_sorted) if industries_sorted else ""  # MoneyDJ 產業
        })
    
    # 4. 計算族群股票數（第二輪：統計）
    print("📊 統計各族群股票數量...")
    group_counter = Counter()
    
    for row in output_rows:
        if row["MainGroup"]:
            groups = [g.strip() for g in row["MainGroup"].split(",") if g.strip()]
            for g in groups:
                group_counter[g] += 1
    
    # 5. 加入 GroupSize 欄位（第三輪：補充）
    for row in output_rows:
        if row["MainGroup"]:
            groups = [g.strip() for g in row["MainGroup"].split(",") if g.strip()]
            sizes = [str(group_counter.get(g, 0)) for g in groups]
            row["GroupSize"] = ", ".join(sizes)
        else:
            row["GroupSize"] = ""
    
    # 6. 輸出 CSV
    df_out = pd.DataFrame(output_rows)
    df_out.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')
    
    print(f"\n✅ 完成！輸出檔案: {OUTPUT_FILE}")
    print(f"   共 {len(df_out)} 檔股票")
    print(f"   {len(group_counter)} 個主族群")
    
    # 7. 統計摘要
    has_main = df_out[df_out['MainGroup'] != ''].shape[0]
    has_industry = df_out[df_out['Industry'] != ''].shape[0]
    has_both = df_out[(df_out['MainGroup'] != '') & (df_out['Industry'] != '')].shape[0]
    
    print(f"\n📊 統計:")
    print(f"   有 MainGroup: {has_main} 檔 ({has_main/len(df_out)*100:.1f}%)")
    print(f"   有 Industry: {has_industry} 檔 ({has_industry/len(df_out)*100:.1f}%)")
    print(f"   兩者都有: {has_both} 檔")
    
    # 8. 顯示主族群統計 (Top 20)
    print(f"\n📊 主族群統計 (Top 20):")
    for group, count in group_counter.most_common(20):
        print(f"   {group}: {count} 檔")
    
    # 9. 範例輸出
    print("\n📋 範例輸出 (前 10 筆):")
    print(df_out.head(10).to_string(index=False))
    
    # 10. 檢查未分類標籤
    print("\n🔍 檢查未分類標籤...")
    try:
        from group_mapping import find_unclassified_tags
        find_unclassified_tags(verbose=True)
    except Exception as e:
        print(f"⚠️ 無法執行未分類檢查: {e}")
    
    # 11. ✨ 分析分類品質
    print("\n" + "="*60)
    print("📊 分類品質分析")
    print("="*60)
    
    quality = analyze_classification_quality(output_rows)
    
    print(f"\n📌 資料來源統計:")
    print(f"   總股票數: {quality['total']}")
    print(f"   有 CMoney 標籤: {quality['has_cmoney']} ({quality['has_cmoney']/quality['total']*100:.1f}%)")
    print(f"   有 MoneyDJ 產業: {quality['has_moneydj']} ({quality['has_moneydj']/quality['total']*100:.1f}%)")
    print(f"   兩者都有: {quality['both']} ({quality['both']/quality['total']*100:.1f}%)")
    print(f"   僅 CMoney: {quality['cmoney_only']}")
    print(f"   僅 MoneyDJ: {quality['moneydj_only']}")
    
    print(f"\n📌 分類結果統計:")
    print(f"   已分類: {quality['has_main_group']} ({quality['has_main_group']/quality['total']*100:.1f}%)")
    print(f"   ├─ 精準分類: {quality['precise']} ({quality['precise']/quality['total']*100:.1f}%)")
    print(f"   ├─ 科技其他: {quality['fallback_tech']} ({quality['fallback_tech']/quality['total']*100:.1f}%)")
    print(f"   ├─ 傳產其他: {quality['fallback_traditional']} ({quality['fallback_traditional']/quality['total']*100:.1f}%)")
    print(f"   └─ 未分類: {quality['unclassified']} ({quality['unclassified']/quality['total']*100:.1f}%)")
    
    # 顯示未分類的股票（如果有）
    if quality['unclassified'] > 0:
        print(f"\n⚠️ 未分類股票清單:")
        unclassified_stocks = df_out[df_out['MainGroup'].str.contains('未分類', na=False)]
        print(unclassified_stocks[['Code', 'Name', 'SubTags', 'Industry']].head(20).to_string(index=False))
        if len(unclassified_stocks) > 20:
            print(f"   ... 還有 {len(unclassified_stocks) - 20} 筆")


if __name__ == "__main__":
    main()
