# -*- coding: utf-8 -*-
"""
00981a 基金策略 - HTML 圖片報表生成器
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
    # Fallback for local testing if path issue
    sys.path.append(os.path.join(PROJECT_ROOT, "src", "utils"))
    from html_renderer import HTMLRenderer, COMMON_STYLE

def generate_fund_report_image(report_data):
    """
    生成 00981a 基金報表圖片
    
    Args:
        report_data (dict): 報表資料字典
        
    Returns:
        str: 圖片路徑
    """
    renderer = HTMLRenderer()
    
    # 準備輸出路徑
    output_dir = os.path.dirname(os.path.abspath(__file__))
    date_clean = report_data.get('date', datetime.now().strftime('%Y-%m-%d')).replace('-', '')
    output_path = os.path.join(output_dir, f"report_00981a_{date_clean}.png")
    
    # 生成 HTML
    html = _build_html(report_data)
    
    # 渲染
    if renderer.render(html, output_path):
        return output_path
    else:
        return None

def _build_html(data):
    """建構 HTML 內容"""
    wl = data.get('water_level', {})
    changes = data.get('changes', {})
    
    # 判斷信號顏色
    alert = wl.get('final_alert', '')
    if '派對' in alert or '買進' in alert:
        badge_color = '#00d9a0'
        badge_text_color = '#000'
    elif '危機' in alert:
        badge_color = '#ff6b6b'
        badge_text_color = '#fff'
    elif '警' in alert or '壓力' in alert:
        badge_color = '#ffc107'
        badge_text_color = '#000'
    else:
        badge_color = '#8892a0'
        badge_text_color = '#fff'

    # 五個部位數據
    stock_pct = wl.get('stock_pct', 0)
    cash_pct = wl.get('cash_pct', 0)
    receivable_pct = wl.get('receivable_pct', 0)
    subs_pct = wl.get('subs_pct', 0)
    futures_pct = wl.get('futures_pct', 0)
    total_exp = wl.get('total_exposure', 0)

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        {COMMON_STYLE}
        <style>
            /* 五格橫排部位 - 加大間距 */
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
            
            /* 新進榜 - 卡片式設計 */
            .new-entry-grid {{
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
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
            .new-entry-shares {{
                color: #fff;
                font-size: 14px;
                margin-top: 4px;
            }}
            
            /* 持股變動 - 寬鬆設計 */
            .change-grid {{
                display: flex;
                flex-wrap: wrap;
                gap: 12px;
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
            
            /* 連續加碼 */
            .streak-item {{
                background: #2a1a1a;
                padding: 12px 14px;
                border-radius: 10px;
                border-left: 4px solid #e94560;
                margin-bottom: 10px;
            }}
            
            /* 異常警示 - 改進版 */
            .alert-box {{
                background: rgba(255, 107, 107, 0.1);
                border: 1px solid #ff6b6b;
                padding: 12px 14px;
                border-radius: 10px;
                margin-top: 12px;
            }}
            .alert-title {{
                color: #ff6b6b;
                font-weight: bold;
                font-size: 14px;
                margin-bottom: 6px;
            }}
            .alert-detail {{
                color: #ccc;
                font-size: 13px;
                line-height: 1.5;
            }}
        </style>
    </head>
    <body>
        <div class="card" style="border-top: 5px solid {badge_color};">
            <div class="header">
                <div>
                    <div class="title">00981A 經理人日報</div>
                    <div class="subtitle">{data.get('date')}</div>
                </div>
                <div style="background:{badge_color}; color:{badge_text_color}; padding: 8px 15px; border-radius: 8px; font-weight:bold; font-size:18px;">
                    {alert}
                </div>
            </div>
            
            {f'<div style="text-align:center; color:#ccc; margin-bottom:15px;">{wl.get("operation", "")}</div>' if wl.get("operation") else ''}
            
            <!-- 五格橫排部位 -->
            <div class="position-row">
                <div class="position-item">
                    <div class="position-label">📈 股票</div>
                    <div class="position-val highlight">{stock_pct:.1f}%</div>
                </div>
                <div class="position-item">
                    <div class="position-label">💵 現金</div>
                    <div class="position-val" style="color:{'#ffc107' if cash_pct < 5 else '#eaeaea'}">{cash_pct:.1f}%</div>
                </div>
                <div class="position-item">
                    <div class="position-label">⚖️ 應收付</div>
                    <div class="position-val">{receivable_pct:.1f}%</div>
                </div>
                <div class="position-item">
                    <div class="position-label">💳 申贖款</div>
                    <div class="position-val" style="color:{'#ff6b6b' if subs_pct > 0 else '#00d9a0'}">{subs_pct:+.1f}%</div>
                </div>
                <div class="position-item">
                    <div class="position-label">🎲 期貨</div>
                    <div class="position-val">{futures_pct:.1f}%</div>
                </div>
            </div>
            
            <div style="margin-bottom:20px;">
                <div class="position-label">總曝險水位</div>
                <div class="progress-container">
                    <div class="progress-bar" style="width: {min(total_exp, 100)}%;">
                        {total_exp:.1f}%
                    </div>
                </div>
            </div>
    """
    
    # 新進榜 - 卡片式設計，紅色
    new_entries = data.get('new_entries', [])
    if new_entries:
        html += '<div class="section-title">🆕 新進榜</div><div class="new-entry-grid">'
        for item in new_entries:
            html += f"""
            <div class="new-entry-card">
                <div class="new-entry-name">{item['name']}</div>
                <div class="new-entry-code">{item['code']}</div>
                <div class="new-entry-shares">{int(item['shares']/1000):,} 張</div>
            </div>
            """
        html += '</div>'
    
    # 持股變動排行 - 寬鬆卡片式
    increases = changes.get('increases', [])
    decreases = changes.get('decreases', [])
    
    if increases or decreases:
        html += '<div class="section-title">📊 持股變動排行</div>'
        
        if increases:
            html += '<div style="color:#ff6b6b; font-size:14px; margin-bottom:8px;">▲ 加碼 TOP 5</div><div class="change-grid">'
            for item in increases[:5]:
                # 支援新舊格式
                if isinstance(item, dict):
                    name, code = item.get('name', ''), item.get('code', '')
                    diff, wt = item.get('diff', 0), item.get('weight', 0)
                    wt_change = item.get('weight_change', 0)
                    amount = item.get('amount', diff * 10)  # 估算金額
                else:
                    name, code, diff, wt = item[0], item[1], item[2], item[3]
                    wt_change = 0
                    amount = diff * 10
                
                wt_change_str = f" ({wt_change:+.2f}%)" if wt_change else ""
                html += f"""
                <div class="change-card change-card-up">
                    <div><span class="change-name">{name}</span><span class="change-code">{code}</span></div>
                    <div class="change-detail">
                        <span class="change-amount" style="color:#ff6b6b;">+{int(diff/1000):,} 張</span>
                        <span style="color:#888; margin-left:6px;">≈ {int(amount/10000):,} 萬</span>
                    </div>
                    <div class="change-weight">權重 {wt:.2f}%{wt_change_str}</div>
                </div>
                """
            html += '</div>'
        
        if decreases:
            html += '<div style="color:#00d9a0; font-size:14px; margin: 15px 0 8px 0;">▼ 減碼 TOP 3</div><div class="change-grid">'
            for item in decreases[:3]:
                if isinstance(item, dict):
                    name, code = item.get('name', ''), item.get('code', '')
                    diff, wt = item.get('diff', 0), item.get('weight', 0)
                    wt_change = item.get('weight_change', 0)
                    amount = item.get('amount', abs(diff) * 10)
                else:
                    name, code, diff, wt = item[0], item[1], item[2], item[3]
                    wt_change = 0
                    amount = abs(diff) * 10
                
                wt_change_str = f" ({wt_change:+.2f}%)" if wt_change else ""
                html += f"""
                <div class="change-card change-card-down">
                    <div><span class="change-name">{name}</span><span class="change-code">{code}</span></div>
                    <div class="change-detail">
                        <span class="change-amount" style="color:#00d9a0;">{int(diff/1000):,} 張</span>
                        <span style="color:#888; margin-left:6px;">≈ {int(amount/10000):,} 萬</span>
                    </div>
                    <div class="change-weight">權重 {wt:.2f}%{wt_change_str}</div>
                </div>
                """
            html += '</div>'

    # 連續加碼警示
    streaks = data.get('streak_alerts', [])
    if streaks:
        html += '<div class="section-title">🔥 連續加碼警示</div>'
        for item in streaks:
            html += f"""
            <div class="streak-item">
                <span style="color:#e94560; font-weight:bold; font-size:15px;">{item['name']}</span> 
                <span style="color:#aaa;">({item['code']})</span>
                <span style="float:right; color:#ffd700; font-weight:bold;">連買 {item['streak']} 天</span>
                <div style="color:#ccc; font-size:13px; margin-top:4px;">本日買超: +{int(item['diff']/1000):,} 張</div>
            </div>
            """

    # 異常警示 - 單一 emoji，換行顯示
    anomalies = data.get('anomalies', [])
    if anomalies:
        for alert_txt in anomalies:
            # 解析警示內容
            lines = alert_txt.split('\n')
            title = lines[0].replace('⚠️', '').replace('🔥', '').replace('❄️', '').replace('🛡️', '').strip()
            details = '<br>'.join(lines[1:]) if len(lines) > 1 else ''
            
            html += f"""
            <div class="alert-box">
                <div class="alert-title">⚠️ {title}</div>
                <div class="alert-detail">{details}</div>
            </div>
            """

    html += """
        </div>
    </body>
    </html>
    """
    return html
