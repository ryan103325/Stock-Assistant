"""
籌碼面評分引擎 — 依據規格書 v2.0 實作四維度評分
總分 0-100 分
"""

from dataclasses import dataclass, field


@dataclass
class DimensionScore:
    score: float = 0.0
    max_score: float = 0.0
    breakdown: dict = field(default_factory=dict)


@dataclass
class ChipScore:
    total: float = 0.0
    rating: str = ''
    rating_en: str = ''
    institutional: DimensionScore = field(default_factory=DimensionScore)
    ownership: DimensionScore = field(default_factory=DimensionScore)
    broker: DimensionScore = field(default_factory=DimensionScore)
    sentiment: DimensionScore = field(default_factory=DimensionScore)
    highlights: list = field(default_factory=list)
    risks: list = field(default_factory=list)
    strategy: str = ''
    low_volume_penalty: bool = False


def _clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))


def score_institutional(data: dict) -> DimensionScore:
    """
    維度一：法人動能（權重 35%，滿分 35 分）
    - 投信指標子項（佔維度 20 分）
    - 土洋對照子項（佔維度 15 分）
    """
    dim = DimensionScore(max_score=35.0)

    trust_5d = data.get('trust_buy_5d') or 0
    trust_days = data.get('trust_consecutive_days') or 0
    foreign_5d = data.get('foreign_buy_5d') or 0
    capital = data.get('capital_million') or 0  # 百萬元

    # ── 投信子項（20分）──
    trust_score = 0.0
    trust_note = ''
    if trust_5d < 0:
        trust_score = 0.0
        trust_note = f'投信近5日賣超 {abs(trust_5d):,} 張'
    else:
        # 計算佔股本比例（股本單位：百萬元 → 換算張數：1億元=1000張）
        if capital > 0:
            capital_shares = capital * 10  # 百萬元 → 張（1百萬元≈10張，1億元=1000張）
            ratio_pct = (trust_5d / capital_shares) * 100 if capital_shares > 0 else 0
        else:
            ratio_pct = 0

        if trust_days >= 3 and ratio_pct >= 0.5:
            trust_score = 20.0
            trust_note = f'投信連續買超 {trust_days} 天，近5日買超 {trust_5d:,} 張（佔股本 {ratio_pct:.2f}%）'
        elif trust_5d > 0:
            # 線性給分：0.1% → 4分，0.5% → 20分
            if ratio_pct > 0:
                trust_score = _clamp((ratio_pct / 0.5) * 20, 0, 20)
            else:
                trust_score = _clamp(trust_days * 2, 0, 10)  # 無股本資料時用天數估算
            trust_note = f'投信近5日買超 {trust_5d:,} 張（連續 {trust_days} 天）'
        else:
            trust_score = 0.0
            trust_note = '投信無買超'

    # ── 土洋對照子項（15分）──
    align_score = 0.0
    align_note = ''
    if foreign_5d > 0 and trust_5d > 0:
        align_score = 15.0
        align_note = '外資與投信同步買超（籌碼方向一致）'
    elif foreign_5d > 0 and trust_5d <= 0:
        align_score = 5.0
        align_note = '外資買超但投信賣超（外資主導）'
    elif foreign_5d <= 0 and trust_5d > 0:
        align_score = 7.5
        align_note = '⚠️ 土洋對作：投信買超但外資賣超'
    else:
        align_score = 0.0
        align_note = '外資與投信均賣超'

    dim.score = trust_score + align_score
    dim.breakdown = {
        'trust': round(trust_score, 1),
        'trust_note': trust_note,
        'foreign_align': round(align_score, 1),
        'align_note': align_note,
    }
    return dim


def score_ownership(data: dict) -> DimensionScore:
    """
    維度二：內部人與大戶結構（權重 35%，滿分 35 分）
    - 大戶趨勢子項（20分）
    - 散戶趨勢子項（15分）
    """
    dim = DimensionScore(max_score=35.0)

    whale_this = data.get('whale_pct_this')
    whale_last = data.get('whale_pct_last')
    retail_this = data.get('retail_pct_this')
    retail_last = data.get('retail_pct_last')

    # ── 大戶趨勢（20分）──
    whale_score = 0.0
    whale_note = ''
    if whale_this is not None and whale_last is not None:
        whale_change = whale_this - whale_last
        if whale_change > 0:
            # 每增加 0.5% 給 4 分，最高 20 分（增幅 2.5% 以上）
            whale_score = _clamp((whale_change / 0.5) * 4, 0, 20)
            whale_note = f'千張大戶持股增加 {whale_change:.2f}%（{whale_last:.1f}% → {whale_this:.1f}%）'
        else:
            whale_score = 0.0
            whale_note = f'千張大戶持股減少 {abs(whale_change):.2f}%（{whale_last:.1f}% → {whale_this:.1f}%）'
    else:
        whale_note = '大戶持股資料不足'

    # ── 散戶趨勢（15分）──
    retail_score = 0.0
    retail_note = ''
    if retail_this is not None and retail_last is not None:
        retail_change = retail_this - retail_last
        if retail_change < 0:
            # 每減少 0.5% 給 3 分，最高 15 分（降幅 2.5% 以上）
            retail_score = _clamp((abs(retail_change) / 0.5) * 3, 0, 15)
            retail_note = f'散戶持股減少 {abs(retail_change):.2f}%（{retail_last:.1f}% → {retail_this:.1f}%）'
        else:
            retail_score = 0.0
            retail_note = f'散戶持股增加 {retail_change:.2f}%（{retail_last:.1f}% → {retail_this:.1f}%）'
    else:
        retail_note = '散戶持股資料不足'

    dim.score = whale_score + retail_score
    dim.breakdown = {
        'whale': round(whale_score, 1),
        'whale_note': whale_note,
        'retail': round(retail_score, 1),
        'retail_note': retail_note,
    }
    return dim


def score_broker(data: dict, low_volume: bool = False) -> DimensionScore:
    """
    維度三：關鍵分點足跡（權重 20%，滿分 20 分）
    - 異常買盤子項（10分）
    - 地緣/特殊加成子項（10分）
    低成交量時扣減 50% 權重
    """
    dim = DimensionScore(max_score=20.0)

    broker_buy = data.get('broker_buy_1d') or 0
    total_vol = data.get('total_volume_1d') or 0
    is_geo = data.get('is_geo_broker') or False

    # ── 異常買盤（10分）──
    abnormal_score = 0.0
    abnormal_note = ''
    if total_vol > 0 and broker_buy > 0:
        ratio_pct = (broker_buy / total_vol) * 100
        if ratio_pct >= 15:
            abnormal_score = 10.0
        elif ratio_pct >= 10:
            abnormal_score = 7.0
        elif ratio_pct >= 5:
            abnormal_score = 4.0
        else:
            abnormal_score = 0.0

        broker_name = data.get('broker_name_1d') or '未知券商'
        abnormal_note = f'{broker_name} 買超 {broker_buy:,} 張（佔成交量 {ratio_pct:.1f}%）'
    elif total_vol <= 100 and total_vol > 0:
        abnormal_note = '成交量過低，分點資料失真'
    else:
        abnormal_note = '無明顯分點集中買盤'

    # ── 地緣加成（10分）──
    geo_score = 10.0 if is_geo else 0.0
    geo_note = '確認為地緣券商' if is_geo else '非地緣券商（預設，需人工確認）'

    # 低成交量扣減 50%
    if low_volume:
        abnormal_score *= 0.5
        geo_score *= 0.5
        abnormal_note += '（低成交量，權重減半）'

    dim.score = abnormal_score + geo_score
    dim.breakdown = {
        'abnormal': round(abnormal_score, 1),
        'abnormal_note': abnormal_note,
        'geo': round(geo_score, 1),
        'geo_note': geo_note,
    }
    return dim


def score_sentiment(data: dict) -> DimensionScore:
    """
    維度四：市場情緒（權重 10%，滿分 10 分）
    - 融資安定度子項（5分）
    - 軋空潛力子項（5分）
    """
    dim = DimensionScore(max_score=10.0)

    margin_change = data.get('margin_change') or 0
    short_ratio = data.get('short_ratio') or 0
    price_above_ma = data.get('price_above_ma')  # None = 未知

    # ── 融資安定度（5分）──
    margin_score = 0.0
    margin_note = ''
    if margin_change < 0:
        # 每減少 100 張給 1 分，最高 5 分
        margin_score = _clamp(abs(margin_change) / 100, 0, 5)
        margin_note = f'融資近5日減少 {abs(margin_change):,} 張（籌碼健康）'
    else:
        margin_note = f'融資近5日增加 {margin_change:,} 張（散戶追價）'

    # ── 軋空潛力（5分）──
    squeeze_score = 0.0
    squeeze_note = ''
    if short_ratio >= 30:
        if price_above_ma is True:
            squeeze_score = 5.0
            squeeze_note = f'券資比 {short_ratio:.1f}%，股價站上均線（軋空潛力高）'
        elif price_above_ma is False:
            squeeze_score = 2.0
            squeeze_note = f'券資比 {short_ratio:.1f}%，但股價未站上均線'
        else:
            squeeze_score = 2.5  # 未知均線關係給中性分
            squeeze_note = f'券資比 {short_ratio:.1f}%（均線關係未知）'
    else:
        squeeze_note = f'券資比 {short_ratio:.1f}%（軋空壓力不足）'

    dim.score = margin_score + squeeze_score
    dim.breakdown = {
        'margin': round(margin_score, 1),
        'margin_note': margin_note,
        'squeeze': round(squeeze_score, 1),
        'squeeze_note': squeeze_note,
    }
    return dim


def generate_highlights(inst: DimensionScore, own: DimensionScore,
                         brok: DimensionScore, sent: DimensionScore) -> list[str]:
    """自動列出得分最高的前三個子項目"""
    items = [
        (inst.breakdown.get('trust', 0), inst.breakdown.get('trust_note', '')),
        (inst.breakdown.get('foreign_align', 0), inst.breakdown.get('align_note', '')),
        (own.breakdown.get('whale', 0), own.breakdown.get('whale_note', '')),
        (own.breakdown.get('retail', 0), own.breakdown.get('retail_note', '')),
        (brok.breakdown.get('abnormal', 0), brok.breakdown.get('abnormal_note', '')),
        (brok.breakdown.get('geo', 0), brok.breakdown.get('geo_note', '')),
        (sent.breakdown.get('margin', 0), sent.breakdown.get('margin_note', '')),
        (sent.breakdown.get('squeeze', 0), sent.breakdown.get('squeeze_note', '')),
    ]
    # 排序取前三，過濾空字串和 0 分
    top = sorted([(s, n) for s, n in items if s > 0 and n], reverse=True)[:3]
    return [note for _, note in top]


def generate_risks(data: dict, total: float, inst: DimensionScore) -> list[str]:
    """偵測風險情境"""
    risks = []
    trust_5d = data.get('trust_buy_5d') or 0
    foreign_5d = data.get('foreign_buy_5d') or 0
    margin_change = data.get('margin_change') or 0
    short_ratio = data.get('short_ratio') or 0
    total_vol = data.get('total_volume_1d') or 0
    broker_buy = data.get('broker_buy_1d') or 0

    # 土洋對作
    if foreign_5d < 0 and trust_5d > 0 and total > 70:
        risks.append('⚠️ 土洋對作：本土法人與外資方向相反，需留意外資賣壓是否影響後續走勢')

    # 低成交量
    if total_vol < 100 and broker_buy > 0:
        risks.append('⚠️ 成交量過低（< 100 張），分點數據佔比易失真，流動性風險較高')

    # 融資暴增
    if margin_change > 500 and total > 70:
        risks.append('⚠️ 融資大幅增加，散戶追價明顯，需提防短期過熱')

    # 券資比異常
    if short_ratio > 50:
        risks.append(f'⚠️ 券資比過高（{short_ratio:.1f}%），雖有軋空機會但也可能反映基本面疑慮')

    return risks


def calculate(data: dict) -> ChipScore:
    """主評分函式，輸入原始資料 dict，回傳 ChipScore"""
    result = ChipScore()

    # 低成交量判斷
    total_vol = data.get('total_volume_1d') or 0
    low_volume = total_vol > 0 and total_vol < 100

    # 四維度評分
    result.institutional = score_institutional(data)
    result.ownership = score_ownership(data)
    result.broker = score_broker(data, low_volume=low_volume)
    result.sentiment = score_sentiment(data)
    result.low_volume_penalty = low_volume

    # 總分
    raw_total = (
        result.institutional.score +
        result.ownership.score +
        result.broker.score +
        result.sentiment.score
    )
    result.total = round(_clamp(raw_total, 0, 100), 1)

    # 低成交量降級
    effective_total = result.total
    if low_volume:
        effective_total = max(0, result.total - 20)  # 降一個等級

    # 評級
    if effective_total > 80:
        result.rating = '強力買進'
        result.rating_en = 'Strong Buy'
        result.strategy = '建議於股價回檔整理時分批進場，目標持有至主力出貨訊號出現'
    elif effective_total >= 60:
        result.rating = '偏多操作'
        result.rating_en = 'Bullish'
        result.strategy = '可配置適當部位，但需設定停損並密切追蹤後續籌碼變化'
    else:
        result.rating = '觀望/中性'
        result.rating_en = 'Neutral'
        result.strategy = '建議等待籌碼面更明確的多方訊號後再行動'

    # 亮點與風險
    result.highlights = generate_highlights(
        result.institutional, result.ownership, result.broker, result.sentiment
    )
    result.risks = generate_risks(data, result.total, result.institutional)

    return result
