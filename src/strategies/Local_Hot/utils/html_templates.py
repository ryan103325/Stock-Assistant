# -*- coding: utf-8 -*-
"""
族群資金動能策略 V2.0 - HTML 模板模組

設計風格：深藍主題 + 淺藍卡片（wkhtmltopdf 兼容版本）
- wkhtmltopdf 不支援 rgba()，改用固定色碼
- Emoji 僅用於標題、分隔符
- 台灣股市：紅漲綠跌
"""

# CSS 樣式 - wkhtmltopdf 兼容版本
CSS_STYLES = """
<style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    
    body {
        font-family: 'Microsoft JhengHei', 'Segoe UI', Arial, sans-serif;
        background-color: #0f172a;
        color: #ffffff;
        padding: 25px;
        font-size: 14px;
    }
    
    .container { max-width: 780px; margin: 0 auto; }
    
    /* 標題區 */
    .header {
        text-align: center;
        padding: 20px;
        margin-bottom: 20px;
        background-color: #1e3a5f;
        border: 1px solid #3b5998;
        border-radius: 12px;
    }
    .title {
        font-size: 26px;
        font-weight: bold;
        color: #fbbf24;
        margin-bottom: 6px;
    }
    .date { font-size: 13px; color: #94a3b8; }
    
    /* 族群卡片 */
    .sector-card {
        background-color: #1e3a5f;
        border: 1px solid #3b5998;
        border-radius: 12px;
        padding: 16px 20px;
        margin-bottom: 16px;
    }
    
    .sector-header {
        margin-bottom: 12px;
        padding-bottom: 10px;
        border-bottom: 1px solid #3b5998;
        overflow: hidden;
    }
    
    .sector-left { float: left; }
    .sector-right { float: right; }
    
    .rank-badge {
        display: inline-block;
        width: 32px;
        height: 32px;
        line-height: 32px;
        background-color: #f59e0b;
        border-radius: 50%;
        text-align: center;
        font-weight: bold;
        font-size: 16px;
        color: #fff;
        margin-right: 12px;
        vertical-align: middle;
    }
    .rank-badge.silver { background-color: #6b7280; }
    .rank-badge.bronze { background-color: #92400e; }
    
    .sector-name {
        display: inline-block;
        font-size: 20px;
        font-weight: bold;
        color: #ffffff;
        vertical-align: middle;
    }
    
    .badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: bold;
        margin-left: 6px;
        vertical-align: middle;
    }
    .badge-red { background-color: #dc2626; color: #fff; }
    .badge-orange { background-color: #f59e0b; color: #000; }
    .badge-blue { background-color: #2563eb; color: #fff; }
    .badge-gray { background-color: #4b5563; color: #fff; }
    
    .stars { color: #fbbf24; font-size: 14px; margin-left: 6px; vertical-align: middle; }
    
    /* 分隔線標題 */
    .section-title {
        color: #94a3b8;
        font-size: 12px;
        margin: 12px 0 8px 0;
        padding-left: 5px;
        border-left: 3px solid #3b82f6;
    }
    
    /* 六格統計 */
    .stats-row {
        margin-bottom: 8px;
        overflow: hidden;
    }
    
    .stat-box {
        float: left;
        width: 32%;
        margin-right: 2%;
        background-color: #2d4a6f;
        border: 1px solid #3b5998;
        padding: 10px 8px;
        border-radius: 8px;
        text-align: center;
    }
    .stat-box:last-child { margin-right: 0; }
    
    .stat-label {
        font-size: 11px;
        color: #94a3b8;
        margin-bottom: 4px;
    }
    
    .stat-value {
        font-size: 15px;
        font-weight: bold;
        color: #ffffff;
    }
    
    /* 台灣：紅漲綠跌 */
    .text-red { color: #ef4444; }
    .text-green { color: #22c55e; }
    .text-white { color: #ffffff; }
    
    /* 訊號標籤 */
    .signals { margin: 10px 0; overflow: hidden; }
    
    .signal-tag {
        display: inline-block;
        background-color: #3c1f1f;
        border: 1px solid #ef4444;
        padding: 4px 10px;
        border-radius: 10px;
        font-size: 11px;
        font-weight: bold;
        color: #ef4444;
        margin-right: 6px;
        margin-bottom: 4px;
    }
    
    /* 成分股區 */
    .stocks-section {
        border-top: 1px solid #3b5998;
        padding-top: 10px;
        margin-top: 8px;
    }
    
    .stocks-title {
        font-size: 12px;
        color: #94a3b8;
        margin-bottom: 8px;
    }
    
    .stock-row {
        padding: 6px 8px;
        background-color: #2d4a6f;
        border-radius: 6px;
        margin-bottom: 4px;
        overflow: hidden;
    }
    
    .stock-arrow { float: left; width: 20px; font-weight: bold; }
    .stock-code { float: left; width: 55px; font-weight: bold; color: #fbbf24; }
    .stock-name { float: left; width: 80px; color: #e2e8f0; overflow: hidden; }
    .stock-price { float: left; width: 75px; color: #94a3b8; text-align: right; }
    .stock-change { float: left; width: 60px; font-weight: bold; text-align: right; }
    .stock-rank { float: right; color: #fbbf24; font-size: 11px; }
    
    /* 底部 */
    .footer {
        text-align: center;
        padding: 15px;
        margin-top: 15px;
        background-color: #1e3a5f;
        border: 1px solid #3b5998;
        border-radius: 10px;
        color: #94a3b8;
        font-size: 12px;
    }
    .footer-stat { color: #fbbf24; font-weight: bold; }
    
    /* 清除浮動 */
    .clearfix::after { content: ""; display: table; clear: both; }
</style>
"""


def calculate_stars(metrics: dict) -> str:
    """根據族群指標計算星等（0-3 顆星）"""
    stars = 0
    if metrics.get('active_stocks', 0) >= 5:
        stars += 1
    if metrics.get('up_ratio', 0) >= 0.70:
        stars += 1
    if metrics.get('avg_volume_ratio', 0) >= 1.3 and metrics.get('median_change', 0) >= 2.0:
        stars += 1
    return '★' * stars + '☆' * (3 - stars)


def generate_header_html(date_str: str) -> str:
    """生成標題區 HTML"""
    return f"""
    <div class="header">
        <div class="title">📊 統一動能策略</div>
        <div class="date">{date_str}</div>
    </div>
    """


def generate_sector_card_html(sector: dict, rank: int) -> str:
    """生成單一族群卡片 HTML"""
    metrics = sector.get('metrics', {})
    score = sector.get('score', {})
    
    # 排名樣式
    rank_class = ''
    if rank == 2:
        rank_class = 'silver'
    elif rank == 3:
        rank_class = 'bronze'
    
    # 基本資訊
    sector_name = metrics.get('sector_name', '未知族群')
    total_score = score.get('total_score', 0)
    mode = score.get('mode', '觀望')
    top50_count = metrics.get('top50_count', 0)
    
    # 評分顏色
    score_badge = 'badge-gray'
    if total_score >= 60:
        score_badge = 'badge-red'
    elif total_score >= 40:
        score_badge = 'badge-orange'
    
    # 星等
    stars = calculate_stars(metrics)
    
    # 統計數據
    active = metrics.get('active_stocks', 0)
    total = metrics.get('total_stocks', 0)
    up_ratio = metrics.get('up_ratio', 0)
    median_change = metrics.get('median_change', 0)
    volume_ratio = metrics.get('avg_volume_ratio', 0)
    fund_flow = metrics.get('fund_flow', 0)
    margin_change = metrics.get('margin_change', 0)
    
    # 資金流向格式化
    if abs(fund_flow) >= 1000:
        fund_str = f"{fund_flow/1000:+.1f}B"
    elif fund_flow != 0:
        fund_str = f"{fund_flow:+.0f}M"
    else:
        fund_str = "—"
    fund_class = 'text-red' if fund_flow > 0 else 'text-green' if fund_flow < 0 else 'text-white'
    
    # 融資增減格式化
    if abs(margin_change) >= 1000:
        margin_str = f"{margin_change/1000:+.1f}千張"
    elif margin_change != 0:
        margin_str = f"{margin_change:+.0f}張"
    else:
        margin_str = "—"
    margin_class = 'text-red' if margin_change > 0 else 'text-green' if margin_change < 0 else 'text-white'
    
    # 中位數漲幅
    median_str = f"{median_change:+.1f}%"
    median_class = 'text-red' if median_change > 0 else 'text-green' if median_change < 0 else 'text-white'
    
    # 上漲比例
    up_ratio_class = 'text-red' if up_ratio >= 0.5 else 'text-green'
    
    # 訊號標籤
    signals = score.get('signals', [])
    signals_html = ''.join([f'<span class="signal-tag">✓ {sig}</span>' for sig in signals])
    
    # 成分股
    members = metrics.get('member_stocks', [])
    top50_members = [m for m in members if m.get('is_top50', False)][:3]
    other_members = [m for m in members if not m.get('is_top50', False)][:max(0, 3-len(top50_members))]
    display_members = (top50_members + other_members)[:3]
    
    stocks_html = ''
    for m in display_members:
        change = m.get('change', 0)
        close_price = m.get('close', 0)
        amount_rank = m.get('amount_rank', 999)
        stock_code = m.get('code', '')
        stock_name = m.get('name', '')[:4]  # 最多4個字
        
        arrow = '▲' if change > 0 else '▼' if change < 0 else '─'
        arrow_class = 'text-red' if change > 0 else 'text-green'
        change_class = 'text-red' if change > 0 else 'text-green'
        
        stocks_html += f'''
        <div class="stock-row clearfix">
            <span class="stock-arrow {arrow_class}">{arrow}</span>
            <span class="stock-code">{stock_code}</span>
            <span class="stock-name">{stock_name}</span>
            <span class="stock-price">${close_price:.1f}</span>
            <span class="stock-change {change_class}">{change:+.1f}%</span>
            <span class="stock-rank">#{amount_rank}</span>
        </div>
        '''
    
    return f"""
    <div class="sector-card">
        <div class="sector-header clearfix">
            <div class="sector-left">
                <span class="rank-badge {rank_class}">{rank}</span>
                <span class="sector-name">{sector_name}</span>
            </div>
            <div class="sector-right">
                <span class="badge {score_badge}">{total_score:.0f}分</span>
                <span class="badge badge-blue">{mode}</span>
                {f'<span class="badge badge-orange">💰{top50_count}支</span>' if top50_count > 0 else ''}
                <span class="stars">{stars}</span>
            </div>
        </div>
        
        <div class="section-title">📈 市場數據</div>
        
        <div class="stats-row clearfix">
            <div class="stat-box">
                <div class="stat-label">平均量比</div>
                <div class="stat-value">{volume_ratio:.2f}x</div>
            </div>
            <div class="stat-box">
                <div class="stat-label">資金流向</div>
                <div class="stat-value {fund_class}">{fund_str}</div>
            </div>
            <div class="stat-box">
                <div class="stat-label">融資增減</div>
                <div class="stat-value {margin_class}">{margin_str}</div>
            </div>
        </div>
        
        <div class="stats-row clearfix">
            <div class="stat-box">
                <div class="stat-label">進榜股票</div>
                <div class="stat-value">{active}/{total}支</div>
            </div>
            <div class="stat-box">
                <div class="stat-label">上漲比例</div>
                <div class="stat-value {up_ratio_class}">{up_ratio*100:.0f}%</div>
            </div>
            <div class="stat-box">
                <div class="stat-label">中位數漲幅</div>
                <div class="stat-value {median_class}">{median_str}</div>
            </div>
        </div>
        
        {f'<div class="signals">{signals_html}</div>' if signals_html else ''}
        
        <div class="stocks-section">
            <div class="stocks-title">📋 成分股表現 Top 3</div>
            {stocks_html if stocks_html else '<div style="color:#64748b;font-size:12px;">無進榜成分股</div>'}
        </div>
    </div>
    """


def generate_footer_html(total_count: int, mode_counts: dict = None) -> str:
    """生成底部統計區 HTML"""
    mode_str = ''
    if mode_counts:
        mode_parts = [f'{k}: {v}' for k, v in mode_counts.items()]
        mode_str = f' ｜ {" ｜ ".join(mode_parts)}'
    
    return f"""
    <div class="footer">
        共 <span class="footer-stat">{total_count}</span> 個族群通過篩選{mode_str}
    </div>
    """


def generate_html(report_data: dict) -> str:
    """生成完整的 HTML 報表內容"""
    date_str = report_data.get('date', '')
    sectors = report_data.get('sectors', [])[:5]
    summary = report_data.get('summary', {})
    
    header_html = generate_header_html(date_str)
    
    cards_html = ''
    for i, sector in enumerate(sectors):
        cards_html += generate_sector_card_html(sector, i + 1)
    
    if not sectors:
        cards_html = """
        <div class="sector-card" style="text-align: center; padding: 40px;">
            <div style="font-size: 36px; margin-bottom: 15px;">📭</div>
            <div style="font-size: 14px; color: #94a3b8;">今日無符合條件的熱門族群</div>
        </div>
        """
    
    total_count = summary.get('total_passed', len(sectors))
    mode_counts = summary.get('mode_counts', {})
    footer_html = generate_footer_html(total_count, mode_counts)
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        {CSS_STYLES}
    </head>
    <body>
        <div class="container">
            {header_html}
            {cards_html}
            {footer_html}
        </div>
    </body>
    </html>
    """
