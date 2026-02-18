"""
籌碼面評分引擎 — 四維度版
總分 0-100 分
維度一：法人動能（30分）
維度二：內部人結構（30分）
維度三：分點主力（20分）
維度四：市場情緒（20分）
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
    維度一：法人動能（滿分 30 分）
    - 投信子項（17分）
    - 土洋對照子項（13分）
    """
    dim = DimensionScore(max_score=30.0)

    trust_5d = data.get('trust_buy_5d') or 0
    trust_days = data.get('trust_consecutive_days') or 0
    foreign_5d = data.get('foreign_buy_5d') or 0

    # 投信子項（17分）
    trust_score = 0.0
    trust_note = ''
    if trust_5d < 0:
        trust_score = 0.0
        trust_note = f'投信近5日賣超 {abs(trust_5d):,} 張'
    elif trust_5d > 0:
        if trust_days >= 3:
            trust_score = _clamp(trust_days * 2.5, 0, 17)
        else:
            trust_score = _clamp(trust_days * 2, 0, 8)
        trust_note = f'投信近5日買超 {trust_5d:,} 張（連續 {trust_days} 天）'
    else:
        trust_note = '投信無買超'

    # 土洋對照子項（13分）
    align_score = 0.0
    align_note = ''
    if foreign_5d > 0 and trust_5d > 0:
        align_score = 13.0
        align_note = '外資與投信同步買超（籌碼方向一致）'
    elif foreign_5d > 0 and trust_5d <= 0:
        align_score = 4.0
        align_note = '外資買超但投信賣超（外資主導）'
    elif foreign_5d <= 0 and trust_5d > 0:
        align_score = 6.5
        align_note = '土洋對作：投信買超但外資賣超'
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
    維度二：內部人與大戶結構（滿分 30 分）
    - 大戶趨勢（17分）
    - 散戶趨勢（13分）
    """
    dim = DimensionScore(max_score=30.0)

    whale_this = data.get('whale_pct_this')
    whale_last = data.get('whale_pct_last')
    retail_this = data.get('retail_pct_this')
    retail_last = data.get('retail_pct_last')

    # 大戶趨勢（17分）
    whale_score = 0.0
    whale_note = ''
    if whale_this is not None and whale_last is not None:
        whale_change = whale_this - whale_last
        if whale_change > 0:
            whale_score = _clamp((whale_change / 0.5) * 3.5, 0, 17)
            whale_note = f'千張大戶持股增加 {whale_change:.2f}%（{whale_last:.1f}% -> {whale_this:.1f}%）'
        else:
            whale_score = 0.0
            whale_note = f'千張大戶持股減少 {abs(whale_change):.2f}%（{whale_last:.1f}% -> {whale_this:.1f}%）'
    else:
        whale_note = '大戶持股資料不足'

    # 散戶趨勢（13分）
    retail_score = 0.0
    retail_note = ''
    if retail_this is not None and retail_last is not None:
        retail_change = retail_this - retail_last
        if retail_change < 0:
            retail_score = _clamp((abs(retail_change) / 0.5) * 2.5, 0, 13)
            retail_note = f'散戶持股減少 {abs(retail_change):.2f}%（{retail_last:.1f}% -> {retail_this:.1f}%）'
        else:
            retail_score = 0.0
            retail_note = f'散戶持股增加 {retail_change:.2f}%（{retail_last:.1f}% -> {retail_this:.1f}%）'
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


def score_broker(data: dict) -> DimensionScore:
    """
    維度三：分點主力（滿分 20 分）
    - 主力連續買超天數（10分）
    - Top 1 買超券商淨買張數（10分）
    """
    dim = DimensionScore(max_score=20.0)

    consecutive = data.get('main_force_consecutive') or 0
    net_5d = data.get('main_force_net_5d') or 0
    top_buy_broker = data.get('top_buy_broker') or ''
    top_buy_net = data.get('top_buy_net') or 0

    # 主力連續買超天數（10分）
    consec_score = 0.0
    consec_note = ''
    if consecutive >= 3:
        consec_score = _clamp(consecutive * 2, 0, 10)
        consec_note = f'主力連續買超 {consecutive} 天'
    elif consecutive > 0:
        consec_score = consecutive * 1.5
        consec_note = f'主力買超 {consecutive} 天（不夠連貫）'
    elif net_5d < 0:
        consec_note = f'主力近5日淨賣超 {abs(net_5d):,} 張'
    else:
        consec_note = '主力無明顯買超'

    # Top 1 買超券商集中度（10分）
    top_score = 0.0
    top_note = ''
    if top_buy_net and top_buy_net > 0:
        if top_buy_net >= 1000:
            top_score = 10.0
        elif top_buy_net >= 500:
            top_score = 7.0
        elif top_buy_net >= 100:
            top_score = 4.0
        else:
            top_score = 2.0
        top_note = f'最大買超券商：{top_buy_broker}（淨買 {top_buy_net:,} 張）'
    elif top_buy_broker:
        top_note = f'最大買超券商：{top_buy_broker}（{top_buy_net} 張）'
    else:
        top_note = '無券商分點資料'

    dim.score = consec_score + top_score
    dim.breakdown = {
        'consecutive': round(consec_score, 1),
        'consec_note': consec_note,
        'top_broker': round(top_score, 1),
        'top_note': top_note,
    }
    return dim


def score_sentiment(data: dict) -> DimensionScore:
    """
    維度四：市場情緒（滿分 20 分）
    - 融資安定度（10分）
    - 軋空潛力（10分）
    """
    dim = DimensionScore(max_score=20.0)

    margin_change = data.get('margin_change') or 0
    short_ratio = data.get('short_ratio') or 0

    # 融資安定度（10分）
    margin_score = 0.0
    margin_note = ''
    if margin_change < 0:
        margin_score = _clamp(abs(margin_change) / 100 * 2, 0, 10)
        margin_note = f'融資近5日減少 {abs(margin_change):,} 張（籌碼健康）'
    elif margin_change > 0:
        margin_note = f'融資近5日增加 {margin_change:,} 張（散戶追價）'
    else:
        margin_note = '融資無明顯變化'

    # 軋空潛力（10分）
    squeeze_score = 0.0
    squeeze_note = ''
    if short_ratio >= 30:
        squeeze_score = _clamp((short_ratio / 30) * 7, 0, 10)
        squeeze_note = f'券資比 {short_ratio:.1f}%（軋空潛力高）'
    elif short_ratio >= 15:
        squeeze_score = 3.5
        squeeze_note = f'券資比 {short_ratio:.1f}%（中等軋空壓力）'
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
                        broker: DimensionScore, sent: DimensionScore) -> list[str]:
    items = [
        (inst.breakdown.get('trust', 0), inst.breakdown.get('trust_note', '')),
        (inst.breakdown.get('foreign_align', 0), inst.breakdown.get('align_note', '')),
        (own.breakdown.get('whale', 0), own.breakdown.get('whale_note', '')),
        (own.breakdown.get('retail', 0), own.breakdown.get('retail_note', '')),
        (broker.breakdown.get('consecutive', 0), broker.breakdown.get('consec_note', '')),
        (broker.breakdown.get('top_broker', 0), broker.breakdown.get('top_note', '')),
        (sent.breakdown.get('margin', 0), sent.breakdown.get('margin_note', '')),
        (sent.breakdown.get('squeeze', 0), sent.breakdown.get('squeeze_note', '')),
    ]
    top = sorted([(s, n) for s, n in items if s > 0 and n], reverse=True)[:3]
    return [note for _, note in top]


def generate_risks(data: dict, total: float) -> list[str]:
    risks = []
    trust_5d = data.get('trust_buy_5d') or 0
    foreign_5d = data.get('foreign_buy_5d') or 0
    margin_change = data.get('margin_change') or 0
    short_ratio = data.get('short_ratio') or 0
    main_force_net_5d = data.get('main_force_net_5d') or 0

    if foreign_5d < 0 and trust_5d > 0 and total > 70:
        risks.append('土洋對作：本土法人與外資方向相反，需留意外資賣壓')

    if margin_change > 500 and total > 70:
        risks.append('融資大幅增加，散戶追價明顯，需提防短期過熱')

    if short_ratio > 50:
        risks.append(f'券資比過高（{short_ratio:.1f}%），雖有軋空機會但也可能反映基本面疑慮')

    if main_force_net_5d < -5000 and total > 60:
        risks.append(f'主力近5日大幅賣超 {abs(main_force_net_5d):,} 張，需留意主力出貨')

    return risks


def calculate(data: dict) -> ChipScore:
    result = ChipScore()

    total_vol = data.get('total_volume_1d') or 0
    low_volume = total_vol > 0 and total_vol < 100

    result.institutional = score_institutional(data)
    result.ownership = score_ownership(data)
    result.broker = score_broker(data)
    result.sentiment = score_sentiment(data)
    result.low_volume_penalty = low_volume

    raw_total = (
        result.institutional.score +
        result.ownership.score +
        result.broker.score +
        result.sentiment.score
    )
    result.total = round(_clamp(raw_total, 0, 100), 1)

    effective_total = result.total
    if low_volume:
        effective_total = max(0, result.total - 20)

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

    result.highlights = generate_highlights(
        result.institutional, result.ownership, result.broker, result.sentiment
    )
    result.risks = generate_risks(data, result.total)

    return result
