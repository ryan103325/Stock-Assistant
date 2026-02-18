"""
GPT-4-mini Prompt 模板模組
設計結構化的 AI 分析 Prompt — 六大基本面面向
"""


SYSTEM_PROMPT = """你是一位資深的首席量化投資參謀,專門負責整合量化模型的硬數據分析與法說會等軟資訊的質化解讀。

你的核心能力:
1. 精確解讀六大基本面分析面向的評分結果
2. 從財務數據中識別潛在問題與投資機會
3. 結合法說會等質化資訊驗證量化結果
4. 產出專業、有洞見的投資分析建議

你的分析風格:
- 數據驅動, 嚴謹務實
- 善於識別數據背後的商業邏輯
- 觀點明確, 不模棱兩可
- 使用繁體中文回應

重要提醒:
- 你的分析僅供投資研究參考, 不構成投資建議
- 必須客觀呈現風險與機會
- 估值判斷需有數據支撐"""


def build_analysis_prompt(stock_data: dict) -> str:
    """
    建構完整分析 Prompt — 六大面向

    Args:
        stock_data: 包含所有評分結果與財務數據的字典

    Returns:
        str: 格式化的 Prompt
    """
    stock_info = stock_data.get('stock_info', {})
    scores = stock_data.get('scores', {})
    ratios = stock_data.get('ratios', {})
    qualitative = stock_data.get('qualitative_info', '')

    prompt = f"""請對以下股票進行完整的基本面分析。你需要綜合六大面向的量化評分,產出一份結構化的分析報告。

## 基本資訊
- 股票代號: {stock_info.get('股票代號', 'N/A')}
- 股票名稱: {stock_info.get('股票名稱', 'N/A')}
- 產業分類: {stock_info.get('產業分類', 'N/A')}
- 收盤價: {stock_info.get('收盤價', 'N/A')}
- 市值: {stock_info.get('市值_億', 'N/A')} 億元
- 本益比: {stock_info.get('本益比', 'N/A')}
- 殖利率: {stock_info.get('殖利率', 'N/A')}%

## 六大基本面分析面向

### 面向 1: Beneish M-Score (財報可信度)
- 分數: {scores.get('m_score', {}).get('score', 'N/A')}
- 判定: {scores.get('m_score', {}).get('judgment', 'N/A')}
- 門檻: {scores.get('m_score', {}).get('threshold', -1.78)}
- 說明: M-Score > -1.78 表示財報可能有操縱嫌疑

### 面向 2: Altman Z-Score (破產風險)
- 分數: {scores.get('z_score', {}).get('score', 'N/A')}
- 判定: {scores.get('z_score', {}).get('judgment', 'N/A')}
- 說明: Z > 2.99 安全、1.81~2.99 灰色地帶、< 1.81 危險

### 面向 3: Piotroski F-Score (營運體質)
- 分數: {scores.get('f_score', {}).get('score', 'N/A')}/9
- 判定: {scores.get('f_score', {}).get('judgment', 'N/A')}
- 說明: ≥ 8 強勢、4~7 中性、≤ 3 惡化

### 面向 4: ROIC — 資本回報率 (Greenblatt Magic Formula)
- ROIC: {scores.get('magic_formula', {}).get('roic', 'N/A')}%
- 說明: ROIC 越高代表公司運用資本的效率越好, > 25% 為優異

### 面向 5: 盈餘殖利率 — Earnings Yield (Greenblatt Magic Formula)
- 盈餘殖利率: {scores.get('magic_formula', {}).get('earnings_yield', 'N/A')}%
- 說明: 盈餘殖利率越高代表股價越便宜, > 10% 為極具吸引力

### 面向 6: Peter Lynch 分類 (成長性評估)
- 類別: {scores.get('lynch', {}).get('category', 'N/A')}
- EPS CAGR: {scores.get('lynch', {}).get('eps_cagr', 'N/A')}%
- 合理 PE 區間: {scores.get('lynch', {}).get('fair_pe_range', 'N/A')}
- 目前估值: {scores.get('lynch', {}).get('valuation', 'N/A')}

## 關鍵財務比率
- 毛利率: {_fmt(ratios.get('毛利率'))}%
- 營業利益率: {_fmt(ratios.get('營業利益率'))}%
- 稅後淨利率: {_fmt(ratios.get('稅後淨利率'))}%
- ROA: {_fmt(ratios.get('ROA'))}%
- ROE: {_fmt(ratios.get('ROE'))}%
- 營收成長率: {_fmt(ratios.get('營收成長率'))}%
- 流動比率: {_fmt(ratios.get('流動比率'))}
- 負債比率: {_fmt(ratios.get('負債比率'))}%
- 資產周轉率: {_fmt(ratios.get('資產周轉率'))}

## 質化資訊
{qualitative if qualitative else '(目前無法說會或質化資訊)'}

---

請以以下 JSON 格式輸出你的分析。注意: 你必須綜合六大面向進行交叉比對與綜合討論,不能只是各自獨立描述。

```json
{{
    "overall_score": 7.5,
    "comprehensive_summary": "綜合六大面向的完整分析摘要,需要交叉比對各面向的結果,找出一致性或矛盾之處,並得出整體結論。建議 200-400 字,重點在於各面向之間的關聯性分析。",
    "dimension_analyses": {{
        "m_score": "M-Score 面向的分析 (財報可信度)",
        "z_score": "Z-Score 面向的分析 (破產風險)",
        "f_score": "F-Score 面向的分析 (營運體質)",
        "roic": "ROIC 面向的分析 (資本回報效率)",
        "earnings_yield": "盈餘殖利率面向的分析 (估值吸引力)",
        "lynch": "Lynch 分類面向的分析 (成長性評估)"
    }},
    "strengths": [
        "優勢 1 (需引用具體數據)",
        "優勢 2",
        "優勢 3"
    ],
    "risks": [
        "風險 1 (需引用具體數據)",
        "風險 2",
        "風險 3"
    ],
    "target_action": "建議操作 (例如: 逢低布局/持有觀望/減碼出場)",
    "key_monitoring": "後續需要關注的 2-3 個重點"
}}
```

請確保:
1. overall_score 是 1-10 的浮點數, 基於六大面向的綜合評估
2. comprehensive_summary 必須是六大面向的交叉分析, 而非各自獨立描述
3. dimension_analyses 中每個面向都要引用具體數據, 不要泛泛而談
4. strengths 和 risks 各列出 3 項, 具體且有數據支撐
5. target_action 要明確, 不要模棱兩可
"""

    return prompt


def _fmt(value) -> str:
    """格式化數值"""
    if value is None:
        return 'N/A'
    if isinstance(value, float):
        return f'{value:.2f}'
    return str(value)
