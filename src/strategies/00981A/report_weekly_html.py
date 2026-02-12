# -*- coding: utf-8 -*-
"""
00981a 基金策略 - 週報 HTML 圖片報表生成器
排版風格與日報一致（使用 COMMON_STYLE 基底 + 卡片式橫排）
"""

import os
import sys
from datetime import datetime

# 加入專案根目錄以匯入 utils
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(CURRENT_DIR)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

try:
    from src.utils.html_renderer import HTMLRenderer, COMMON_STYLE
except ImportError:
    sys.path.append(os.path.join(PROJECT_ROOT, "src", "utils"))
    from html_renderer import HTMLRenderer, COMMON_STYLE

def generate_weekly_report_image(report_data):
    """
    生成 00981a 週報圖片
    
    Args:
        report_data (dict): 週報資料字典
        
    Returns:
        str: 圖片路徑，失敗回傳 None
    """
    renderer = HTMLRenderer()
    
    output_dir = os.path.dirname(os.path.abspath(__file__))
    date_range = report_data.get('date_range', {})
    end_date = date_range.get('end', datetime.now().strftime('%Y-%m-%d'))
    date_clean = end_date.replace('-', '')
    output_path = os.path.join(output_dir, f"report_00981a_weekly_{date_clean}.png")
    
    html = _build_html(report_data)
    
    if renderer.render(html, output_path):
        return output_path
    else:
        return None


def _build_html(data):
    """建構週報 HTML 內容（與日報風格一致）"""
    date_range = data.get('date_range', {})
    signal = data.get('signal', {})
    
    # 信號顏色判斷
    strategy = signal.get('strategy', '')
    alert_text = f"{signal.get('emoji', '')} {strategy.split('(')[0].strip() if '(' in strategy else strategy}"
    
    # 預設中立
    badge_color = '#8892a0'
    badge_text_color = '#fff'
    
    if '撤退' in strategy or 'Defensive' in strategy or '出貨' in strategy or 'Distribution' in strategy:
        badge_color = '#00d9a0'
        badge_text_color = '#000'
    elif '派對' in strategy or '建倉' in strategy or 'Accumulation' in strategy or '抄底' in strategy or 'Bottom' in strategy:
        badge_color = '#ff6b6b'
        badge_text_color = '#fff'

    exp_diff = data.get('exp_diff', 0)
    avg_sp = data.get('avg_sp', 0)
    has_inflow = data.get('has_inflow', False)
    total_exposure = data.get('total_exposure', 0) 

    # 數據顏色
    exp_color = '#ff6b6b' if exp_diff > 0 else '#00d9a0' if exp_diff < 0 else '#eaeaea'
    sp_color = '#ff6b6b' if avg_sp < 0 else '#00d9a0' if avg_sp > 0 else '#eaeaea'

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        {COMMON_STYLE}
        <style>
            /* 五格橫排部位 (與日報一致) */
            .position-row {{
                display: flex;
                justify-content: space-between;
                gap: 15px;
                margin-bottom: 20px;
            }}
            .position-item {{
                flex: 1;
                background: rgba(255,255,255,0.05);
                padding: 14px 10px;
                border-radius: 10px;
                text-align: center;
                border: 1px solid rgba(255,255,255,0.08);
            }}
            .position-label {{ font-size: 13px; color: #aaa; margin-bottom: 6px; }}
            .position-val {{ font-size: 18px; font-weight: bold; }}
            
            .progress-container {{
                background: #2d3a5a;
                border-radius: 8px;
                height: 20px;
                margin-top: 5px;
                overflow: hidden;
            }}
            .progress-bar {{
                height: 100%;
                background: linear-gradient(90deg, #4ecca3, #00d9a0);
                text-align: right;
                padding-right: 8px;
                line-height: 20px;
                font-size: 12px;
                color: #000;
                font-weight: bold;
            }}
            
            .section-title {{
                font-size: 16px;
                font-weight: bold;
                color: #ffd700;
                margin: 20px 0 12px 0;
                border-left: 4px solid #ffd700;
                padding-left: 10px;
            }}
            
            /* 策略說明 */
            .strategy-desc {{
                text-align: left;
                color: #dedede;
                font-size: 14px;
                line-height: 1.5;
                margin-bottom: 15px;
                padding: 12px 16px;
                background: rgba(255,255,255,0.05);
                border-left: 4px solid {badge_color};
                border-radius: 4px;
            }}
            
            /* 新進榜 - 卡片式設計 (與日報一致) */
            .new-entry-grid {{
                display: flex;
                flex-wrap: wrap;
                gap: 18px;
            }}
            .new-entry-card {{
                background: rgba(255, 107, 107, 0.1);
                border: 1px solid rgba(255, 107, 107, 0.3);
                padding: 10px 14px;
                border-radius: 10px;
                min-width: 140px;
            }}
            .new-entry-name {{
                color: #ff6b6b;
                font-weight: bold;
                font-size: 15px;
            }}
            .new-entry-code {{
                color: #888;
                font-size: 12px;
            }}
            .new-entry-weight {{
                color: #fff;
                font-size: 14px;
                margin-top: 4px;
            }}
            
            /* 持股變動 - 寬鬆卡片式 (與日報一致) */
            .change-grid {{
                display: flex;
                flex-wrap: wrap;
                gap: 20px;
            }}
            .change-card {{
                background: rgba(255,255,255,0.03);
                padding: 12px 16px;
                border-radius: 10px;
                min-width: 160px;
                flex: 1;
                max-width: 200px;
            }}
            .change-card-up {{
                border-left: 4px solid #ff6b6b;
            }}
            .change-card-down {{
                border-left: 4px solid #00d9a0;
            }}
            .change-name {{
                color: #fff;
                font-weight: bold;
                font-size: 14px;
            }}
            .change-code {{
                color: #888;
                font-size: 12px;
                margin-left: 4px;
            }}
            .change-detail {{
                margin-top: 6px;
                font-size: 13px;
                color: #ccc;
            }}
            .change-amount {{
                font-weight: bold;
            }}
            .change-weight {{
                font-size: 12px;
                color: #888;
                margin-top: 2px;
            }}
            
            /* 概念股配置 */
            .concept-grid {{
                display: flex;
                flex-wrap: wrap;
                gap: 15px;
            }}
            .concept-card {{
                background: rgba(255,255,255,0.03);
                padding: 12px 16px;
                border-radius: 10px;
                min-width: 160px;
                flex: 1;
                max-width: 220px;
            }}
            .concept-card-up {{
                border-left: 4px solid #ff6b6b;
            }}
            .concept-card-down {{
                border-left: 4px solid #00d9a0;
            }}
            .concept-name {{
                color: #fff;
                font-weight: bold;
                font-size: 14px;
            }}
            .concept-weight {{
                font-size: 13px;
                color: #ccc;
                margin-top: 4px;
            }}
            .concept-stocks {{
                font-size: 12px;
                color: #888;
                margin-top: 4px;
            }}
            
            /* AI 總結 */
            .ai-summary {{
                margin-top: 20px;
                padding: 15px 20px;
                background: rgba(255, 215, 0, 0.05);
                border: 1px dashed rgba(255, 215, 0, 0.4);
                border-radius: 10px;
                color: #eee;
                font-size: 14px;
                line-height: 1.6;
                display: flex;
                align-items: flex-start;
            }}
            .ai-icon {{ font-size: 18px; margin-right: 10px; margin-top: -2px; }}
        </style>
    </head>
    <body>
        <div class="card" style="border-top: 5px solid {badge_color};">
            <div class="header">
                <div>
                    <div class="title">00981A 經理人週報</div>
                    <div class="subtitle">{date_range.get('start', '')} ~ {date_range.get('end', '')}</div>
                </div>
                <div style="background:{badge_color}; color:{badge_text_color}; padding: 8px 15px; border-radius: 8px; font-weight:bold; font-size:18px;">
                    {alert_text}
                </div>
            </div>
            
            <div class="strategy-desc">
                {signal.get('reason', '無詳細說明')}
            </div>
            
            <!-- 三格橫排指標 (與日報 position-row 風格一致) -->
            <div class="position-row">
                <div class="position-item">
                    <div class="position-label">📊 曝險變動</div>
                    <div class="position-val" style="color:{exp_color}">{exp_diff:+.1f}%</div>
                </div>
                <div class="position-item">
                    <div class="position-label">📈 週均 SP</div>
                    <div class="position-val" style="color:{sp_color}">{avg_sp:.2f}</div>
                </div>
                <div class="position-item">
                    <div class="position-label">💰 資金流入</div>
                    <div class="position-val" style="color:{'#00d9a0' if has_inflow else '#666'}">{'✅ 有' if has_inflow else '❌ 無'}</div>
                </div>
            </div>
            
            <div style="margin-bottom:20px;">
                <div class="position-label">總曝險水位</div>
                <div class="progress-container">
                    <div class="progress-bar" style="width: {min(max(total_exposure, 0), 100)}%;">
                        {total_exposure:.1f}%
                    </div>
                </div>
            </div>
    """

    # 新進榜 - 卡片式 (與日報一致)
    new_entries = data.get('new_entries', [])
    if new_entries:
        html += '<div class="section-title">🆕 本週新進榜</div><div class="new-entry-grid">'
        for item in new_entries:
            html += f"""
            <div class="new-entry-card">
                <div class="new-entry-name">{item['name']}</div>
                <div class="new-entry-code">{item['code']}</div>
                <div class="new-entry-weight">權重 {item.get('weight', 0):.2f}%</div>
            </div>
            """
        html += '</div>'

    # 持股變動排行 - 卡片式 (與日報一致，按權重變化排序)
    buys = data.get('buys', [])
    sells = data.get('sells', [])
    
    if buys or sells:
        html += '<div class="section-title">📊 本週持股變動</div>'
        
        if buys:
            html += '<div style="color:#ff6b6b; font-size:14px; margin-bottom:8px;">▲ 買超 TOP 5</div><div class="change-grid">'
            for item in buys[:5]:
                diff = item.get('diff', 0)
                wt = item.get('weight', 0)
                wt_change = item.get('weight_change', 0)
                wt_change_str = f" ({wt_change:+.2f}%)" if wt_change else ""
                html += f"""
                <div class="change-card change-card-up">
                    <div><span class="change-name">{item['name']}</span><span class="change-code">{item['code']}</span></div>
                    <div class="change-detail">
                        <span class="change-amount" style="color:#ff6b6b;">+{int(diff/1000):,} 張</span>
                    </div>
                    <div class="change-weight">權重 {wt:.2f}%{wt_change_str}</div>
                </div>
                """
            html += '</div>'
        
        if sells:
            html += '<div style="color:#00d9a0; font-size:14px; margin: 15px 0 8px 0;">▼ 賣超 TOP 5</div><div class="change-grid">'
            for item in sells[:5]:
                diff = item.get('diff', 0)
                wt = item.get('weight', 0)
                wt_change = item.get('weight_change', 0)
                wt_change_str = f" ({wt_change:+.2f}%)" if wt_change else ""
                html += f"""
                <div class="change-card change-card-down">
                    <div><span class="change-name">{item['name']}</span><span class="change-code">{item['code']}</span></div>
                    <div class="change-detail">
                        <span class="change-amount" style="color:#00d9a0;">{int(diff/1000):,} 張</span>
                    </div>
                    <div class="change-weight">權重 {wt:.2f}%{wt_change_str}</div>
                </div>
                """
            html += '</div>'

    # 概念股配置
    concept = data.get('concept', {})
    concept_inc = concept.get('increases', [])
    concept_dec = concept.get('decreases', [])
    concept_stocks = concept.get('group_stock_changes', {})
    
    if concept_inc or concept_dec:
        html += '<div class="section-title">🎪 概念股配置</div>'
        
        if concept_inc:
            html += '<div style="color:#ff6b6b; font-size:14px; margin-bottom:8px;">▲ 增持 TOP 3</div><div class="concept-grid">'
            for item in concept_inc[:3]:
                g, w, c = item[0], item[1], item[2]
                arrow = "↑" if c > 0.1 else "→"
                stock_txt = ""
                if g in concept_stocks:
                    top_s = [s for s in concept_stocks[g] if s[2] > 0][:2]
                    if top_s:
                        stock_txt = "、".join([f"{s[0]}" for s in top_s])
                html += f"""
                <div class="concept-card concept-card-up">
                    <div class="concept-name">{g}</div>
                    <div class="concept-weight">{w:.1f}% ({arrow} {abs(c):.1f}%)</div>
                    {f'<div class="concept-stocks">主要：{stock_txt}</div>' if stock_txt else ''}
                </div>
                """
            html += '</div>'
        
        if concept_dec:
            html += '<div style="color:#00d9a0; font-size:14px; margin: 15px 0 8px 0;">▼ 減持 TOP 3</div><div class="concept-grid">'
            for item in concept_dec[:3]:
                g, w, c = item[0], item[1], item[2]
                arrow = "↓" if c < -0.1 else "→"
                stock_txt = ""
                if g in concept_stocks:
                    top_s = [s for s in concept_stocks[g] if s[2] < 0][:2]
                    if top_s:
                        stock_txt = "、".join([f"{s[0]}" for s in top_s])
                html += f"""
                <div class="concept-card concept-card-down">
                    <div class="concept-name">{g}</div>
                    <div class="concept-weight">{w:.1f}% ({arrow} {abs(c):.1f}%)</div>
                    {f'<div class="concept-stocks">主要：{stock_txt}</div>' if stock_txt else ''}
                </div>
                """
            html += '</div>'

    # AI 總結
    ai_summary = data.get('ai_summary', '')
    if ai_summary:
        html += f"""
        <div class="ai-summary">
            <span class="ai-icon">💡</span>
            <div><b>AI 總結：</b>{ai_summary}</div>
        </div>
        """

    html += """
        </div>
    </body>
    </html>
    """
    return html

if __name__ == "__main__":
    # 測試資料
    mock_data = {
        'date_range': {'start': '2026-02-03', 'end': '2026-02-07'},
        'signal': {
            'strategy': '攻擊型建倉 (Accumulation)',
            'emoji': '🔴',
            'reason': '本周曝險顯著增加 (+2.5%)，且連續淨買入，顯示經理人看好後市。'
        },
        'exp_diff': 2.5,
        'avg_sp': -0.35,
        'has_inflow': True,
        'total_exposure': 96.1,
        'new_entries': [
            {'name': '漢唐', 'code': '2404', 'weight': 1.25},
            {'name': '聯詠', 'code': '3034', 'weight': 0.83},
            {'name': '智原', 'code': '3035', 'weight': 0.55}
        ],
        'buys': [
            {'name': '世芯-KY', 'code': '3661', 'diff': 33000, 'weight': 2.92, 'weight_change': 0.45},
            {'name': '富世達', 'code': '6805', 'diff': 50000, 'weight': 2.95, 'weight_change': 0.38},
            {'name': '欣興', 'code': '3037', 'diff': 198000, 'weight': 2.53, 'weight_change': 0.32},
            {'name': '南亞', 'code': '1303', 'diff': 903000, 'weight': 0.81, 'weight_change': 0.15}
        ],
        'sells': [
            {'name': '辛耘', 'code': '3583', 'diff': -2000, 'weight': 0.0, 'weight_change': -0.55},
            {'name': '群聯', 'code': '8299', 'diff': -295000, 'weight': 5.83, 'weight_change': -0.42},
            {'name': '台達電', 'code': '2308', 'diff': -132000, 'weight': 5.13, 'weight_change': -0.30}
        ],
        'concept': {
            'increases': [
                ('AI', 35.2, 1.5),
                ('PCB', 12.3, 0.8),
                ('記憶體', 8.5, 0.5),
            ],
            'decreases': [
                ('封測', 5.2, -0.6),
                ('面板', 2.1, -0.3),
            ],
            'group_stock_changes': {
                'AI': [('世芯-KY', '3661', 33000), ('富世達', '6805', 50000)],
                'PCB': [('欣興', '3037', 198000)],
                '封測': [('辛耘', '3583', -2000)],
            }
        },
        'ai_summary': '經理人本周轉趨積極，重點加碼世芯、富世達等高價股，顯示對從 AI 伺服器到消費性電子的全面佈局。'
    }
    
    output = generate_weekly_report_image(mock_data)
    if output:
        print(f"✅ 測試圖片已生成: {output}")
    else:
        print("❌ 測試失敗")
