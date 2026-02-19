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
    - 大戶持股趨勢（12分）：50週緩升=佳，急速拉升=警示
    - 總股東人數趨勢（10分）：緩降=籌碼集中=佳
    - 平均張數交叉比較（8分）：股東少+平均張數多=集中
    """
    dim = DimensionScore(max_score=30.0)

    weekly = data.get('ownership_weekly') or []
    whale_this = data.get('whale_pct_this')
    total_holders = data.get('total_holders_this')
    avg_shares = data.get('avg_shares_this')

    # === 大戶持股趨勢（12分）===
    whale_score = 0.0
    whale_note = ''
    whale_warning = ''

    if whale_this is not None and len(weekly) >= 2:
        # 計算各時段變化
        def _get_whale(idx):
            if idx < len(weekly):
                return weekly[idx].get('whale_400_pct')
            return None

        w_1w = _get_whale(1)
        w_4w = _get_whale(3) if len(weekly) >= 4 else None
        w_13w = _get_whale(12) if len(weekly) >= 13 else None
        w_50w = weekly[-1].get('whale_400_pct') if len(weekly) >= 25 else None

        changes = []
        if w_1w is not None:
            changes.append(('1週', whale_this - w_1w))
        if w_4w is not None:
            changes.append(('4週', whale_this - w_4w))
        if w_13w is not None:
            changes.append(('13週', whale_this - w_13w))
        if w_50w is not None:
            changes.append(('長期', whale_this - w_50w))

        # 評分：以最長可用趨勢為主要依據
        long_change = changes[-1][1] if changes else 0
        short_change = changes[0][1] if changes else 0

        if long_change > 0:
            whale_score = _clamp(long_change * 4, 0, 12)
            trend_parts = [f'{label} {v:+.2f}%' for label, v in changes]
            whale_note = f'大戶持股趨勢上升（{", ".join(trend_parts)}）'

            # 急漲警示：短期漲幅 > 長期漲幅的50%，或 1 週變化超過 0.5%
            if len(changes) >= 2 and short_change > 0.5:
                whale_warning = f'⚡ 大戶短期急增 {short_change:+.2f}%，留意是否為特定事件'
            elif len(changes) >= 3 and changes[0][1] > changes[-1][1] * 0.5 and changes[0][1] > 0.3:
                whale_warning = f'⚡ 大戶近期加速增持，注意追高風險'
        elif long_change < 0:
            trend_parts = [f'{label} {v:+.2f}%' for label, v in changes]
            whale_note = f'大戶持股趨勢下降（{", ".join(trend_parts)}）'
        else:
            whale_note = f'大戶持股持平 {whale_this:.2f}%'
    else:
        whale_note = '大戶持股資料不足'

    # === 總股東人數趨勢（10分）===
    holders_score = 0.0
    holders_note = ''

    if total_holders is not None and len(weekly) >= 4:
        h_now = weekly[0].get('total_holders')
        h_4w = weekly[3].get('total_holders') if len(weekly) >= 4 else None
        h_13w = weekly[12].get('total_holders') if len(weekly) >= 13 else None
        h_long = weekly[-1].get('total_holders') if len(weekly) >= 25 else None

        if h_now is not None and h_4w is not None:
            h_4w_change = h_now - h_4w
            h_13w_change = (h_now - h_13w) if h_13w is not None else None
            h_long_change = (h_now - h_long) if h_long is not None else None

            # 股東人數下降 = 籌碼集中 = 正面
            if h_4w_change < 0:  # 近4週減少
                holders_score = _clamp(abs(h_4w_change) / 3000, 0, 6)
                holders_note = f'股東人數近4週減少 {abs(h_4w_change):,} 人（籌碼集中）'
                if h_13w_change is not None and h_13w_change < 0:
                    holders_score = _clamp(holders_score + 2, 0, 10)
                    holders_note += f'，13週亦減 {abs(h_13w_change):,} 人'
            elif h_4w_change > 0:
                holders_note = f'股東人數近4週增加 {h_4w_change:,} 人（籌碼分散）'
                if h_13w_change is not None and h_13w_change > 0:
                    holders_note += f'，13週亦增 {h_13w_change:,} 人'
            else:
                holders_note = f'股東人數近4週持平'

            holders_note += f'（目前 {h_now:,} 人）'
    else:
        holders_note = '股東人數資料不足'

    # === 平均張數交叉比較（8分）===
    avg_score = 0.0
    avg_note = ''

    if avg_shares is not None and len(weekly) >= 4:
        avg_now = weekly[0].get('avg_shares')
        avg_4w = weekly[3].get('avg_shares') if len(weekly) >= 4 else None
        h_now = weekly[0].get('total_holders')
        h_4w = weekly[3].get('total_holders') if len(weekly) >= 4 else None

        if avg_now is not None and avg_4w is not None and h_now is not None and h_4w is not None:
            avg_change = avg_now - avg_4w
            h_change = h_now - h_4w

            if h_change < 0 and avg_change > 0:
                # 股東減少 + 平均張數增加 = 籌碼集中 = 最佳
                avg_score = _clamp(avg_change * 4, 0, 8)
                avg_note = f'籌碼集中趨勢：股東減少且人均張數增加（{avg_4w:.2f} → {avg_now:.2f} 張/人）'
            elif h_change > 0 and avg_change < 0:
                # 股東增加 + 平均張數減少 = 籌碼分散
                avg_note = f'籌碼分散趨勢：股東增加且人均張數減少（{avg_4w:.2f} → {avg_now:.2f} 張/人）'
            elif h_change < 0 and avg_change <= 0:
                avg_score = 3.0
                avg_note = f'股東減少但人均張數持平（{avg_now:.2f} 張/人）'
            elif h_change > 0 and avg_change > 0:
                avg_score = 2.0
                avg_note = f'股東增加但人均張數亦增（{avg_4w:.2f} → {avg_now:.2f} 張/人），混合訊號'
            else:
                avg_note = f'股東人數與平均張數皆持平（{avg_now:.2f} 張/人）'
    else:
        avg_note = '平均張數資料不足'

    dim.score = whale_score + holders_score + avg_score
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


def _sum_top_n_net(broker_list: list, n: int = 5) -> int:
    """加總前 N 名券商的淨買/賣超張數"""
    total = 0
    for b in broker_list[:n]:
        try:
            net = int(str(b.get('net', '0')).replace(',', ''))
            total += net
        except (ValueError, TypeError):
            pass
    return total


def _parse_net(broker: dict) -> int:
    """解析券商 net 欄位為整數（buy + sell，sell 為負值）"""
    try:
        return int(str(broker.get('net', '0')).replace(',', ''))
    except (ValueError, TypeError):
        return 0


def _get_broker_net_map(broker_list: list, n: int = 15) -> dict:
    """回傳 {券商名稱: net張數} 字典，取前 n 名"""
    result = {}
    for b in broker_list[:n]:
        name = b.get('broker', '')
        if name:
            result[name] = _parse_net(b)
    return result


def score_broker(data: dict) -> DimensionScore:
    """
    維度三：分點主力（滿分 20 分）
    - 60日前五名方向（8分）：前5名合計淨買超 vs 賣超
    - 主力行為追蹤（7分）：逐家追蹤 60d Top5 在 1d/5d/10d/20d 的量能動向
    - 多時框量能仲裁（5分）：1d/5d/10d/20d/60d 前5加總方向，60d vs 20d 衝突時量能仲裁
    """
    dim = DimensionScore(max_score=20.0)

    # 取各期間資料
    b60 = data.get('broker_60d') or {}
    b20 = data.get('broker_20d') or {}
    b10 = data.get('broker_10d') or {}
    b5 = data.get('broker_5d') or {}
    b1 = data.get('broker_1d') or {}

    # ================================================================
    # === 1. 60日前五名方向（8分）===
    # ================================================================
    long_score = 0.0
    long_note = ''

    buy_top5_60 = b60.get('buy_brokers') or []
    sell_top5_60 = b60.get('sell_brokers') or []
    buy_sum_60 = _sum_top_n_net(buy_top5_60, 5)
    sell_sum_60 = abs(_sum_top_n_net(sell_top5_60, 5))
    buy_names_60 = [b.get('broker', '') for b in buy_top5_60[:5] if b.get('broker')]

    # 逐家建立 net 對照表（供後續追蹤使用）
    buy_net_60_map = {b.get('broker', ''): _parse_net(b) for b in buy_top5_60[:5]}

    if buy_sum_60 > 0 or sell_sum_60 > 0:
        net_direction_60 = buy_sum_60 - sell_sum_60
        if net_direction_60 > 0:
            if buy_sum_60 >= 5000:
                long_score = 8.0
            elif buy_sum_60 >= 2000:
                long_score = 6.0
            elif buy_sum_60 >= 500:
                long_score = 4.0
            else:
                long_score = 2.0
            long_note = f'60日前5大買超合計 {buy_sum_60:,} 張＞賣超 {sell_sum_60:,} 張（主力偏多）'
        else:
            long_note = f'60日前5大賣超 {sell_sum_60:,} 張＞買超 {buy_sum_60:,} 張（主力偏空）'
    else:
        long_note = '無60日分點資料'

    # ================================================================
    # === 2. 主力行為追蹤（7分）===
    # 60d Top5 買超券商在近期各時框動向，以量能為主要判斷依據
    # ================================================================
    track_score = 0.0
    track_note = ''
    intent_label = ''  # 主力意圖標籤

    if buy_names_60:
        # 各時框的 buy/sell 名稱→net 對照表
        buy_map_20 = _get_broker_net_map(b20.get('buy_brokers') or [])
        sell_map_20 = _get_broker_net_map(b20.get('sell_brokers') or [])
        buy_map_10 = _get_broker_net_map(b10.get('buy_brokers') or [])
        sell_map_10 = _get_broker_net_map(b10.get('sell_brokers') or [])
        buy_map_5 = _get_broker_net_map(b5.get('buy_brokers') or [])
        sell_map_5 = _get_broker_net_map(b5.get('sell_brokers') or [])
        buy_map_1 = _get_broker_net_map(b1.get('buy_brokers') or [])
        sell_map_1 = _get_broker_net_map(b1.get('sell_brokers') or [])

        # 對每家 60d Top5 做量能追蹤
        confirmed_exit = []   # 20d 賣超量 > 60d 買超量（完全反手）
        heavy_exit = []       # 20d 賣超量 > 60d 買超量 50%（疑似出脫）
        still_buying = []     # 仍在 5d 或 10d 買超名單
        silent = []           # 沒出現（沉默）

        for name in buy_names_60:
            net_60 = buy_net_60_map.get(name, 0)  # 60d 買超量（正值）
            # 取近期最明顯動向（20d 為主要觀察對象）
            sell_20 = abs(sell_map_20.get(name, 0))  # 20d 賣超量（取絕對值）
            buy_20 = buy_map_20.get(name, 0)

            if sell_20 > 0 and net_60 > 0:
                ratio = sell_20 / net_60
                if ratio >= 1.0:
                    confirmed_exit.append((name, sell_20, net_60, ratio))
                elif ratio >= 0.5:
                    heavy_exit.append((name, sell_20, net_60, ratio))
                else:
                    # 有在 20d 賣但量小，看是否近期仍買
                    if name in buy_map_5 or name in buy_map_10:
                        still_buying.append(name)
                    else:
                        silent.append(name)
            elif name in buy_map_5 or name in buy_map_10 or name in buy_map_20:
                still_buying.append(name)
            elif name in sell_map_5 or name in sell_map_10:
                # 在近期賣超但量少（前面已排除大量出脫）
                heavy_exit.append((name, abs(sell_map_5.get(name, sell_map_10.get(name, 0))), net_60, 0))
            else:
                silent.append(name)

        # 同時確認 name 在 20d 名單完全不重疊（新主力接手判斷）
        all_20d_names = set(buy_map_20.keys()) | set(sell_map_20.keys())
        overlap_count = sum(1 for n in buy_names_60 if n in all_20d_names)

        if confirmed_exit:
            names_str = '、'.join(f'{n}（賣超 {s:,} 張，原買 {b:,} 張）'
                                  for n, s, b, _ in confirmed_exit[:2])
            track_score = 0.0
            intent_label = '🔴 主力反手出脫'
            track_note = f'⚠️ 60日主力反手：{names_str}'
        elif heavy_exit:
            names_str = '、'.join(f'{n}（20d 賣超 {s:,} / 60d 買超 {b:,} 張）'
                                   for n, s, b, _ in heavy_exit[:2])
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
            # 60d 名單與 20d 名單幾乎不重疊
            buy_sum_20 = _sum_top_n_net(b20.get('buy_brokers') or [], 5)
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
    # 1d/5d/10d/20d/60d 各取前5名加總方向，60d vs 20d 衝突時量能仲裁
    # ================================================================
    arb_score = 0.0
    arb_note = ''
    period_details = []

    for label, bd in [('1d', b1), ('5d', b5), ('10d', b10), ('20d', b20), ('60d', b60)]:
        buy_list = bd.get('buy_brokers') or []
        sell_list = bd.get('sell_brokers') or []
        buy_sum = _sum_top_n_net(buy_list, 5)
        sell_sum = abs(_sum_top_n_net(sell_list, 5))
        if buy_sum > 0 or sell_sum > 0:
            direction = 'buy' if buy_sum >= sell_sum else 'sell'
            period_details.append((label, direction, buy_sum, sell_sum))

    if len(period_details) >= 3:
        buy_count = sum(1 for _, d, _, _ in period_details if d == 'buy')
        buy_pct = buy_count / len(period_details)

        # 60d vs 20d 衝突偵測
        dir_60 = next((d for l, d, _, _ in period_details if l == '60d'), None)
        dir_20 = next((d for l, d, _, _ in period_details if l == '20d'), None)
        conflict_60_20 = dir_60 and dir_20 and dir_60 != dir_20

        if conflict_60_20:
            # 量能仲裁：20d 賣超量 vs 60d 買超量的比例
            sell_20_total = next((s for l, d, b, s in period_details if l == '20d' and d == 'sell'), 0)
            buy_60_total = next((b for l, d, b, s in period_details if l == '60d' and d == 'buy'), 0)

            if sell_20_total > 0 and buy_60_total > 0:
                conflict_ratio = sell_20_total / buy_60_total
                if conflict_ratio >= 0.5:
                    arb_score = 1.0
                    arb_note = f'60d 偏多 vs 20d 偏空（衝突），20d 賣超量達 60d 買超量 {conflict_ratio:.0%}（主力轉向疑慮）'
                elif conflict_ratio >= 0.3:
                    arb_score = 2.0
                    arb_note = f'60d 偏多 vs 20d 偏空，20d 賣超量達 {conflict_ratio:.0%}（短期壓力）'
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
def _build_strategy(inst: DimensionScore, own: DimensionScore,
                    broker: DimensionScore, sent: DimensionScore,
                    data: dict, total: float, low_volume: bool) -> str:
    """依各維度實際結果動態組裝具體策略建議"""
    parts = []

    # --- 法人面建議 ---
    trust = inst.breakdown.get('trust', 0)
    foreign = inst.breakdown.get('foreign', 0)
    trust_days = data.get('trust_consecutive_days') or 0
    foreign_5d = data.get('foreign_buy_5d') or 0
    trust_5d = data.get('trust_buy_5d') or 0

    if trust >= 8 and foreign >= 4:
        parts.append(f'法人同步買超（投信連{trust_days}天），可順勢偏多，關注投信何時停止加碼作為減碼訊號')
    elif trust >= 8 and foreign <= 0:
        parts.append(f'投信連買{trust_days}天但外資賣超 {abs(foreign_5d):,} 張，留意土洋對作風險，若外資轉買可加碼')
    elif trust <= 0 and foreign >= 4:
        parts.append('外資買超但投信未跟進，可能為外資短期操作，建議等投信同步轉買再進場')
    elif trust <= 0 and foreign <= 0:
        parts.append('法人雙空，不宜追多，等待法人轉向訊號')

    # 轉折偵測
    turning = inst.breakdown.get('trust_turning', '')
    if turning:
        parts.append(f'⚠ 投信出現轉折跡象，建議減碼觀察')

    # --- 分點主力建議 ---
    intent = broker.breakdown.get('intent_label', '')
    exit_note = broker.breakdown.get('exit_note', '')
    long_score = broker.breakdown.get('long_term', 0)

    if '🔴' in intent:
        parts.append(f'主力出脫訊號明確，不宜加碼，已持有者考慮分批出場')
    elif '🟡' in intent and '疑似' in intent:
        parts.append('部分主力出脫跡象，建議觀察 5 日後主力動向是否回穩再決定')
    elif '🟢' in intent:
        if long_score >= 6:
            parts.append('主力持續布局且 60 日量能偏多，可作為買進參考，回檔可分批承接')
        else:
            parts.append('主力仍在場但整體賣壓較大，宜小量試單，不重倉')
    elif '🔵' in intent:
        parts.append('新主力進場但尚未確認意圖，建議觀察 10~20 日買超持續性再跟進')
    elif '⚫' in intent:
        parts.append('主力撤場觀望，流動性風險升高，建議迴避')

    # --- 股東結構建議 ---
    whale = own.breakdown.get('whale', 0)
    holders = own.breakdown.get('holders', 0)
    whale_warning = own.breakdown.get('whale_warning', '')

    if whale >= 8 and holders >= 6:
        parts.append('籌碼持續集中（大戶增持＋股東減少），中線偏多訊號')
    elif whale <= 0 and holders <= 0:
        parts.append('籌碼分散中（大戶減持＋股東增加），不宜追高')
    if whale_warning:
        parts.append('大戶短期急增，留意是否為特定事件拉抬')

    # --- 情緒面建議 ---
    margin = sent.breakdown.get('margin', 0)
    squeeze = sent.breakdown.get('squeeze', 0)
    margin_change = data.get('margin_change') or 0
    short_ratio = data.get('short_ratio') or 0

    if margin >= 8:
        parts.append(f'融資減少 {abs(margin_change):,} 張，浮額消化健康')
    elif margin_change > 500:
        parts.append(f'融資增加 {margin_change:,} 張，散戶追價偏高，注意過熱回檔風險')

    if squeeze >= 6:
        parts.append(f'券資比 {short_ratio:.1f}%，軋空壓力大，若搭配法人買超可能觸發軋空行情')

    # --- 低量偵測 ---
    if low_volume:
        parts.append('⚠ 成交量極低（<100張），流動性不足，進出場滑價風險大')

    # 組裝
    if not parts:
        if total > 60:
            return '多項指標偏多但未出現極端訊號，可小量布局並設停損追蹤'
        else:
            return '多項指標中性偏弱，建議觀望為主，等待明確轉向訊號'

    return '；'.join(parts)


def generate_highlights(inst: DimensionScore, own: DimensionScore,
                        broker: DimensionScore, sent: DimensionScore) -> list[str]:
    items = [
        (inst.breakdown.get('trust', 0), inst.breakdown.get('trust_note', '')),
        (inst.breakdown.get('foreign', 0), inst.breakdown.get('foreign_note', '')),
        (inst.breakdown.get('foreign_align', 0), inst.breakdown.get('align_note', '')),
        (own.breakdown.get('whale', 0), own.breakdown.get('whale_note', '')),
        (own.breakdown.get('holders', 0), own.breakdown.get('holders_note', '')),
        (own.breakdown.get('avg_shares', 0), own.breakdown.get('avg_note', '')),
        (broker.breakdown.get('long_term', 0), broker.breakdown.get('long_note', '')),
        (broker.breakdown.get('exit_detect', 0), broker.breakdown.get('exit_note', '')),
        (sent.breakdown.get('margin', 0), sent.breakdown.get('margin_note', '')),
        (sent.breakdown.get('squeeze', 0), sent.breakdown.get('squeeze_note', '')),
    ]
    # 加入轉折偵測
    turning = inst.breakdown.get('trust_turning', '')
    if turning:
        items.append((5, turning))
    # 加入大戶急漲警示
    whale_warning = own.breakdown.get('whale_warning', '')
    if whale_warning:
        items.append((5, whale_warning))
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
    elif effective_total >= 60:
        result.rating = '偏多操作'
        result.rating_en = 'Bullish'
    else:
        result.rating = '觀望/中性'
        result.rating_en = 'Neutral'

    # 策略建議：依各維度實際結果動態組裝
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
