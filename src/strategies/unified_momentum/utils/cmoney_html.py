# -*- coding: utf-8 -*-
"""
CMoney 雙圖報表 HTML 模板

圖片一：法人走向（三大法人、外資、投信、自營商）
圖片二：資金融資券（資金流向、融資增減、融券增減、券資比）
"""

# CSS 樣式
CSS_STYLES = """
<style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    
    body {
        font-family: 'Microsoft JhengHei', 'Segoe UI', Arial, sans-serif;
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        color: #ffffff;
        padding: 15px;
        padding-bottom: 30px;
        font-size: 12px;
    }
    
    .container { max-width: 900px; margin: 0 auto; padding-bottom: 20px; }
    
    .header {
        text-align: center;
        padding: 12px;
        margin-bottom: 15px;
        background: linear-gradient(90deg, #1e3a5f 0%, #2d4a6f 100%);
        border-radius: 10px;
        border: 1px solid #3b5998;
    }
    .title {
        font-size: 20px;
        font-weight: bold;
        color: #fbbf24;
        margin-bottom: 3px;
    }
    .date { font-size: 11px; color: #94a3b8; }
    
    .section-title {
        font-size: 14px;
        font-weight: bold;
        padding: 8px 0;
        margin-top: 12px;
        border-bottom: 2px solid #3b5998;
    }
    .section-title.inst { color: #a78bfa; }
    .section-title.fund { color: #22c55e; }
    .section-title.margin { color: #3b82f6; }
    .section-title.short { color: #f97316; }
    .section-title.ratio { color: #ef4444; }
    
    .cards-row {
        display: flex;
        gap: 10px;
        margin-top: 10px;
    }
    
    .vertical-card {
        flex: 1;
        background: #1e3a5f;
        border: 1px solid #3b5998;
        border-radius: 8px;
        overflow: hidden;
        min-width: 0;
    }
    .vertical-card .card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 10px 12px;
        background: linear-gradient(90deg, #243b5a 0%, #1e3a5f 100%);
        border-bottom: 1px solid #3b5998;
    }
    .vertical-card .sector-name {
        font-size: 13px;
        font-weight: bold;
        color: #fbbf24;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        max-width: 150px;
    }
    .vertical-card .sector-score {
        font-size: 12px;
        font-weight: bold;
        padding: 2px 8px;
        border-radius: 12px;
        background: #1a3a2f;
        white-space: nowrap;
    }
    
    .vertical-card .data-section {
        padding: 10px 12px;
        border-bottom: 1px dashed #3b5998;
    }
    .vertical-card .data-line {
        font-size: 11px;
        color: #94a3b8;
        margin: 4px 0;
    }
    .vertical-card .data-line span {
        color: #ffffff;
        font-weight: 500;
    }
    .vertical-card .data-line.positive span { color: #ef4444; }
    .vertical-card .data-line.negative span { color: #22c55e; }
    
    .vertical-card .stock-section {
        padding: 8px 12px;
    }
    .vertical-card .stock-label {
        font-size: 10px;
        color: #64748b;
        margin-bottom: 6px;
    }
    .vertical-card .stock-pills {
        display: flex;
        flex-wrap: wrap;
        gap: 4px;
    }
    .vertical-card .stock-pill {
        display: inline-block;
        background: #0f172a;
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 10px;
    }
    .vertical-card .stock-pill .stock-code {
        color: #64748b;
        margin-right: 3px;
    }
    .vertical-card .stock-pill .stock-name {
        color: #ffffff;
        margin-right: 5px;
    }
    .vertical-card .stock-pill .stock-change {
        font-weight: bold;
    }
    .vertical-card .no-stock {
        font-size: 10px;
        color: #64748b;
        font-style: italic;
    }
    
    .no-data {
        text-align: center;
        color: #64748b;
        padding: 15px;
        font-style: italic;
    }
</style>
"""


def get_score_color(score: float) -> str:
    """分數紅綠燈顏色"""
    if score >= 90:
        return '#dc2626'
    elif score >= 70:
        return '#f97316'
    elif score >= 50:
        return '#fbbf24'
    elif score >= 30:
        return '#4ade80'
    else:
        return '#059669'


def clean_sector_name(name: str) -> str:
    """清理族群名稱"""
    if not name:
        return name
    name = name.replace('概念股_', '')
    name = name.replace('集團股_', '')
    name = name.replace('概念股', '')
    name = name.replace('集團股', '')
    name = name.replace('_', ' ')
    return name.strip()


def generate_stock_pills_html(top3: list) -> str:
    """生成成分股 pill 列表"""
    if not top3:
        return '<div class="no-stock">無 Top100 成分股</div>'
    
    html = '<div class="stock-label">📊 Top100 漲幅前 3：</div>'
    html += '<div class="stock-pills">'
    
    for stock in top3:
        change = stock.get('change', 0)
        color = '#ef4444' if change >= 0 else '#22c55e'
        sign = '+' if change >= 0 else ''
        
        html += f'''
        <span class="stock-pill">
            <span class="stock-code">{stock.get('code', '')}</span>
            <span class="stock-name">{stock.get('name', '')}</span>
            <span class="stock-change" style="color:{color}">{sign}{change:.1f}%</span>
        </span>
        '''
    
    html += '</div>'
    return html


def generate_cards_row_html(items: list, data_renderer) -> str:
    """生成三欄並排卡片"""
    if not items:
        return '<div class="no-data">無資料</div>'
    
    html = '<div class="cards-row">'
    
    for item in items[:3]:
        sector = clean_sector_name(item.get('sector', ''))
        score = item.get('score', {})
        data = item.get('data', {})
        top3 = item.get('top3', [])
        
        final_score = score.get('final_score', 0)
        score_color = get_score_color(final_score)
        
        html += f'''
        <div class="vertical-card">
            <div class="card-header">
                <span class="sector-name" title="{sector}">{sector}</span>
                <span class="sector-score" style="color:{score_color}">{final_score:.0f}分</span>
            </div>
            <div class="data-section">
                {data_renderer(data)}
            </div>
            <div class="stock-section">
                {generate_stock_pills_html(top3)}
            </div>
        </div>
        '''
    
    html += '</div>'
    return html


# === 法人走向報表 ===

def render_inst_data(data: dict) -> str:
    """渲染法人買超數據"""
    amount = data.get('buy_amount', 0)
    amount_in_billion = amount / 100  # 百萬轉億
    
    # 判斷買超或賣超
    amount_class = 'positive' if amount >= 0 else 'negative'
    sign = '+' if amount >= 0 else ''
    
    return f'''
    <div class="data-line {amount_class}">買超金額: <span>{sign}{amount_in_billion:.2f} 億</span></div>
    '''


def generate_institutional_report_html(results: dict, date_str: str) -> str:
    """生成法人走向報表 HTML"""
    inst = results.get('institutional', {})
    
    html = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>法人走向報表</title>
        {CSS_STYLES}
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="title">📊 法人走向報表</div>
                <div class="date">{date_str}</div>
            </div>
            
            <div class="section-title inst">🏛️ 三大法人合計 Top 3</div>
            {generate_cards_row_html(inst.get('inst_total', []), render_inst_data)}
            
            <div class="section-title inst">🌐 外資買超 Top 3</div>
            {generate_cards_row_html(inst.get('foreign', []), render_inst_data)}
            
            <div class="section-title inst">🏢 投信買超 Top 3</div>
            {generate_cards_row_html(inst.get('trust', []), render_inst_data)}
            
            <div class="section-title inst">💼 自營商買超 Top 3</div>
            {generate_cards_row_html(inst.get('dealer', []), render_inst_data)}
        </div>
    </body>
    </html>
    '''
    
    return html


# === 資金融資券報表 ===

def render_fund_flow_data(data: dict) -> str:
    """渲染資金流向數據"""
    fund_flow = data.get('fund_flow', 0)
    price_change = data.get('price_change', 0)
    turnover = data.get('turnover_change', 0)
    
    pct_class = 'positive' if price_change >= 0 else 'negative'
    sign = '+' if price_change >= 0 else ''
    
    return f'''
    <div class="data-line positive">資金流入: <span>{fund_flow:.1f} 億</span></div>
    <div class="data-line {pct_class}">漲跌幅: <span>{sign}{price_change:.2f}%</span></div>
    <div class="data-line">成交增幅: <span>+{turnover:.1f}%</span></div>
    '''


def render_margin_data(data: dict) -> str:
    """渲染融資增減數據"""
    change = data.get('margin_change', 0)
    pct = data.get('change_pct', 0)
    
    return f'''
    <div class="data-line positive">融資增減: <span>+{change:,.0f} 張</span></div>
    <div class="data-line positive">增減比例: <span>+{pct:.2f}%</span></div>
    '''


def render_short_data(data: dict) -> str:
    """渲染融券增減數據"""
    change = data.get('short_change', 0)
    
    return f'''
    <div class="data-line">融券增減: <span>{change:,.0f} 張</span></div>
    '''


def render_ratio_data(data: dict) -> str:
    """渲染券資比數據"""
    ratio = data.get('short_margin_ratio', 0)
    
    return f'''
    <div class="data-line negative">券資比: <span>{ratio:.2f}%</span></div>
    '''


def generate_fund_margin_report_html(results: dict, date_str: str) -> str:
    """生成資金融資券報表 HTML"""
    fm = results.get('fund_margin', {})
    
    html = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>資金融資券報表</title>
        {CSS_STYLES}
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="title">📊 資金融資券報表</div>
                <div class="date">{date_str}</div>
            </div>
            
            <div class="section-title fund">💰 資金流向 Top 3</div>
            {generate_cards_row_html(fm.get('fund_flow', []), render_fund_flow_data)}
            
            <div class="section-title margin">📈 融資增減 Top 3</div>
            {generate_cards_row_html(fm.get('margin', []), render_margin_data)}
            
            <div class="section-title short">📉 融券增減 Top 3</div>
            {generate_cards_row_html(fm.get('short', []), render_short_data)}
            
            <div class="section-title ratio">⚖️ 券資比 Top 3</div>
            {generate_cards_row_html(fm.get('ratio', []), render_ratio_data)}
        </div>
    </body>
    </html>
    '''
    
    return html


if __name__ == "__main__":
    print("=== 測試 cmoney_html ===")
    print("generate_institutional_report_html 和 generate_fund_margin_report_html 已就緒")
