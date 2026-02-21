"""
籌碼面評分引擎 — 四維度版（v2）
總分 0-100 分

維度一：法人動能（30分）
  投信趨勢（10分）+ 外資趨勢（9分）+ 自營商趨勢（6分）+ 三大法人一致性（5分）

維度二：股東結構（30分）
  大戶持股趨勢（12分）：1週(3) + 4週(4) + 13週(5) 三區間
  股東人數趨勢（10分）：1週(2) + 4週(3) + 13週(5) 三區間（相對比例）
  平均張數（8分）：1週(2) + 4週(3) + 13週(3) 三區間（相對比例）

維度三：分點主力（20分）
  各期間方向加權（8分）：60d(3)+20d(2)+10d(1.5)+5d(1)+1d(0.5)
  主力行為追蹤（7分）
  多時框量能仲裁（5分）

維度四：市場情緒（20分）
  融資安定度（8分）：比率制（今日相對5日均值）
  融券動向（6分）：比率制（今日相對5日均值）
  券資比（6分）：分級制
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


# ================================================================
# 維度一：法人動能（30分）
# 投信(10) + 外資(9) + 自營商(6) + 一致性(5)
# ================================================================

def score_institutional(data: dict) -> DimensionScore:
    dim = DimensionScore(max_score=30.0)

    trust_5d = data.get('trust_buy_5d') or 0
    trust_days = data.get('trust_consecutive_days') or 0
    foreign_5d = data.get('foreign_buy_5d') or 0
    foreign_days = data.get('foreign_consecutive_days') or 0
    dealer_5d = data.get('dealer_buy_5d') or 0
    dealer_days = data.get('dealer_consecutive_days') or 0
    daily = data.get('institutional_daily') or []

    # === 投信趨勢（10分）— 分級制 ===
    trust_score = 0.0
    if trust_5d > 0:
        if trust_days >= 5:
            trust_score = 10.0
        elif trust_days >= 3:
            trust_score = 8.0
        else:
            trust_score = 5.0  # 連買 1-2 天
    elif abs(trust_5d) < 100:
        trust_score = 2.0  # 幾乎中性
    trust_note = (
        f'投信近5日買超 {trust_5d:,} 張（連續 {trust_days} 天）' if trust_5d > 0 else
        f'投信近5日賣超 {abs(trust_5d):,} 張' if trust_5d < 0 else
        '投信無明顯動作'
    )

    # 轉折偵測（投信）
    trust_turning = ''
    if len(daily) >= 5:
        trust_vals = [d.get('trust_net') or 0 for d in daily[:5]]
        if trust_vals[0] > 0 and all(v <= 0 for v in trust_vals[2:5]):
            trust_turning = '⚡ 投信疑似轉買超'
        elif trust_vals[0] < 0 and all(v > 0 for v in trust_vals[2:5]):
            trust_turning = '⚠️ 投信疑似轉賣超'

    # === 外資趨勢（9分）— 分級制 ===
    foreign_score = 0.0
    if foreign_5d > 0:
        if foreign_days >= 5:
            foreign_score = 9.0
        elif foreign_days >= 3:
            foreign_score = 7.0
        else:
            foreign_score = 4.0
    elif abs(foreign_5d) < 200:
        foreign_score = 1.0  # 幾乎中性
    foreign_note = (
        f'外資近5日買超 {foreign_5d:,} 張（連續 {foreign_days} 天）' if foreign_5d > 0 else
        f'外資近5日賣超 {abs(foreign_5d):,} 張' if foreign_5d < 0 else
        '外資無明顯動作'
    )

    # === 自營商趨勢（6分）— 短線操作，看連續天數 ===
    dealer_score = 0.0
    if dealer_5d > 0:
        if dealer_days >= 3:
            dealer_score = 6.0
        else:
            dealer_score = 4.0  # 連買 1-2 天
    elif abs(dealer_5d) < 100:
        dealer_score = 2.0  # 幾乎中性
    dealer_note = (
        f'自營商近5日買超 {dealer_5d:,} 張（連續 {dealer_days} 天）' if dealer_5d > 0 else
        f'自營商近5日賣超 {abs(dealer_5d):,} 張' if dealer_5d < 0 else
        '自營商無明顯動作'
    )

    # === 三大法人一致性（5分）===
    align_score = 0.0
    align_note = ''
    buy_count = sum(1 for v in [trust_5d, foreign_5d, dealer_5d] if v > 0)

    if buy_count == 3:
        align_score = 5.0
        align_note = '三大法人同步買超（籌碼方向一致）'
    elif buy_count == 2:
        align_score = 3.0
        sellers = [n for n, v in [('投信', trust_5d), ('外資', foreign_5d), ('自營商', dealer_5d)] if v < 0]
        align_note = f'二買一賣（{"、".join(sellers)}賣超）'
    elif buy_count == 1:
        align_score = 1.0
        buyers = [n for n, v in [('投信', trust_5d), ('外資', foreign_5d), ('自營商', dealer_5d)] if v > 0]
        align_note = f'土洋對作：僅{"、".join(buyers)}買超'
    else:
        align_note = '三大法人均賣超'

    dim.score = trust_score + foreign_score + dealer_score + align_score
    dim.breakdown = {
        'trust': round(trust_score, 1),
        'trust_note': trust_note,
        'trust_turning': trust_turning,
        'foreign': round(foreign_score, 1),
        'foreign_note': foreign_note,
        'dealer': round(dealer_score, 1),
        'dealer_note': dealer_note,
        'dealer_5d': dealer_5d,
        'foreign_align': round(align_score, 1),
        'align_note': align_note,
    }
    return dim


# ================================================================
# 維度二：股東結構（30分）
# 大戶持股(12) + 股東人數(10) + 平均張數(8)
# 各子項均採 1週 + 4週 + 13週 三區間評分
# ================================================================

def score_ownership(data: dict) -> DimensionScore:
    dim = DimensionScore(max_score=30.0)

    weekly = data.get('ownership_weekly') or []

    def _whale(idx):
        return weekly[idx].get('whale_400_pct') if idx < len(weekly) else None

    def _holders(idx):
        return weekly[idx].get('total_holders') if idx < len(weekly) else None

    def _avg(idx):
        return weekly[idx].get('avg_shares') if idx < len(weekly) else None

    # === 大戶持股趨勢（12分）= 1週(3) + 4週(4) + 13週(5) ===
    whale_score = 0.0
    whale_notes = []
    whale_warning = ''

    w_now = _whale(0)
    w_1w  = _whale(1)
    w_4w  = _whale(3)  if len(weekly) >= 4  else None
    w_13w = _whale(12) if len(weekly) >= 13 else None

    if w_now is not None:
        # 1週（3分）
        if w_1w is not None:
            d = w_now - w_1w
            if d > 0.1:
                whale_score += 3.0; whale_notes.append(f'1週 {d:+.2f}%▲')
            elif d >= 0:
                whale_score += 1.0; whale_notes.append(f'1週 {d:+.2f}%→')
            else:
                whale_notes.append(f'1週 {d:+.2f}%▼')
            if d > 0.5:
                whale_warning = f'🔥 大戶1週積極增持 {d:+.2f}%，動能強勁'

        # 4週（4分）
        if w_4w is not None:
            d = w_now - w_4w
            if d > 0.3:
                whale_score += 4.0; whale_notes.append(f'4週 {d:+.2f}%▲')
            elif d > 0.1:
                whale_score += 3.0; whale_notes.append(f'4週 {d:+.2f}%↑')
            elif d >= 0:
                whale_score += 1.0; whale_notes.append(f'4週 {d:+.2f}%→')
            else:
                whale_notes.append(f'4週 {d:+.2f}%▼')

        # 13週（5分）
        if w_13w is not None:
            d = w_now - w_13w
            if d > 0.5:
                whale_score += 5.0; whale_notes.append(f'13週 {d:+.2f}%▲')
            elif d > 0.3:
                whale_score += 4.0; whale_notes.append(f'13週 {d:+.2f}%↑')
            elif d > 0.1:
                whale_score += 3.0; whale_notes.append(f'13週 {d:+.2f}%↗')
            elif d >= 0:
                whale_score += 1.0; whale_notes.append(f'13週 {d:+.2f}%→')
            else:
                whale_notes.append(f'13週 {d:+.2f}%▼')

    whale_note = (
        f'大戶持股 {w_now:.2f}%（{", ".join(whale_notes)}）'
        if w_now is not None and whale_notes else '大戶持股資料不足'
    )

    # === 股東人數趨勢（10分）= 1週(2) + 4週(3) + 13週(5)（相對比例）===
    holders_score = 0.0
    holders_notes = []

    h_now  = _holders(0)
    h_1w   = _holders(1)
    h_4w   = _holders(3)  if len(weekly) >= 4  else None
    h_13w  = _holders(12) if len(weekly) >= 13 else None

    if h_now is not None:
        # 1週（2分）
        if h_1w and h_1w > 0:
            pct = (h_now - h_1w) / h_1w * 100
            if pct < -0.3:
                holders_score += 2.0; holders_notes.append(f'1週 {pct:+.2f}%▼')
            elif pct < 0:
                holders_score += 1.0; holders_notes.append(f'1週 {pct:+.2f}%↘')
            else:
                holders_notes.append(f'1週 {pct:+.2f}%▲')

        # 4週（3分）
        if h_4w and h_4w > 0:
            pct = (h_now - h_4w) / h_4w * 100
            if pct < -1.0:
                holders_score += 3.0; holders_notes.append(f'4週 {pct:+.2f}%▼')
            elif pct < -0.5:
                holders_score += 2.0; holders_notes.append(f'4週 {pct:+.2f}%↓')
            elif pct < 0:
                holders_score += 1.0; holders_notes.append(f'4週 {pct:+.2f}%↘')
            else:
                holders_notes.append(f'4週 {pct:+.2f}%▲')

        # 13週（5分）
        if h_13w and h_13w > 0:
            pct = (h_now - h_13w) / h_13w * 100
            if pct < -2.0:
                holders_score += 5.0; holders_notes.append(f'13週 {pct:+.2f}%▼')
            elif pct < -1.0:
                holders_score += 4.0; holders_notes.append(f'13週 {pct:+.2f}%↓')
            elif pct < -0.5:
                holders_score += 3.0; holders_notes.append(f'13週 {pct:+.2f}%↘')
            elif pct < 0:
                holders_score += 1.0; holders_notes.append(f'13週 {pct:+.2f}%→')
            else:
                holders_notes.append(f'13週 {pct:+.2f}%▲')

    holders_note = (
        f'股東人數 {h_now:,} 人（{", ".join(holders_notes)}）'
        if h_now is not None and holders_notes else '股東人數資料不足'
    )

    # === 平均張數（8分）= 1週(2) + 4週(3) + 13週(3)（股東方向 + 均張相對比例）===
    avg_score = 0.0
    avg_notes = []

    a_now  = _avg(0)
    a_1w   = _avg(1)
    a_4w   = _avg(3)  if len(weekly) >= 4  else None
    a_13w  = _avg(12) if len(weekly) >= 13 else None

    if a_now is not None and h_now is not None:
        # 1週（2分）
        if h_1w is not None and a_1w is not None:
            h_down = h_now < h_1w
            a_up = a_now > a_1w
            if h_down and a_up:
                avg_score += 2.0
                pct = (a_now - a_1w) / a_1w * 100 if a_1w > 0 else 0
                avg_notes.append(f'1週均張 {pct:+.1f}%▲（股東減）')
            elif h_down:
                avg_score += 1.0
                avg_notes.append(f'1週股東減，均張持平')

        # 4週（3分）
        if h_4w is not None and a_4w is not None:
            h_down = h_now < h_4w
            pct = (a_now - a_4w) / a_4w * 100 if a_4w > 0 else 0
            if h_down and pct > 1.0:
                avg_score += 3.0; avg_notes.append(f'4週均張 {pct:+.1f}%▲（股東減）')
            elif h_down and pct > 0:
                avg_score += 2.0; avg_notes.append(f'4週均張 {pct:+.1f}%↑（股東減）')
            elif h_down:
                avg_score += 1.0; avg_notes.append(f'4週股東減，均張持平')

        # 13週（3分）
        if h_13w is not None and a_13w is not None:
            h_down = h_now < h_13w
            pct = (a_now - a_13w) / a_13w * 100 if a_13w > 0 else 0
            if h_down and pct > 2.0:
                avg_score += 3.0; avg_notes.append(f'13週均張 {pct:+.1f}%▲（股東減）')
            elif h_down and pct > 0:
                avg_score += 2.0; avg_notes.append(f'13週均張 {pct:+.1f}%↑（股東減）')
            elif h_down:
                avg_score += 1.0; avg_notes.append(f'13週股東減，均張持平')

    avg_note = (
        f'均張 {a_now:.2f} 張/人（{", ".join(avg_notes)}）' if a_now is not None and avg_notes else
        f'均張 {a_now:.2f} 張/人（無明顯集中訊號）' if a_now is not None else
        '平均張數資料不足'
    )

    dim.score = _clamp(whale_score + holders_score + avg_score, 0, 30)
    dim.breakdown = {
        'whale': round(whale_score, 1),
        'whale_note': whale_note,
        'whale_warning': whale_warning,
        'holders': round(holders_score, 1),
        'holders_note': holders_note,
        'avg_shares': round(avg_score, 1),
        'avg_note': avg_note,
    }
    return dim


# ================================================================
# 維度三：分點主力（20分）
# 各期間方向加權(8) + 主力追蹤(7) + 多時框仲裁(5)
# ================================================================

def _sum_top_n_net(broker_list: list, n: int = 5) -> int:
    total = 0
    for b in broker_list[:n]:
        try:
            net = int(str(b.get('net', '0')).replace(',', ''))
            total += net
        except (ValueError, TypeError):
            pass
    return total


def _parse_net(broker: dict) -> int:
    try:
        return int(str(broker.get('net', '0')).replace(',', ''))
    except (ValueError, TypeError):
        return 0


def _get_broker_net_map(broker_list: list, n: int = 15) -> dict:
    result = {}
    for b in broker_list[:n]:
        name = b.get('broker', '')
        if name:
            result[name] = _parse_net(b)
    return result


def score_broker(data: dict) -> DimensionScore:
    dim = DimensionScore(max_score=20.0)

    b60 = data.get('broker_60d') or {}
    b20 = data.get('broker_20d') or {}
    b10 = data.get('broker_10d') or {}
    b5  = data.get('broker_5d')  or {}
    b1  = data.get('broker_1d')  or {}

    # ================================================================
    # === 1. 各期間方向加權（8分）===
    # 60d(3) + 20d(2) + 10d(1.5) + 5d(1) + 1d(0.5)
    # 判斷：該期間前5買超合計 > 前5賣超合計 = 偏多
    # ================================================================
    period_weights = [
        ('60d', b60, 3.0),
        ('20d', b20, 2.0),
        ('10d', b10, 1.5),
        ('5d',  b5,  1.0),
        ('1d',  b1,  0.5),
    ]
    long_score = 0.0
    period_direction_notes = []

    for label, bd, weight in period_weights:
        buy_list  = bd.get('buy_brokers')  or []
        sell_list = bd.get('sell_brokers') or []
        buy_sum  = _sum_top_n_net(buy_list,  5)
        sell_sum = abs(_sum_top_n_net(sell_list, 5))
        if buy_sum > 0 or sell_sum > 0:
            if buy_sum > sell_sum:
                long_score += weight
                period_direction_notes.append(f'{label}偏多')
            else:
                period_direction_notes.append(f'{label}偏空')

    long_note = (
        f'各期間方向：{", ".join(period_direction_notes)}（分點方向分 {long_score:.1f}/8）'
        if period_direction_notes else '無分點資料'
    )

    # ================================================================
    # === 2. 主力行為追蹤（7分）===
    # 追蹤 60d Top5 買超券商在近期各時框動向
    # ================================================================
    track_score = 0.0
    track_note = ''
    intent_label = ''

    buy_top5_60 = b60.get('buy_brokers') or []
    buy_names_60 = [b.get('broker', '') for b in buy_top5_60[:5] if b.get('broker')]
    buy_net_60_map = {b.get('broker', ''): _parse_net(b) for b in buy_top5_60[:5]}

    if buy_names_60:
        buy_map_20  = _get_broker_net_map(b20.get('buy_brokers') or [])
        sell_map_20 = _get_broker_net_map(b20.get('sell_brokers') or [])
        buy_map_10  = _get_broker_net_map(b10.get('buy_brokers') or [])
        sell_map_10 = _get_broker_net_map(b10.get('sell_brokers') or [])
        buy_map_5   = _get_broker_net_map(b5.get('buy_brokers') or [])
        sell_map_5  = _get_broker_net_map(b5.get('sell_brokers') or [])

        confirmed_exit = []
        heavy_exit = []
        still_buying = []
        silent = []

        for name in buy_names_60:
            net_60   = buy_net_60_map.get(name, 0)
            sell_20  = abs(sell_map_20.get(name, 0))

            if sell_20 > 0 and net_60 > 0:
                ratio = sell_20 / net_60
                if ratio >= 1.0:
                    confirmed_exit.append((name, sell_20, net_60, ratio))
                elif ratio >= 0.5:
                    heavy_exit.append((name, sell_20, net_60, ratio))
                else:
                    if name in buy_map_5 or name in buy_map_10:
                        still_buying.append(name)
                    else:
                        silent.append(name)
            elif name in buy_map_5 or name in buy_map_10 or name in buy_map_20:
                still_buying.append(name)
            elif name in sell_map_5 or name in sell_map_10:
                heavy_exit.append((name, abs(sell_map_5.get(name, sell_map_10.get(name, 0))), net_60, 0))
            else:
                silent.append(name)

        all_20d_names = set(buy_map_20.keys()) | set(sell_map_20.keys())
        overlap_count = sum(1 for n in buy_names_60 if n in all_20d_names)

        if confirmed_exit:
            names_str = '、'.join(
                f'{n}（賣超 {s:,} 張，原買 {b:,} 張）' for n, s, b, _ in confirmed_exit[:2]
            )
            track_score = 0.0
            intent_label = '🔴 主力反手出脫'
            track_note = f'⚠️ 60日主力反手：{names_str}'
        elif heavy_exit:
            names_str = '、'.join(
                f'{n}（20d 賣超 {s:,} / 60d 買超 {b:,} 張）' for n, s, b, _ in heavy_exit[:2]
            )
            track_score = 2.0
            intent_label = '🟡 主力疑似出脫'
            track_note = f'⚠️ {names_str}，出脫比例偏高'
        elif len(still_buying) >= 3:
            track_score = 7.0
            intent_label = '🟢 主力持續布局'
            track_note = f'60d 前5大主力中 {len(still_buying)} 家仍在近期買超（持續布局）'
        elif len(still_buying) >= 1:
            track_score = 4.0
            intent_label = '🟡 主力行為分歧'
            track_note = f'60d 前5大主力中 {len(still_buying)} 家仍買超，{len(silent)} 家沉默'
        elif overlap_count < 2:
            buy_sum_20  = _sum_top_n_net(b20.get('buy_brokers') or [], 5)
            sell_sum_20 = abs(_sum_top_n_net(b20.get('sell_brokers') or [], 5))
            if buy_sum_20 > sell_sum_20:
                track_score = 4.0
                intent_label = '🔵 新主力接手'
                track_note = f'60d 舊主力已撤，近20日有新買盤進場（買超 {buy_sum_20:,} 張）'
            else:
                track_score = 1.0
                intent_label = '⚫ 主力撤場'
                track_note = '60d 舊主力撤離，近20日新買盤不足，需觀望'
        else:
            track_score = 3.0
            intent_label = '🟡 主力觀望'
            track_note = '60d 前5大主力近期無明顯動作（沉默觀望）'
    else:
        track_note = '無主力追蹤資料'
        intent_label = '⚪ 無資料'

    # ================================================================
    # === 3. 多時框量能仲裁（5分）===
    # ================================================================
    arb_score = 0.0
    arb_note = ''
    period_details = []

    for label, bd in [('1d', b1), ('5d', b5), ('10d', b10), ('20d', b20), ('60d', b60)]:
        buy_list  = bd.get('buy_brokers')  or []
        sell_list = bd.get('sell_brokers') or []
        buy_sum  = _sum_top_n_net(buy_list,  5)
        sell_sum = abs(_sum_top_n_net(sell_list, 5))
        if buy_sum > 0 or sell_sum > 0:
            direction = 'buy' if buy_sum >= sell_sum else 'sell'
            period_details.append((label, direction, buy_sum, sell_sum))

    if len(period_details) >= 3:
        buy_count = sum(1 for _, d, _, _ in period_details if d == 'buy')
        buy_pct   = buy_count / len(period_details)

        dir_60 = next((d for l, d, _, _ in period_details if l == '60d'), None)
        dir_20 = next((d for l, d, _, _ in period_details if l == '20d'), None)
        conflict_60_20 = dir_60 and dir_20 and dir_60 != dir_20

        if conflict_60_20:
            sell_20_total = next((s for l, d, b, s in period_details if l == '20d' and d == 'sell'), 0)
            buy_60_total  = next((b for l, d, b, s in period_details if l == '60d' and d == 'buy'), 0)
            if sell_20_total > 0 and buy_60_total > 0:
                conflict_ratio = sell_20_total / buy_60_total
                if conflict_ratio >= 0.5:
                    arb_score = 1.0
                    arb_note = f'60d 偏多 vs 20d 偏空（衝突），20d 賣超達 60d 買超 {conflict_ratio:.0%}（主力轉向疑慮）'
                elif conflict_ratio >= 0.3:
                    arb_score = 2.0
                    arb_note = f'60d 偏多 vs 20d 偏空，20d 賣超量 {conflict_ratio:.0%}（短期壓力）'
                else:
                    arb_score = 3.0
                    arb_note = f'60d 偏多 vs 20d 偏空，但 20d 賣超量僅 {conflict_ratio:.0%}（影響有限）'
            else:
                arb_score = 2.0
                arb_note = '60d 與 20d 方向衝突，量能資料不足'
        elif buy_pct >= 0.8:
            arb_score = 5.0
            arb_note = '多時框前5大方向高度一致偏多'
        elif buy_pct >= 0.6:
            arb_score = 4.0
            sell_periods = [l for l, d, _, _ in period_details if d == 'sell']
            arb_note = f'多時框偏多，{",".join(sell_periods)} 偏空（小分歧）'
        elif buy_pct >= 0.4:
            arb_score = 2.0
            arb_note = '多時框方向分歧，多空力道接近'
        else:
            arb_note = '多時框前5大方向偏空'
    else:
        arb_note = '期間資料不足'

    dim.score = long_score + track_score + arb_score
    dim.breakdown = {
        'long_term': round(long_score, 1),
        'long_note': long_note,
        'exit_detect': round(track_score, 1),
        'exit_note': track_note,
        'intent_label': intent_label,
        'period_align': round(arb_score, 1),
        'period_note': arb_note,
    }
    return dim


# ================================================================
# 維度四：市場情緒（20分）
# 融資安定度(8) + 融券動向(6) + 券資比(6)
# 融資/融券均使用「今日相對5日均值」比率制
# ================================================================

def score_sentiment(data: dict) -> DimensionScore:
    dim = DimensionScore(max_score=20.0)

    margin_daily = data.get('margin_daily') or []
    short_ratio  = data.get('short_ratio')  or 0

    def _rate_score(daily_vals: list, positive_is_decrease: bool) -> tuple[float, str, float]:
        """
        計算今日值相對5日均絕對值的比率，回傳 (score, note_suffix, rate)。
        positive_is_decrease=True 表示「減少」方向為正面（融資）
        positive_is_decrease=False 表示「增加」方向為正面（不適用此函式）
        """
        if len(daily_vals) < 2:
            return 3.0, '資料不足（基礎分）', 0.0
        today = daily_vals[0]
        avg_abs = sum(abs(x) for x in daily_vals) / len(daily_vals)
        if avg_abs == 0:
            return 3.0, '近5日無明顯波動（基礎分）', 0.0
        rate = today / avg_abs * 100
        return rate, '', avg_abs

    # === 融資安定度（8分）===
    margin_vals = [d.get('margin_change') for d in margin_daily if d.get('margin_change') is not None]
    margin_score = 0.0
    margin_note  = ''

    if len(margin_vals) >= 2:
        today_m = margin_vals[0]
        avg_abs_m = sum(abs(x) for x in margin_vals) / len(margin_vals)
        if avg_abs_m > 0:
            rate_m = today_m / avg_abs_m * 100  # 今日相對均值的%（負=減少）
            if rate_m < -150:
                margin_score = 8.0
                margin_note = f'今日融資大幅減少 {abs(today_m):,} 張（相對均值 {rate_m:.0f}%，籌碼高度健康）'
            elif rate_m < -80:
                margin_score = 6.0
                margin_note = f'今日融資明顯減少 {abs(today_m):,} 張（相對均值 {rate_m:.0f}%）'
            elif rate_m < -30:
                margin_score = 4.0
                margin_note = f'今日融資略有減少 {abs(today_m):,} 張（相對均值 {rate_m:.0f}%）'
            elif rate_m <= 30:
                margin_score = 3.0
                margin_note = f'今日融資幾乎持平（相對均值 {rate_m:.0f}%）'
            elif rate_m < 100:
                margin_score = 1.0
                margin_note = f'今日融資略有增加 {today_m:,} 張（相對均值 {rate_m:.0f}%）'
            else:
                margin_score = 0.0
                margin_note = f'今日融資大幅增加 {today_m:,} 張（相對均值 {rate_m:.0f}%，散戶追價）'
        else:
            margin_score = 3.0
            margin_note = '近5日融資無明顯波動（基礎分）'
    elif margin_vals:
        margin_score = 3.0
        margin_note = f'融資資料不足1日，今日增減 {margin_vals[0]:,} 張'
    else:
        margin_note = '融資資料不足'

    # === 融券動向（6分）===
    # === 融券動向（6分）===
    # 融券增加 = 散戶看空 = 軋空燃料增加 = 正面訊號
    short_vals = [d.get('short_change') for d in margin_daily if d.get('short_change') is not None]
    short_score = 0.0
    short_note  = ''

    if len(short_vals) >= 2:
        today_s = short_vals[0]
        avg_abs_s = sum(abs(x) for x in short_vals) / len(short_vals)
        if avg_abs_s > 0:
            rate_s = today_s / avg_abs_s * 100  # 正=增加（軋空燃料增加）
            if rate_s > 150:
                short_score = 6.0
                short_note = f'今日融券大量增加 {today_s:,} 張（相對均值 +{rate_s:.0f}%，軋空潛力大增）'
            elif rate_s > 80:
                short_score = 4.0
                short_note = f'今日融券明顯增加 {today_s:,} 張（相對均值 +{rate_s:.0f}%，軋空燃料增）'
            elif rate_s > 30:
                short_score = 3.0
                short_note = f'今日融券略有增加 {today_s:,} 張（相對均值 +{rate_s:.0f}%）'
            elif rate_s >= -30:
                short_score = 3.0
                short_note = f'今日融券幾乎持平（相對均值 {rate_s:.0f}%）'
            elif rate_s > -100:
                short_score = 1.0
                short_note = f'今日融券略有回補 {abs(today_s):,} 張（相對均值 {rate_s:.0f}%，空方下車）'
            else:
                short_score = 0.0
                short_note = f'今日融券大量回補 {abs(today_s):,} 張（相對均值 {rate_s:.0f}%，軋空力道減弱）'
        else:
            short_score = 3.0
            short_note = '近5日融券無明顯波動（基礎分）'
    elif short_vals:
        short_score = 3.0
        short_note = f'融券資料不足，今日增減 {short_vals[0]:,} 張'
    else:
        short_note = '融券資料不足'

    # === 券資比（6分）===
    squeeze_score = 0.0
    squeeze_note  = ''
    if short_ratio >= 30:
        squeeze_score = 6.0
        squeeze_note = f'券資比 {short_ratio:.1f}%（軋空潛力高）'
    elif short_ratio >= 15:
        squeeze_score = 3.0
        squeeze_note = f'券資比 {short_ratio:.1f}%（中等軋空壓力）'
    else:
        squeeze_note = f'券資比 {short_ratio:.1f}%（軋空壓力不足）'

    dim.score = margin_score + short_score + squeeze_score
    dim.breakdown = {
        'margin': round(margin_score, 1),
        'margin_note': margin_note,
        'short_change': round(short_score, 1),
        'short_note': short_note,
        'squeeze': round(squeeze_score, 1),
        'squeeze_note': squeeze_note,
    }
    return dim


# ================================================================
# 策略建議 / 亮點 / 風險
# ================================================================

def _build_strategy(inst: DimensionScore, own: DimensionScore,
                    broker: DimensionScore, sent: DimensionScore,
                    data: dict, total: float, low_volume: bool) -> str:
    parts = []

    trust       = inst.breakdown.get('trust', 0)
    foreign     = inst.breakdown.get('foreign', 0)
    dealer      = inst.breakdown.get('dealer', 0)
    trust_days  = data.get('trust_consecutive_days') or 0
    foreign_5d  = data.get('foreign_buy_5d') or 0
    dealer_5d   = data.get('dealer_buy_5d') or 0

    # 法人面
    if trust >= 8 and foreign >= 4:
        parts.append(f'法人同步買超（投信連{trust_days}天），可順勢偏多，關注投信何時停止加碼作為減碼訊號')
    elif trust >= 8 and foreign <= 0:
        parts.append(f'投信連買{trust_days}天但外資賣超 {abs(foreign_5d):,} 張，留意土洋對作風險，若外資轉買可加碼')
    elif trust <= 0 and foreign >= 4:
        parts.append('外資買超但投信未跟進，可能為外資短期操作，建議等投信同步轉買再進場')
    elif trust <= 0 and foreign <= 0:
        parts.append('法人雙空，不宜追多，等待法人轉向訊號')

    if dealer >= 4:
        parts.append(f'自營商同步買超 {dealer_5d:,} 張，短線動能支撐')

    # 轉折
    turning = inst.breakdown.get('trust_turning', '')
    if turning:
        parts.append('⚠ 投信出現轉折跡象，建議減碼觀察')

    # 主力面
    intent    = broker.breakdown.get('intent_label', '')
    long_score = broker.breakdown.get('long_term', 0)

    if '🔴' in intent:
        parts.append('主力出脫訊號明確，不宜加碼，已持有者考慮分批出場')
    elif '🟡' in intent and '疑似' in intent:
        parts.append('部分主力出脫跡象，建議觀察 5 日後主力動向是否回穩再決定')
    elif '🟢' in intent:
        if long_score >= 5:
            parts.append('主力持續布局且多期間方向偏多，可作為買進參考，回檔可分批承接')
        else:
            parts.append('主力仍在場但整體賣壓較大，宜小量試單，不重倉')
    elif '🔵' in intent:
        parts.append('新主力進場但尚未確認意圖，建議觀察 10~20 日買超持續性再跟進')
    elif '⚫' in intent:
        parts.append('主力撤場觀望，流動性風險升高，建議迴避')

    # 股東結構
    whale   = own.breakdown.get('whale', 0)
    holders = own.breakdown.get('holders', 0)
    whale_warning = own.breakdown.get('whale_warning', '')

    if whale >= 8 and holders >= 6:
        parts.append('籌碼持續集中（大戶增持＋股東減少），中線偏多訊號')
    elif whale <= 0 and holders <= 0:
        parts.append('籌碼分散中（大戶減持＋股東增加），不宜追高')
    if whale_warning:
        parts.append('大戶短期急增，留意是否為特定事件拉抬')

    # 情緒面
    margin       = sent.breakdown.get('margin', 0)
    short_change = sent.breakdown.get('short_change', 0)
    squeeze      = sent.breakdown.get('squeeze', 0)
    short_ratio  = data.get('short_ratio') or 0

    if margin >= 6:
        parts.append('融資今日明顯減少，浮額消化健康')
    elif margin <= 1:
        parts.append('融資今日大幅增加，散戶追價偏高，注意過熱回檔風險')

    if short_change >= 4:
        parts.append('融券今日明顯增加，累積軋空燃料，若逢法人買超易有軋空行情')
    elif short_change <= 1:
        parts.append('融券今日大量回補，空方下車，軋空力道減弱')

    if squeeze >= 5:
        parts.append(f'券資比 {short_ratio:.1f}%，軋空壓力大，若搭配法人買超可能觸發軋空行情')

    if low_volume:
        parts.append('⚠ 成交量極低（<100張），流動性不足，進出場滑價風險大')

    if not parts:
        if total > 60:
            return '多項指標偏多但未出現極端訊號，可小量布局並設停損追蹤'
        else:
            return '多項指標中性偏弱，建議觀望為主，等待明確轉向訊號'

    return '；'.join(parts)


def generate_highlights(inst: DimensionScore, own: DimensionScore,
                        broker: DimensionScore, sent: DimensionScore) -> list[str]:
    items = [
        (inst.breakdown.get('trust', 0),        inst.breakdown.get('trust_note', '')),
        (inst.breakdown.get('foreign', 0),       inst.breakdown.get('foreign_note', '')),
        (inst.breakdown.get('dealer', 0),        inst.breakdown.get('dealer_note', '')),
        (inst.breakdown.get('foreign_align', 0), inst.breakdown.get('align_note', '')),
        (own.breakdown.get('whale', 0),          own.breakdown.get('whale_note', '')),
        (own.breakdown.get('holders', 0),        own.breakdown.get('holders_note', '')),
        (own.breakdown.get('avg_shares', 0),     own.breakdown.get('avg_note', '')),
        (broker.breakdown.get('long_term', 0),   broker.breakdown.get('long_note', '')),
        (broker.breakdown.get('exit_detect', 0), broker.breakdown.get('exit_note', '')),
        (sent.breakdown.get('margin', 0),        sent.breakdown.get('margin_note', '')),
        (sent.breakdown.get('short_change', 0),  sent.breakdown.get('short_note', '')),
        (sent.breakdown.get('squeeze', 0),       sent.breakdown.get('squeeze_note', '')),
    ]
    turning = inst.breakdown.get('trust_turning', '')
    if turning:
        items.append((5, turning))
    whale_warning = own.breakdown.get('whale_warning', '')
    if whale_warning:
        items.append((5, whale_warning))

    # 多方亮點（正分前 4 名）
    bullish = sorted([(s, n) for s, n in items if s > 0 and n], reverse=True)[:4]
    result = [f"✅ {note}" for _, note in bullish]

    # 空方警訊（負分前 3 名）
    bearish = sorted([(s, n) for s, n in items if s < 0 and n])[:3]
    result += [f"⚠️ {note}" for _, note in bearish]

    return result


def generate_risks(data: dict, total: float) -> list[str]:
    risks = []
    trust_5d        = data.get('trust_buy_5d') or 0
    foreign_5d      = data.get('foreign_buy_5d') or 0
    short_ratio     = data.get('short_ratio') or 0
    main_force_net  = data.get('main_force_net_5d') or 0
    margin_daily    = data.get('margin_daily') or []

    if foreign_5d < 0 and trust_5d > 0 and total > 70:
        risks.append('土洋對作：本土法人與外資方向相反，需留意外資賣壓')

    # 融資今日大增 → 散戶過熱
    margin_vals = [d.get('margin_change') for d in margin_daily if d.get('margin_change') is not None]
    if margin_vals and margin_vals[0] > 0:
        avg_abs = sum(abs(x) for x in margin_vals) / len(margin_vals)
        if avg_abs > 0 and margin_vals[0] / avg_abs > 1.0 and total > 70:
            risks.append('融資今日大幅增加，散戶追價明顯，需提防短期過熱')

    if short_ratio > 50:
        risks.append(f'券資比過高（{short_ratio:.1f}%），雖有軋空機會但也可能反映基本面疑慮')

    if main_force_net < -5000 and total > 60:
        risks.append(f'主力近5日大幅賣超 {abs(main_force_net):,} 張，需留意主力出貨')

    return risks


# ================================================================
# 主計算入口
# ================================================================

def calculate(data: dict) -> ChipScore:
    result = ChipScore()

    total_vol  = data.get('total_volume_1d') or 0
    low_volume = total_vol > 0 and total_vol < 100

    result.institutional = score_institutional(data)
    result.ownership     = score_ownership(data)
    result.broker        = score_broker(data)
    result.sentiment     = score_sentiment(data)
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
        result.rating    = '強力買進'
        result.rating_en = 'Strong Buy'
    elif effective_total >= 60:
        result.rating    = '偏多操作'
        result.rating_en = 'Bullish'
    elif effective_total >= 40:
        result.rating    = '觀望/中性'
        result.rating_en = 'Neutral'
    elif effective_total >= 20:
        result.rating    = '偏空操作'
        result.rating_en = 'Bearish'
    else:
        result.rating    = '強力偏空'
        result.rating_en = 'Strong Sell'

    result.strategy = _build_strategy(
        result.institutional, result.ownership,
        result.broker, result.sentiment,
        data, effective_total, low_volume,
    )
    result.highlights = generate_highlights(
        result.institutional, result.ownership, result.broker, result.sentiment
    )
    result.risks = generate_risks(data, result.total)

    return result
