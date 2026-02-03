# -*- coding: utf-8 -*-
"""
CMoney 三維度族群報表 HTML 模板

區塊：
1. 三維度熱門族群（可選）
2. 資金流向 Top 3
3. 融資增減 Top 3
4. 券資比 Top 3
"""

# CSS 樣式
CSS_STYLES = """
<style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    
    body {
        font-family: 'Microsoft JhengHei', 'Segoe UI', Arial, sans-serif;
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        color: #ffffff;
        padding: 20px;
        font-size: 13px;
    }
    
    .container { max-width: 750px; margin: 0 auto; }
    
    /* 標題 */
    .header {
        text-align: center;
        padding: 15px;
        margin-bottom: 20px;
        background: linear-gradient(90deg, #1e3a5f 0%, #2d4a6f 100%);
        border-radius: 10px;
        border: 1px solid #3b5998;
    }
    .title {
        font-size: 22px;
        font-weight: bold;
        color: #fbbf24;
        margin-bottom: 5px;
    }
    .date { font-size: 12px; color: #94a3b8; }
    
    /* 區塊標題 */
    .section-title {
        font-size: 16px;
        font-weight: bold;
        color: #60a5fa;
        padding: 10px 0;
        margin-top: 15px;
        border-bottom: 2px solid #3b5998;
    }
    .section-title.multi { color: #f97316; }
    .section-title.fund { color: #22c55e; }
    .section-title.margin { color: #3b82f6; }
    .section-title.ratio { color: #ef4444; }
    
    /* 族群卡片 */
    .sector-card {
        background: #1e3a5f;
        border: 1px solid #3b5998;
        border-radius: 8px;
        padding: 12px 15px;
        margin: 10px 0;
    }
    .sector-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 8px;
    }
    .sector-name {
        font-size: 15px;
        font-weight: bold;
        color: #fbbf24;
    }
    .sector-score {
        font-size: 14px;
        font-weight: bold;
        color: #22c55e;
        background: #1a3a2f;
        padding: 3px 10px;
        border-radius: 15px;
    }
    
    /* 數據列 */
    .data-row {
        display: flex;
        flex-wrap: wrap;
        gap: 15px;
        margin: 8px 0;
    }
    .data-item {
        font-size: 12px;
        color: #94a3b8;
    }
    .data-item span {
        color: #ffffff;
        font-weight: 500;
    }
    .data-item.positive span { color: #22c55e; }
    .data-item.negative span { color: #ef4444; }
    
    /* 成分股列表 */
    .stock-list {
        margin-top: 8px;
        padding-top: 8px;
        border-top: 1px dashed #3b5998;
    }
    .stock-label {
        font-size: 11px;
        color: #64748b;
        margin-bottom: 5px;
    }
    .stock-item {
        display: inline-block;
        background: #0f172a;
        padding: 3px 8px;
        border-radius: 4px;
        margin: 2px 5px 2px 0;
        font-size: 11px;
    }
    .stock-code { color: #94a3b8; }
    .stock-name { color: #ffffff; }
    .stock-change { color: #22c55e; font-weight: bold; }
    .stock-change.negative { color: #ef4444; }
    
    /* 多維度族群 */
    .multi-dim-card {
        background: linear-gradient(135deg, #1e3a5f 0%, #2d3a4f 100%);
        border: 2px solid #f97316;
    }
    .dim-scores {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        margin: 8px 0;
    }
    .dim-score {
        font-size: 11px;
        padding: 4px 10px;
        border-radius: 4px;
        background: #0f172a;
    }
    .dim-score.fund { border-left: 3px solid #22c55e; }
    .dim-score.margin { border-left: 3px solid #3b82f6; }
    .dim-score.ratio { border-left: 3px solid #ef4444; }
    
    /* 無資料提示 */
    .no-data {
        text-align: center;
        color: #64748b;
        padding: 15px;
        font-style: italic;
    }
</style>
"""


def format_number(value, unit='', decimals=2):
    """格式化數字"""
    if value is None:
        return '—'
    try:
        if abs(value) >= 10000:
            return f"{value/10000:.1f}萬{unit}"
        elif abs(value) >= 1000:
            return f"{value:,.0f}{unit}"
        else:
            return f"{value:.{decimals}f}{unit}"
    except:
        return str(value)


def generate_stock_list_html(top3: list) -> str:
    """生成成分股列表 HTML"""
    if not top3:
        return '<div class="stock-label">無 Top100 成分股</div>'
    
    html = '<div class="stock-list">'
    html += '<div class="stock-label">📊 Top100 漲幅前 3：</div>'
    
    for stock in top3:
        change = stock.get('change', 0)
        change_class = 'negative' if change < 0 else ''
        sign = '+' if change >= 0 else ''
        
        html += f'''
        <span class="stock-item">
            <span class="stock-code">{stock.get('code', '')}</span>
            <span class="stock-name">{stock.get('name', '')}</span>
            <span class="stock-change {change_class}">{sign}{change:.2f}%</span>
        </span>
        '''
    
    html += '</div>'
    return html


def generate_multi_dimension_html(multi_list: list) -> str:
    """生成三維度熱門族群區塊"""
    if not multi_list:
        return ''
    
    html = '<div class="section-title multi">🔥 三維度熱門族群</div>'
    
    for item in multi_list[:3]:  # 最多顯示 3 個
        sector = item.get('sector', '')
        dims = item.get('dimensions', {})
        avg_score = item.get('avg_score', 0)
        top3 = item.get('top3', [])
        
        html += f'''
        <div class="sector-card multi-dim-card">
            <div class="sector-header">
                <span class="sector-name">{sector}</span>
                <span class="sector-score">平均 {avg_score:.0f} 分</span>
            </div>
            <div class="dim-scores">
        '''
        
        # 資金流向
        if dims.get('fund_flow'):
            ff = dims['fund_flow']
            html += f'<span class="dim-score fund">💰 資金: {ff["final_score"]:.0f}分 (#{ff["rank"]})</span>'
        
        # 融資增減
        if dims.get('margin'):
            mg = dims['margin']
            html += f'<span class="dim-score margin">📈 融資: {mg["final_score"]:.0f}分 (#{mg["rank"]})</span>'
        
        # 券資比
        if dims.get('ratio'):
            rt = dims['ratio']
            html += f'<span class="dim-score ratio">📉 券資比: {rt["final_score"]:.0f}分 (#{rt["rank"]})</span>'
        
        html += '</div>'
        html += generate_stock_list_html(top3)
        html += '</div>'
    
    return html


def generate_fund_flow_html(fund_list: list) -> str:
    """生成資金流向區塊"""
    html = '<div class="section-title fund">💰 資金流向 Top 3</div>'
    
    if not fund_list:
        html += '<div class="no-data">無資料</div>'
        return html
    
    for item in fund_list[:3]:
        sector = item.get('sector', '')
        score = item.get('score', {})
        data = item.get('data', {})
        top3 = item.get('top3', [])
        
        fund_flow = data.get('fund_flow', 0)
        price_change = data.get('price_change', 0)
        turnover_change = data.get('turnover_change', 0)
        
        price_class = 'positive' if price_change >= 0 else 'negative'
        price_sign = '+' if price_change >= 0 else ''
        
        html += f'''
        <div class="sector-card">
            <div class="sector-header">
                <span class="sector-name">{sector}</span>
                <span class="sector-score">{score.get("final_score", 0):.0f} 分</span>
            </div>
            <div class="data-row">
                <div class="data-item positive">資金流入: <span>{fund_flow:.1f} 億</span></div>
                <div class="data-item {price_class}">漲跌幅: <span>{price_sign}{price_change:.2f}%</span></div>
                <div class="data-item">成交增幅: <span>+{turnover_change:.1f}%</span></div>
            </div>
            {generate_stock_list_html(top3)}
        </div>
        '''
    
    return html


def generate_margin_html(margin_list: list) -> str:
    """生成融資增減區塊"""
    html = '<div class="section-title margin">📈 融資增減 Top 3</div>'
    
    if not margin_list:
        html += '<div class="no-data">無資料</div>'
        return html
    
    for item in margin_list[:3]:
        sector = item.get('sector', '')
        score = item.get('score', {})
        data = item.get('data', {})
        top3 = item.get('top3', [])
        
        margin_change = data.get('margin_change', 0)
        change_pct = data.get('change_pct', 0)
        
        html += f'''
        <div class="sector-card">
            <div class="sector-header">
                <span class="sector-name">{sector}</span>
                <span class="sector-score">{score.get("final_score", 0):.0f} 分</span>
            </div>
            <div class="data-row">
                <div class="data-item positive">融資增減: <span>+{margin_change:,.0f} 張</span></div>
                <div class="data-item positive">增減比例: <span>+{change_pct:.2f}%</span></div>
            </div>
            {generate_stock_list_html(top3)}
        </div>
        '''
    
    return html


def generate_ratio_html(ratio_list: list) -> str:
    """生成券資比區塊"""
    html = '<div class="section-title ratio">📉 券資比 Top 3</div>'
    
    if not ratio_list:
        html += '<div class="no-data">無資料</div>'
        return html
    
    for item in ratio_list[:3]:
        sector = item.get('sector', '')
        score = item.get('score', {})
        data = item.get('data', {})
        top3 = item.get('top3', [])
        
        ratio = data.get('short_margin_ratio', 0)
        
        html += f'''
        <div class="sector-card">
            <div class="sector-header">
                <span class="sector-name">{sector}</span>
                <span class="sector-score">{score.get("final_score", 0):.0f} 分</span>
            </div>
            <div class="data-row">
                <div class="data-item negative">券資比: <span>{ratio:.2f}%</span></div>
            </div>
            {generate_stock_list_html(top3)}
        </div>
        '''
    
    return html


def generate_cmoney_report_html(results: dict, date_str: str) -> str:
    """
    生成完整的 CMoney 報表 HTML
    
    Args:
        results: process_cmoney_rankings 的輸出
        date_str: 日期字串
        
    Returns:
        str: 完整 HTML
    """
    html = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>CMoney 族群動能報表</title>
        {CSS_STYLES}
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="title">📊 CMoney 族群動能報表</div>
                <div class="date">{date_str}</div>
            </div>
            
            {generate_multi_dimension_html(results.get('multi_dimension', []))}
            {generate_fund_flow_html(results.get('fund_flow', []))}
            {generate_margin_html(results.get('margin', []))}
            {generate_ratio_html(results.get('ratio', []))}
        </div>
    </body>
    </html>
    '''
    
    return html


if __name__ == "__main__":
    # 測試
    print("=== 測試 cmoney_html ===")
    
    test_results = {
        'fund_flow': [
            {
                'sector': '概念股_IC載板',
                'score': {'final_score': 57, 'rank': 2},
                'data': {'fund_flow': 210.3, 'price_change': 8.59, 'turnover_change': 55.01},
                'top3': [
                    {'code': '2330', 'name': '台積電', 'change': 9.1},
                    {'code': '2454', 'name': '聯發科', 'change': 8.5},
                    {'code': '3711', 'name': '日月光', 'change': 8.2}
                ]
            }
        ],
        'margin': [],
        'ratio': [],
        'multi_dimension': []
    }
    
    html = generate_cmoney_report_html(test_results, '2026-01-31')
    print(f"HTML 長度: {len(html)}")
