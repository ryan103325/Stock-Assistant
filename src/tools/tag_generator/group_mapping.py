"""
族群整合模組 - 將 master_stock_tags.csv 的標籤整合為簡化族群
"""

import os
import pandas as pd

# 族群整合對照表：key = 簡化名稱, value = 原始標籤列表 (會比對 MainTags 欄位)
GROUP_MAPPING = {
    "AI": [
        "AI人工智慧", "AI伺服器", "ChatGPT", "TPU", "HPC", 
        "ASIC", "IP/ASIC", "矽智財IP"
    ],
    "記憶體": [
        "記憶體", "DRAM", "DRAM銷售", "FLASH", "記憶體IC設計",
        "IC-DRAM製造", "IC-製造", "非揮發性記憶體"
    ],
    "被動元件": [
        "被動元件", "電阻", "電容", "電感", "MLCC", 
        "鋁質電容", "鉭質電容", "變壓器", "保護元件"
    ],
    "伺服器": [
        "伺服器", "AI伺服器", "雲端", "資料中心"
    ],
    "散熱": [
        "散熱模組", "散熱零組件", "散熱"
    ],
    "PCB": [
        "PCB", "PCB-製造", "PCB-材料設備", "IC載板", "ABF", "銅箔基板"
    ],
    "IC設計": [
        "IC-設計", "IC設計", "ASIC"
    ],
    "IC代工": [
        "IC-代工", "IC代工", "CoWoS"
    ],
    "封測": [
        "IC-封測", "IC封測"
    ],
    "光通訊": [
        "光通訊", "光纖", "矽光子"
    ],
    "電動車": [
        "電動車", "MIH", "Tesla特斯拉", "鴻海MIH電動車平台",
        "車用電子", "汽車零組件"
    ],
    "網通": [
        "網通", "5G", "O-RAN", "WiFi 6", "通訊設備"
    ],
    "面板": [
        "LCD-TFT面板", "Micro LED", "Mini LED", "顯示器", "OLED"
    ],
    "半導體設備": [
        "IC-半導體設備", "儀器設備工程", "CoWoS"
    ],
    "航運": [
        "航運", "貨櫃航運", "散裝航運"
    ],
    "金融": [
        "金控", "銀行", "保險", "證券"
    ],
    "蘋果供應鏈": [
        "Apple蘋果", "iPhone", "Airpods"
    ],
    "電源供應器": [
        "電源供應器", "BBU"
    ],
    "連接器": [
        "連接器", "連接元件", "Type-c"
    ],
}

# ==========================================
# MoneyDJ 產業別對照表
# ==========================================
# 用於將 MoneyDJ 的產業分類對應到我們的族群系統
# 當股票沒有 CMoney 標籤時，使用此對照表進行分類

MONEYDJ_INDUSTRY_MAPPING = {
    # === 電子科技類 ===
    
    # 半導體相關
    "半導體業": "IC設計",
    "IC製造業": "IC代工",
    "IC設計業": "IC設計",
    "IC封測業": "封測",
    "IC通路業": "電子通路",
    "半導體設備業": "半導體設備",
    "晶圓代工業": "IC代工",
    "IC載板業": "PCB",
    
    # 電腦與週邊
    "電腦及週邊設備業": "伺服器",
    "資訊服務業": "伺服器",
    "雲端服務業": "伺服器",
    
    # 光電與顯示
    "光電業": "面板",
    "顯示器業": "面板",
    "LED業": "面板",
    "觸控面板業": "面板",
    "背光模組業": "面板",
    
    # 通訊網路
    "通信網路業": "網通",
    "網路通訊業": "網通",
    "無線通訊業": "網通",
    "電信服務業": "電信服務",
    "衛星通訊業": "網通",
    
    # 電子零組件
    "電子零組件業": "被動元件",
    "被動元件業": "被動元件",
    "電阻器業": "被動元件",
    "電容器業": "被動元件",
    "連接器業": "連接器",
    "連接線業": "連接器",
    "電源供應器業": "電源供應器",
    "散熱模組業": "散熱",
    
    # PCB 相關
    "印刷電路板業": "PCB",
    "PCB業": "PCB",
    "軟板業": "PCB",
    "硬板業": "PCB",
    "HDI板業": "PCB",
    
    # 其他電子
    "電子通路業": "電子通路",
    "電子代理業": "電子通路",
    "測試設備業": "半導體設備",
    
    # === 傳統產業類 ===
    
    # 基礎材料
    "水泥工業": "水泥",
    "水泥業": "水泥",
    "預拌混凝土業": "水泥",
    
    "鋼鐵工業": "鋼鐵",
    "鋼鐵業": "鋼鐵",
    "不鏽鋼業": "鋼鐵",
    "鋼構業": "鋼鐵",
    
    "塑膠工業": "塑膠",
    "塑膠業": "塑膠",
    "塑化業": "塑膠",
    "石化原料業": "塑膠",
    
    "橡膠工業": "橡膠",
    "橡膠業": "橡膠",
    "輪胎業": "橡膠",
    
    # 紡織與成衣
    "紡織纖維": "紡織",
    "紡織業": "紡織",
    "成衣業": "紡織",
    "化纖業": "紡織",
    "紡織製品業": "紡織",
    
    # 食品
    "食品工業": "食品",
    "食品業": "食品",
    "飲料業": "食品",
    "乳製品業": "食品",
    "烘焙業": "食品",
    "水產業": "食品",
    "飼料業": "食品",
    
    # 機械與設備
    "電機機械": "機械",
    "機械業": "機械",
    "工具機業": "機械",
    "產業機械業": "機械",
    "自動化設備業": "機械",
    "CNC業": "機械",
    
    # 建材與營建
    "建材營造業": "營建",
    "建材營造": "營建",
    "營建業": "營建",
    "建設業": "營建",
    "營造業": "營建",
    "玻璃業": "建材",
    "陶瓷業": "建材",
    
    # 化學
    "化學工業": "化學",
    "化學業": "化學",
    "化工業": "化學",
    "特用化學業": "化學",
    "塗料業": "化學",
    
    # 造紙
    "造紙工業": "造紙",
    "造紙業": "造紙",
    "紙業": "造紙",
    
    # 電機電纜
    "電線電纜業": "電機電纜",
    "電纜業": "電機電纜",
    "重電業": "電機電纜",
    "配電設備業": "電機電纜",
    
    # === 運輸與物流 ===
    "航運業": "航運",
    "海運業": "航運",
    "貨櫃航運業": "航運",
    "散裝航運業": "航運",
    "空運業": "航運",
    "物流業": "航運",
    "倉儲業": "航運",
    
    # === 金融保險 ===
    "金融保險業": "金融",
    "金融業": "金融",
    "銀行業": "金融",
    "證券業": "金融",
    "保險業": "金融",
    "金控業": "金融",
    "票券業": "金融",
    "創投業": "金融",
    
    # === 生技醫療 ===
    "生技醫療業": "生技醫療",
    "生技業": "生技醫療",
    "醫療保健業": "生技醫療",
    "製藥業": "生技醫療",
    "醫療器材業": "生技醫療",
    "檢驗檢測業": "生技醫療",
    "長照產業": "生技醫療",
    
    # === 服務與觀光 ===
    "觀光事業": "觀光",
    "觀光業": "觀光",
    "飯店業": "觀光",
    "旅館業": "觀光",
    "餐飲業": "觀光",
    "旅遊業": "觀光",
    
    "貿易百貨業": "百貨零售",
    "百貨業": "百貨零售",
    "零售業": "百貨零售",
    "量販店業": "百貨零售",
    "便利商店業": "百貨零售",
    
    "文化創意業": "運動休閒",
    "運動休閒業": "運動休閒",
    "休閒娛樂業": "運動休閒",
    
    # === 汽車與零組件 ===
    "汽車工業": "電動車",
    "汽車業": "電動車",
    "汽車零組件業": "電動車",
    "車用零組件業": "電動車",
    "電動車業": "電動車",
    
    # === 能源與公用事業 ===
    "油電燃氣業": "傳產其他",
    "電力事業": "傳產其他",
    "瓦斯業": "傳產其他",
    "綠能環保業": "傳產其他",
    "太陽能業": "傳產其他",
    "風力發電業": "傳產其他",
}

# 模組層級快取
_stock_group_map = None
_tags_df = None



def _get_src_root():
    """取得 src 根目錄"""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_stock_tags():
    """載入 master_stock_tags.csv"""
    global _tags_df
    if _tags_df is not None:
        return _tags_df
    
    src_root = _get_src_root()
    tags_path = os.path.join(src_root, "data_core", "market_meta", "master_stock_tags.csv")
    
    if not os.path.exists(tags_path):
        print(f"⚠️ 找不到族群標籤檔: {tags_path}")
        return pd.DataFrame()
    
    _tags_df = pd.read_csv(tags_path, dtype={"Code": str})
    return _tags_df


def build_stock_group_map():
    """
    建立 {股票代碼: [族群列表]} 對照表
    一檔股票可能屬於多個族群
    """
    global _stock_group_map
    if _stock_group_map is not None:
        return _stock_group_map
    
    df = load_stock_tags()
    if df.empty:
        return {}
    
    _stock_group_map = {}
    
    for _, row in df.iterrows():
        code = str(row['Code']).strip()
        main_tags = str(row.get('MainTags', ''))
        
        # 找出這檔股票屬於哪些整合後的族群
        matched_groups = set()
        for group_name, keywords in GROUP_MAPPING.items():
            for kw in keywords:
                if kw in main_tags:
                    matched_groups.add(group_name)
                    break
        
        if matched_groups:
            _stock_group_map[code] = list(matched_groups)
    
    return _stock_group_map


def get_stock_groups(stock_code: str) -> list:
    """
    取得某檔股票所屬的族群列表
    
    Args:
        stock_code: 股票代碼 (如 "2330")
    
    Returns:
        族群名稱列表 (如 ["AI", "IC代工"])
    """
    group_map = build_stock_group_map()
    code = str(stock_code).strip()
    return group_map.get(code, [])


def calculate_group_weights(holdings_df, code_col='股票代號', weight_col='持股權重'):
    """
    計算各族群的總權重
    
    Args:
        holdings_df: 持股明細 DataFrame
        code_col: 股票代號欄位名稱
        weight_col: 權重欄位名稱
    
    Returns:
        dict: {族群名稱: 總權重}
    """
    group_weights = {}
    
    for _, row in holdings_df.iterrows():
        code = str(row[code_col]).strip()
        try:
            weight = float(str(row[weight_col]).replace('%', '').replace(',', ''))
        except:
            weight = 0
        
        groups = get_stock_groups(code)
        for g in groups:
            group_weights[g] = group_weights.get(g, 0) + weight
    
    return group_weights


def calculate_group_stock_changes(holdings_today, holdings_yesterday, 
                                   code_col='股票代號', name_col='股票名稱', 
                                   shares_col='股數'):
    """
    計算各族群內個股的張數變化
    
    Args:
        holdings_today: 今日持股 DataFrame
        holdings_yesterday: 昨日持股 DataFrame
    
    Returns:
        dict: {族群名稱: [(股票名稱, 股票代號, 變化張數), ...]}
    """
    def clean_shares(val):
        try:
            return float(str(val).replace(',', ''))
        except:
            return 0
    
    # 建立今日/昨日的 {代碼: (名稱, 股數)} 對照
    today_map = {}
    for _, row in holdings_today.iterrows():
        code = str(row[code_col]).strip()
        name = str(row[name_col])
        shares = clean_shares(row[shares_col])
        today_map[code] = (name, shares)
    
    yesterday_map = {}
    for _, row in holdings_yesterday.iterrows():
        code = str(row[code_col]).strip()
        name = str(row[name_col])
        shares = clean_shares(row[shares_col])
        yesterday_map[code] = (name, shares)
    
    # 計算每檔股票的變化
    all_codes = set(today_map.keys()) | set(yesterday_map.keys())
    stock_changes = {}  # {code: (name, diff)}
    
    for code in all_codes:
        today_shares = today_map.get(code, (None, 0))[1]
        yesterday_shares = yesterday_map.get(code, (None, 0))[1]
        diff = today_shares - yesterday_shares
        
        name = today_map.get(code, (None, 0))[0] or yesterday_map.get(code, (None, 0))[0]
        if diff != 0 and name:
            stock_changes[code] = (name, diff)
    
    # 按族群分組
    group_changes = {}
    for code, (name, diff) in stock_changes.items():
        groups = get_stock_groups(code)
        for g in groups:
            if g not in group_changes:
                group_changes[g] = []
            group_changes[g].append((name, code, diff))
    
    # 每個族群內按變化量絕對值排序
    for g in group_changes:
        group_changes[g].sort(key=lambda x: abs(x[2]), reverse=True)
    
    return group_changes


# ==========================================
# 🔍 自動偵測新標籤功能
# ==========================================

# 自動匹配規則 (增強版 - 支援優先級和排除規則)
AUTO_MATCH_KEYWORDS = {
    "AI": {
        "keywords": ["AI", "人工智慧", "ChatGPT", "GPT", "LLM", "機器學習", "深度學習"],
        "priority": 1,
        "min_match_length": 2  # 關鍵字至少2個字元
    },
    "記憶體": {
        "keywords": ["記憶體", "DRAM", "FLASH", "NAND", "HBM", "DDR", "RAM", "SSD"],
        "exclude": ["IC設計", "設計"],  # 排除「記憶體IC設計」
        "priority": 2
    },
    "被動元件": {
        "keywords": ["電阻", "電容", "電感", "MLCC", "被動", "濾波", "石英", "晶振"],
        "priority": 3
    },
    "PCB": {
        "keywords": ["PCB", "電路板", "載板", "銅箔", "ABF", "軟板", "硬板"],
        "priority": 3
    },
    "IC設計": {
        "keywords": ["IC設計", "IC-設計", "晶片設計", "ASIC", "FPGA"],
        "exclude": ["代工", "封測"],
        "priority": 2
    },
    "IC代工": {
        "keywords": ["代工", "晶圓代工", "IC-代工", "CoWoS", "先進封裝"],
        "exclude": ["設計", "封測"],
        "priority": 2
    },
    "封測": {
        "keywords": ["封測", "封裝", "IC-封測", "測試", "打線"],
        "priority": 2
    },
    "半導體設備": {
        "keywords": ["設備", "半導體設備", "製程設備", "檢測", "量測", "儀器"],
        "priority": 3
    },
    "光通訊": {
        "keywords": ["光通訊", "光纖", "矽光子", "光學", "鏡頭", "鏡片", "光收發"],
        "priority": 3
    },
    "電動車": {
        "keywords": ["電動車", "EV", "車用", "汽車", "MIH", "Tesla", "特斯拉", "充電樁"],
        "priority": 2
    },
    "網通": {
        "keywords": ["5G", "6G", "網通", "WiFi", "通訊", "O-RAN", "衛星", "基地台"],
        "priority": 3
    },
    "面板": {
        "keywords": ["面板", "LCD", "OLED", "LED", "顯示", "觸控", "Mini LED", "Micro LED"],
        "priority": 3
    },
    "航運": {
        "keywords": ["航運", "船運", "貨櫃", "散裝", "空運", "海運", "貨運"],
        "priority": 1
    },
    "金融": {
        "keywords": ["銀行", "保險", "證券", "金控", "金融", "壽險", "產險"],
        "priority": 2
    },
    "蘋果供應鏈": {
        "keywords": ["Apple", "蘋果", "iPhone", "iPad", "Mac", "Airpods", "Watch"],
        "priority": 2
    },
    "電源供應器": {
        "keywords": ["電源", "供應器", "PSU", "BBU", "UPS", "變壓器", "穩壓器"],
        "priority": 3
    },
    "連接器": {
        "keywords": ["連接器", "連接", "接頭", "Type-c", "USB", "HDMI", "插座"],
        "priority": 3
    },
    "散熱": {
        "keywords": ["散熱", "熱導", "風扇", "水冷", "均熱板", "散熱模組"],
        "priority": 3
    },
    "伺服器": {
        "keywords": ["伺服器", "Server", "資料中心", "雲端", "機櫃"],
        "priority": 2
    },
    # 傳統產業
    "食品": {
        "keywords": ["食品", "飲料", "乳製品", "速食", "烘焙", "罐頭", "飼料", "肉品"],
        "priority": 4
    },
    "水泥": {
        "keywords": ["水泥", "預拌混凝土"],
        "priority": 4
    },
    "塑膠": {
        "keywords": ["塑膠", "塑化", "PE", "PP", "PVC", "ABS", "PS", "樹脂"],
        "priority": 4
    },
    "紡織": {
        "keywords": ["紡織", "成衣", "織布", "化纖", "尼龍", "聚酯"],
        "priority": 4
    },
    "鋼鐵": {
        "keywords": ["鋼鐵", "不鏽鋼", "鋼筋", "鋼構", "鋼板", "鋼管", "螺絲"],
        "priority": 4
    },
    "建材": {
        "keywords": ["建材", "磁磚", "塗料", "玻璃", "衛浴"],
        "priority": 4
    },
    "機械": {
        "keywords": ["機械", "工具機", "產業機械", "自動化", "CNC"],
        "priority": 4
    },
    "營建": {
        "keywords": ["營建", "地產", "住宅", "營造", "建設", "房地產"],
        "priority": 4
    },
    "化學": {
        "keywords": ["化學", "化工", "肥料", "染料", "塗料", "溶劑"],
        "priority": 4
    },
    "生技醫療": {
        "keywords": ["生技", "醫療", "製藥", "新藥", "診斷", "檢驗", "醫藥", "長照"],
        "priority": 3
    },
    "電子通路": {
        "keywords": ["通路", "代理", "零組件通路", "電子元件"],
        "priority": 4
    },
    "運動休閒": {
        "keywords": ["運動", "休閒", "健身", "戶外", "自行車"],
        "priority": 4
    },
    "電信服務": {
        "keywords": ["電信", "通信服務", "電訊"],
        "priority": 4
    },
    "百貨零售": {
        "keywords": ["百貨", "零售", "購物", "量販", "便利店"],
        "priority": 4
    },
    "觀光": {
        "keywords": ["觀光", "飯店", "旅館", "旅遊", "餐飲", "旅行社"],
        "priority": 4
    },
    "電機電纜": {
        "keywords": ["電機", "電纜", "重電", "配電", "智慧電網"],
        "priority": 4
    },
    "橡膠": {
        "keywords": ["橡膠", "輪胎"],
        "priority": 4
    },
    "造紙": {
        "keywords": ["造紙", "工業用紙", "家庭用紙"],
        "priority": 4
    },
}


def scan_all_tags():
    """
    掃描 master_stock_tags.csv 中所有獨特的 MainTags
    
    Returns:
        set: 所有獨特的標籤
    """
    df = load_stock_tags()
    if df.empty:
        return set()
    
    all_tags = set()
    for _, row in df.iterrows():
        main_tags = str(row.get('MainTags', ''))
        if main_tags and main_tags != 'nan':
            # 分割逗號分隔的標籤
            tags = [t.strip() for t in main_tags.split(',')]
            all_tags.update(tags)
    
    return all_tags


def get_mapped_tags():
    """
    取得已被 GROUP_MAPPING 涵蓋的所有標籤
    
    Returns:
        set: 已分類的標籤
    """
    mapped = set()
    for keywords in GROUP_MAPPING.values():
        mapped.update(keywords)
    return mapped


def auto_classify_tag(tag: str, use_ai: bool = False) -> list:
    """
    使用增強版關鍵字自動將標籤分類到現有族群
    
    Args:
        tag: 標籤名稱
        use_ai: 是否使用 AI 輔助分類
        
    Returns:
        族群名稱列表（一個標籤可能屬於多個族群）
    """
    # 0. 先檢查 AI 快取
    try:
        from ai_classifier import get_ai_learned_tags
        ai_cache = get_ai_learned_tags()
        if tag in ai_cache:
            return [ai_cache[tag]]
    except:
        pass
    
    # 1. 嘗試關鍵字匹配（增強版）
    tag_upper = tag.upper()
    matched_groups = []
    
    for group, rules in AUTO_MATCH_KEYWORDS.items():
        keywords = rules.get("keywords", []) if isinstance(rules, dict) else rules
        exclude_kws = rules.get("exclude", []) if isinstance(rules, dict) else []
        priority = rules.get("priority", 99) if isinstance(rules, dict) else 99
        min_length = rules.get("min_match_length", 1) if isinstance(rules, dict) else 1
        
        # 檢查包含規則
        include_match = False
        for kw in keywords:
            if len(kw) >= min_length and (kw.upper() in tag_upper or tag_upper in kw.upper()):
                include_match = True
                break
        
        # 檢查排除規則
        exclude_match = False
        for ex_kw in exclude_kws:
            if ex_kw.upper() in tag_upper:
                exclude_match = True
                break
        
        if include_match and not exclude_match:
            matched_groups.append((group, priority))
    
    # 按優先級排序並返回
    if matched_groups:
        matched_groups.sort(key=lambda x: x[1])
        return [g[0] for g in matched_groups]
    
    # 2. 如果啟用 AI，嘗試 AI 分類
    if use_ai:
        try:
            from ai_classifier import classify_tag_with_ai
            ai_result = classify_tag_with_ai(tag)
            if ai_result not in ["傳產其他", "科技其他", "其他"]:
                return [ai_result]
        except Exception as e:
            print(f"⚠️ AI 分類失敗: {e}")
    
    # 3. Fallback
    if any(c.isupper() for c in tag) and len(tag) <= 6:
        return ["科技其他"]
    
    return ["傳產其他"]


def auto_classify_tag_single(tag: str, use_ai: bool = False) -> str:
    """
    簡化版：只返回第一個匹配的族群（向後兼容）
    """
    results = auto_classify_tag(tag, use_ai)
    return results[0] if results else "其他"


def find_unclassified_tags(verbose: bool = True):
    """
    找出尚未被分類的標籤，並嘗試自動分類
    
    Args:
        verbose: 是否印出詳細資訊
        
    Returns:
        dict: {
            'unclassified': [未分類標籤列表],
            'auto_classified': {標籤: 建議族群},
            'truly_unknown': [完全無法匹配的標籤]
        }
    """
    all_tags = scan_all_tags()
    mapped_tags = get_mapped_tags()
    
    # 找出未被納入的標籤
    unclassified = all_tags - mapped_tags
    
    # 嘗試自動分類
    auto_classified = {}
    truly_unknown = []
    
    for tag in unclassified:
        suggested_group = auto_classify_tag(tag)
        if suggested_group != "其他":
            auto_classified[tag] = suggested_group
        else:
            truly_unknown.append(tag)
    
    if verbose:
        print(f"\n📊 標籤分類統計")
        print(f"━━━━━━━━━━━━━━━━━━━━━━")
        print(f"總標籤數: {len(all_tags)}")
        print(f"已分類: {len(mapped_tags)}")
        print(f"未分類: {len(unclassified)}")
        print(f"  ├─ 可自動歸類: {len(auto_classified)}")
        print(f"  └─ 需手動處理: {len(truly_unknown)}")
        
        if auto_classified:
            print(f"\n🔄 建議自動歸類:")
            for tag, group in sorted(auto_classified.items(), key=lambda x: x[1]):
                print(f"   {tag} → {group}")
        
        if truly_unknown and len(truly_unknown) <= 20:
            print(f"\n❓ 無法自動分類 (建議手動處理):")
            for tag in sorted(truly_unknown)[:20]:
                print(f"   - {tag}")
            if len(truly_unknown) > 20:
                print(f"   ... 還有 {len(truly_unknown) - 20} 個")
    
    return {
        'unclassified': list(unclassified),
        'auto_classified': auto_classified,
        'truly_unknown': truly_unknown
    }


def get_extended_group_mapping():
    """
    取得擴展版的族群對照表，包含自動分類的標籤
    
    Returns:
        dict: 擴展版 GROUP_MAPPING
    """
    # 複製原始對照表
    extended = {k: list(v) for k, v in GROUP_MAPPING.items()}
    
    # 加入自動分類的標籤
    result = find_unclassified_tags(verbose=False)
    for tag, group in result['auto_classified'].items():
        if group in extended:
            extended[group].append(tag)
    
    # 建立「其他」分類
    if result['truly_unknown']:
        extended['其他'] = result['truly_unknown']
    
    return extended


def build_stock_group_map_extended():
    """
    建立擴展版 {股票代碼: [族群列表]} 對照表
    使用自動分類功能處理新標籤
    """
    df = load_stock_tags()
    if df.empty:
        return {}
    
    extended_mapping = get_extended_group_mapping()
    stock_group_map = {}
    
    for _, row in df.iterrows():
        code = str(row['Code']).strip()
        main_tags = str(row.get('MainTags', ''))
        
        matched_groups = set()
        for group_name, keywords in extended_mapping.items():
            for kw in keywords:
                if kw in main_tags:
                    matched_groups.add(group_name)
                    break
        
        if matched_groups:
            stock_group_map[code] = list(matched_groups)
    
    return stock_group_map


def classify_by_moneydj_industry(industries: set) -> set:
    """
    根據 MoneyDJ 產業別分類到族群
    
    Args:
        industries: MoneyDJ 產業別集合（例如：{"半導體業", "IC製造業"}）
        
    Returns:
        族群集合（例如：{"IC代工"}）
    """
    groups = set()
    
    for industry in industries:
        industry = industry.strip()
        
        # 方法 1: 完全匹配
        if industry in MONEYDJ_INDUSTRY_MAPPING:
            groups.add(MONEYDJ_INDUSTRY_MAPPING[industry])
            continue
        
        # 方法 2: 部分匹配（如果產業名稱包含對照表的 key）
        matched = False
        for moneydj_key, group in MONEYDJ_INDUSTRY_MAPPING.items():
            # 檢查是否互相包含
            if moneydj_key in industry or industry in moneydj_key:
                groups.add(group)
                matched = True
                break
        
        # 方法 3: 如果還是沒匹配，用關鍵字匹配
        if not matched:
            # 提取產業名稱的關鍵字進行匹配
            industry_keywords = []
            for key in ["半導體", "IC", "電子", "光電", "通訊", "網通", 
                       "水泥", "鋼鐵", "塑膠", "紡織", "食品",
                       "航運", "金融", "生技", "醫療", "觀光"]:
                if key in industry:
                    industry_keywords.append(key)
            
            # 如果有提取到關鍵字，用 AUTO_MATCH_KEYWORDS 匹配
            if industry_keywords:
                for keyword in industry_keywords:
                    suggested = auto_classify_tag(keyword, use_ai=False)
                    for s in suggested:
                        if s not in ["傳產其他", "科技其他", "其他"]:
                            groups.add(s)
                            matched = True
                            break
                    if matched:
                        break
    
    return groups


def test_moneydj_mapping():
    """
    測試 MoneyDJ 產業對照功能
    """
    print("\n" + "="*60)
    print("🧪 測試 MoneyDJ 產業對照功能")
    print("="*60)
    
    test_cases = [
        {"半導體業", "IC製造業"},
        {"光電業"},
        {"航運業", "貨櫃航運業"},
        {"金融保險業"},
        {"食品工業"},
        {"生技醫療業"},
        {"未知產業XYZ"},  # 測試無法匹配的情況
    ]
    
    for industries in test_cases:
        groups = classify_by_moneydj_industry(industries)
        print(f"\n產業: {industries}")
        print(f"→ 族群: {groups if groups else '(無法分類)'}")


if __name__ == "__main__":
    # 測試
    print("測試族群對照...")
    print(f"2330 (台積電): {get_stock_groups('2330')}")
    print(f"2337 (旺宏): {get_stock_groups('2337')}")
    print(f"2454 (聯發科): {get_stock_groups('2454')}")
    print(f"2327 (國巨): {get_stock_groups('2327')}")
    print(f"2603 (長榮): {get_stock_groups('2603')}")
    
    print("\n" + "="*50)
    print("🔍 偵測未分類標籤...")
    find_unclassified_tags(verbose=True)
    
    # ✨ 新增：測試 MoneyDJ 對照
    test_moneydj_mapping()
