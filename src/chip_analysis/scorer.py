"""
籌碼面評分引擎 — 四維度版
總分 0-100 分
維度一：法人動能（30分）
維度二：股東結構（30分）
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
    - 投信趨勢（12分）：連續天數 + 金額方向
    - 外資趨勢（10分）：同上
    - 三大法人一致性（8分）：同方向加分
    含轉折偵測
    """
    dim = DimensionScore(max_score=30.0)

    trust_5d = data.get('trust_buy_5d') or 0
    trust_days = data.get('trust_consecutive_days') or 0
    foreign_5d = data.get('foreign_buy_5d') or 0
    foreign_days = data.get('foreign_consecutive_days') or 0
    dealer_5d = data.get('dealer_buy_5d') or 0
    daily = data.get('institutional_daily') or []

    # 投信趨勢（12分）
    trust_score = 0.0
    trust_note = ''
    if trust_5d > 0:
        if trust_days >= 3:
            trust_score = _clamp(trust_days * 2, 0, 12)
        else:
            trust_score = _clamp(trust_days * 1.5, 0, 6)
        trust_note = f'投信近5日買超 {trust_5d:,} 張（連續 {trust_days} 天）'
    elif trust_5d < 0:
        trust_note = f'投信近5日賣超 {abs(trust_5d):,} 張'
    else:
        trust_note = '投信無買超'

    # 轉折偵測（投信）
    trust_turning = ''
    if len(daily) >= 5:
        trust_vals = [d.get('trust_net') or 0 for d in daily[:5]]
        if trust_vals[0] > 0 and all(v <= 0 for v in trust_vals[2:5]):
            trust_turning = '⚡ 投信疑似轉買超'
        elif trust_vals[0] < 0 and all(v > 0 for v in trust_vals[2:5]):
            trust_turning = '⚠️ 投信疑似轉賣超'

    # 外資趨勢（10分）
    foreign_score = 0.0
    foreign_note = ''
    if foreign_5d > 0:
        if foreign_days >= 3:
            foreign_score = _clamp(foreign_days * 1.5, 0, 10)
        else:
            foreign_score = _clamp(foreign_days * 1.2, 0, 5)
        foreign_note = f'外資近5日買超 {foreign_5d:,} 張（連續 {foreign_days} 天）'
    elif foreign_5d < 0:
        foreign_note = f'外資近5日賣超 {abs(foreign_5d):,} 張'
    else:
        foreign_note = '外資無買超'

    # 三大法人一致性（8分）
    align_score = 0.0
    align_note = ''
    buy_count = sum(1 for v in [trust_5d, foreign_5d, dealer_5d] if v > 0)
    sell_count = sum(1 for v in [trust_5d, foreign_5d, dealer_5d] if v < 0)

    if buy_count == 3:
        align_score = 8.0
        align_note = '三大法人同步買超（籌碼方向一致）'
    elif buy_count == 2:
        align_score = 5.0
        sellers = []
        if trust_5d < 0: sellers.append('投信')
        if foreign_5d < 0: sellers.append('外資')
        if dealer_5d < 0: sellers.append('自營商')
        align_note = f'二買一賣（{"、".join(sellers)}賣超）'
    elif buy_count == 1:
        align_score = 2.0
        buyers = []
        if trust_5d > 0: buyers.append('投信')
        if foreign_5d > 0: buyers.append('外資')
        if dealer_5d > 0: buyers.append('自營商')
        align_note = f'土洋對作：僅{"、".join(buyers)}買超'
    else:
        align_note = '三大法人均賣超'

    dim.score = trust_score + foreign_score + align_score
    dim.breakdown = {
        'trust': round(trust_score, 1),
        'trust_note': trust_note,
        'trust_turning': trust_turning,
        'foreign': round(foreign_score, 1),
        'foreign_note': foreign_note,
        'dealer_5d': dealer_5d,
        'foreign_align': round(align_score, 1),
        'align_note': align_note,
    }
    return dim


def score_ownership(data: dict) -> DimensionScore:
    """
    維度二：股東結構（滿分 30 分）
    - 大戶長期趨勢（17分）：近 4/13/50 週變化
    - 散戶趨勢 + 股東人數/平均張數（13分）
    """
    dim = DimensionScore(max_score=30.0)

    weekly = data.get('ownership_weekly') or []
    whale_this = data.get('whale_pct_this')
    whale_last = data.get('whale_pct_last')
    retail_this = data.get('retail_pct_this')
    retail_last = data.get('retail_pct_last')
    total_holders = data.get('total_holders_this')
    avg_shares = data.get('avg_shares_this')

    # 大戶趨勢（17分）
    whale_score = 0.0
    whale_note = ''
    if whale_this is not None and whale_last is not None:
        # 短期趨勢（近1週）
        whale_1w_change = whale_this - whale_last

        # 中期趨勢（近4週）
        whale_4w_change = None
        if len(weekly) >= 4 and weekly[3].get('whale_400_pct') is not None:
            whale_4w_change = whale_this - weekly[3]['whale_400_pct']

        # 長期趨勢（近13週）
        whale_13w_change = None
        if len(weekly) >= 13 and weekly[12].get('whale_400_pct') is not None:
            whale_13w_change = whale_this - weekly[12]['whale_400_pct']

        # 評分邏輯
        if whale_4w_change is not None and whale_13w_change is not None:
            if whale_4w_change > 0 and whale_13w_change > 0:
                whale_score = _clamp(whale_13w_change * 4, 0, 17)  # 長短期同步增加
                whale_note = f'大戶持股長短期同步增加（4週 +{whale_4w_change:.2f}%, 13週 +{whale_13w_change:.2f}%）'
            elif whale_4w_change > 0 and whale_13w_change <= 0:
                whale_score = _clamp(whale_4w_change * 5, 0, 10)
                whale_note = f'大戶近期轉增（4週 +{whale_4w_change:.2f}%），但長期仍減少'
            elif whale_4w_change <= 0 and whale_13w_change > 0:
                whale_score = _clamp(whale_13w_change * 2, 0, 8)
                whale_note = f'大戶長期增加但近期放緩（4週 {whale_4w_change:+.2f}%）'
            else:
                whale_note = f'大戶持股長短期均減少（4週 {whale_4w_change:+.2f}%, 13週 {whale_13w_change:+.2f}%）'
        elif whale_4w_change is not None:
            if whale_4w_change > 0:
                whale_score = _clamp(whale_4w_change * 5, 0, 12)
                whale_note = f'大戶近4週持股增加 {whale_4w_change:+.2f}%'
            else:
                whale_note = f'大戶近4週持股減少 {whale_4w_change:+.2f}%'
        else:
            if whale_1w_change > 0:
                whale_score = _clamp(whale_1w_change * 5, 0, 8)
                whale_note = f'大戶持股增加 {whale_1w_change:+.2f}%（{whale_last:.1f}% → {whale_this:.1f}%）'
            else:
                whale_note = f'大戶持股減少 {whale_1w_change:+.2f}%（{whale_last:.1f}% → {whale_this:.1f}%）'
    else:
        whale_note = '大戶持股資料不足'

    # 散戶趨勢 + 股東人數（13分）
    retail_score = 0.0
    retail_note = ''
    if retail_this is not None and retail_last is not None:
        retail_change = retail_this - retail_last
        if retail_change < 0:
            retail_score = _clamp(abs(retail_change) * 5, 0, 8)
            retail_note = f'散戶持股減少 {abs(retail_change):.2f}%'
        else:
            retail_note = f'散戶持股增加 {retail_change:.2f}%'
    else:
        retail_note = '散戶持股資料不足'

    # 股東人數趨勢（附加到 retail_score）
    if len(weekly) >= 4:
        holders_now = weekly[0].get('total_holders')
        holders_4w = weekly[3].get('total_holders')
        if holders_now is not None and holders_4w is not None:
            holders_change = holders_now - holders_4w
            if holders_change < 0:  # 股東減少 = 籌碼集中 = 偏多
                retail_score += _clamp(abs(holders_change) / 5000, 0, 5)
                retail_note += f'，股東人數近4週減少 {abs(holders_change):,} 人（籌碼集中）'
            elif holders_change > 0:
                retail_note += f'，股東人數近4週增加 {holders_change:,} 人（籌碼分散）'

    # 加入平均張數資訊
    holders_info = ''
    if total_holders is not None:
        holders_info = f'總股東人數 {total_holders:,} 人'
    if avg_shares is not None:
        if holders_info:
            holders_info += f'，平均 {avg_shares:.2f} 張/人'
        else:
            holders_info = f'平均 {avg_shares:.2f} 張/人'

    dim.score = whale_score + retail_score
    dim.breakdown = {
        'whale': round(whale_score, 1),
        'whale_note': whale_note,
        'retail': round(retail_score, 1),
        'retail_note': retail_note,
        'holders_info': holders_info,
    }
    return dim


def score_broker(data: dict) -> DimensionScore:
    """
    維度三：分點主力（滿分 20 分）
    - 60日主力方向（8分）
    - 主力出脫偵測（7分）：60日 Top 1 在近期是否轉賣超
    - 多期間一致性（5分）
    """
    dim = DimensionScore(max_score=20.0)

    # 取各期間資料
    b60 = data.get('broker_60d') or {}
    b20 = data.get('broker_20d') or {}
    b5 = data.get('broker_5d') or {}
    b1 = data.get('broker_1d') or {}

    # 主力走勢
    consecutive = data.get('main_force_consecutive') or 0
    net_5d = data.get('main_force_net_5d') or 0

    # 60日主力方向（8分）
    long_score = 0.0
    long_note = ''
    top_60_buy = b60.get('top_buy_net') or 0
    top_60_broker = b60.get('top_buy_broker') or ''
    top_60_sell_net = b60.get('top_sell_net') or 0

    if top_60_buy > 0:
        if top_60_buy >= 1000:
            long_score = 8.0
        elif top_60_buy >= 500:
            long_score = 6.0
        elif top_60_buy >= 100:
            long_score = 4.0
        else:
            long_score = 2.0
        long_note = f'60日最大買超：{top_60_broker}（淨買 {top_60_buy:,} 張）'
    elif top_60_broker:
        long_note = f'60日最大買超：{top_60_broker}（{top_60_buy} 張）'
    else:
        long_note = '無60日分點資料'

    # 主力出脫偵測（7分）：60日 Top 1 在近1/5日是否仍買超
    exit_score = 0.0
    exit_note = ''
    if top_60_broker:
        # 檢查 60日 Top 1 在近期的位置
        recent_buy_names_5d = [b.get('broker', '') for b in (b5.get('buy_brokers') or [])]
        recent_sell_names_5d = [b.get('broker', '') for b in (b5.get('sell_brokers') or [])]
        recent_buy_names_1d = [b.get('broker', '') for b in (b1.get('buy_brokers') or [])]
        recent_sell_names_1d = [b.get('broker', '') for b in (b1.get('sell_brokers') or [])]

        if top_60_broker in recent_buy_names_5d:
            exit_score = 7.0
            exit_note = f'{top_60_broker} 60日主力仍在近5日買超中（持續布局）'
        elif top_60_broker in recent_buy_names_1d:
            exit_score = 5.0
            exit_note = f'{top_60_broker} 60日主力今日仍買超'
        elif top_60_broker in recent_sell_names_5d:
            exit_score = 0.0
            exit_note = f'⚠️ {top_60_broker} 60日主力近5日已轉賣超（疑似出脫）'
        elif top_60_broker in recent_sell_names_1d:
            exit_score = 1.0
            exit_note = f'⚠️ {top_60_broker} 60日主力今日轉賣超'
        else:
            exit_score = 3.0
            exit_note = f'{top_60_broker} 60日主力近期無明顯動作'
    else:
        exit_note = '無主力追蹤資料'

    # 多期間一致性（5分）
    period_score = 0.0
    period_note = ''
    period_directions = []
    for label, bd in [('1d', b1), ('5d', b5), ('20d', b20), ('60d', b60)]:
        tb = bd.get('top_buy_net')
        ts = bd.get('top_sell_net')
        if tb is not None and ts is not None:
            if abs(tb) > abs(ts):
                period_directions.append('buy')
            else:
                period_directions.append('sell')

    if len(period_directions) >= 3:
        buy_pct = period_directions.count('buy') / len(period_directions)
        if buy_pct >= 0.75:
            period_score = 5.0
            period_note = '多期間方向一致偏多'
        elif buy_pct >= 0.5:
            period_score = 3.0
            period_note = '多期間方向分歧'
        else:
            period_note = '多期間方向偏空'
    else:
        period_note = '期間資料不足'

    dim.score = long_score + exit_score + period_score
    dim.breakdown = {
        'long_term': round(long_score, 1),
        'long_note': long_note,
        'exit_detect': round(exit_score, 1),
        'exit_note': exit_note,
        'period_align': round(period_score, 1),
        'period_note': period_note,
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
        (inst.breakdown.get('foreign', 0), inst.breakdown.get('foreign_note', '')),
        (inst.breakdown.get('foreign_align', 0), inst.breakdown.get('align_note', '')),
        (own.breakdown.get('whale', 0), own.breakdown.get('whale_note', '')),
        (own.breakdown.get('retail', 0), own.breakdown.get('retail_note', '')),
        (broker.breakdown.get('long_term', 0), broker.breakdown.get('long_note', '')),
        (broker.breakdown.get('exit_detect', 0), broker.breakdown.get('exit_note', '')),
        (sent.breakdown.get('margin', 0), sent.breakdown.get('margin_note', '')),
        (sent.breakdown.get('squeeze', 0), sent.breakdown.get('squeeze_note', '')),
    ]
    # 加入轉折偵測
    turning = inst.breakdown.get('trust_turning', '')
    if turning:
        items.append((5, turning))
    holders = own.breakdown.get('holders_info', '')
    if holders:
        items.append((1, holders))
    top = sorted([(s, n) for s, n in items if s > 0 and n], reverse=True)[:4]
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
