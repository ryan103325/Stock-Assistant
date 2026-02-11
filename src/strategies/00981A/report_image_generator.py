# -*- coding: utf-8 -*-
"""
00981a 基金日報 - 圖片生成器
使用 Pillow 生成視覺化報告卡片
"""

from PIL import Image, ImageDraw, ImageFont
import os
from datetime import datetime

# ==========================================
# 🎨 設計系統
# ==========================================
COLORS = {
    'bg': '#1a1a2e',           # 深藍紫背景
    'card': '#16213e',         # 深海藍卡片
    'card_light': '#1f3460',   # 較亮卡片
    'accent': '#e94560',       # 珊瑚紅強調
    'positive': '#00d9a0',     # 青綠 (正向)
    'negative': '#ff6b6b',     # 淺紅 (負向)
    'warning': '#ffc107',      # 警告黃
    'text': '#eaeaea',         # 主文字
    'text_dim': '#8892a0',     # 次要文字
    'divider': '#2d3a5a',      # 分隔線
    'gold': '#ffd700',         # 金色
}

def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

WIDTH = 800
PADDING = 35
SECTION_GAP = 25

# ==========================================
# 🔤 字體載入
# ==========================================
def get_font(size, bold=False):
    font_paths = [
        "C:/Windows/Fonts/msjh.ttc",
        "C:/Windows/Fonts/msjhbd.ttc",
        "C:/Windows/Fonts/NotoSansTC-Regular.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]
    if bold:
        font_paths.insert(0, "C:/Windows/Fonts/msjhbd.ttc")
    for path in font_paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except:
                continue
    return ImageFont.load_default()

# ==========================================
# 🎨 繪圖工具
# ==========================================
def draw_rounded_rect(draw, xy, radius, fill):
    draw.rounded_rectangle(xy, radius=radius, fill=fill)

def draw_badge(draw, x, y, text, bg_color, text_color='#ffffff'):
    font = get_font(12, bold=True)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    padding_h = 8
    draw_rounded_rect(draw, (x, y, x + text_width + padding_h * 2, y + 20), 10, hex_to_rgb(bg_color))
    draw.text((x + padding_h, y + 4), text, font=font, fill=hex_to_rgb(text_color))
    return text_width + padding_h * 2 + 8

def draw_section_header(draw, y, title, badge_text=None, badge_color=None):
    font = get_font(24, bold=True)
    draw.text((PADDING, y), title, font=font, fill=hex_to_rgb(COLORS['text']))
    if badge_text and badge_color:
        bbox = draw.textbbox((0, 0), title, font=font)
        draw_badge(draw, PADDING + bbox[2] - bbox[0] + 15, y + 3, badge_text, badge_color)
    return y + 45  # 增加標題後間距

def draw_stat_box(draw, x, y, label, value, color=None):
    box_width, box_height = 170, 60
    draw_rounded_rect(draw, (x, y, x + box_width, y + box_height), 8, hex_to_rgb(COLORS['card_light']))
    font_label = get_font(14)
    draw.text((x + 10, y + 8), label, font=font_label, fill=hex_to_rgb(COLORS['text_dim']))
    font_value = get_font(22, bold=True)
    value_color = hex_to_rgb(color) if color else hex_to_rgb(COLORS['text'])
    draw.text((x + 10, y + 28), value, font=font_value, fill=value_color)
    return box_width

def draw_divider(draw, y):
    draw.line((PADDING, y, WIDTH - PADDING, y), fill=hex_to_rgb(COLORS['divider']), width=1)
    return y + SECTION_GAP

def draw_indicator(draw, x, y, indicator_type):
    size = 16
    if indicator_type == 'up':
        draw.polygon([(x, y + size), (x + size//2, y), (x + size, y + size)], fill=hex_to_rgb(COLORS['positive']))
    elif indicator_type == 'down':
        draw.polygon([(x, y), (x + size//2, y + size), (x + size, y)], fill=hex_to_rgb(COLORS['negative']))
    elif indicator_type == 'fire':
        draw.ellipse((x, y, x + size, y + size), fill=hex_to_rgb(COLORS['accent']))
    elif indicator_type == 'warn':
        draw.polygon([(x + size//2, y), (x, y + size), (x + size, y + size)], fill=hex_to_rgb(COLORS['warning']))
    return size + 5

# ==========================================
# 📊 主要繪製函式
# ==========================================
def generate_fund_report_image(report_data):
    # 動態計算高度 (增加緩衝)
    base_height = 480  # 標題 + 資金水位
    changes = report_data.get('changes', {})
    if changes.get('increases') or changes.get('decreases'):
        base_height += 280
    if report_data.get('streak_alerts'):
        base_height += 100 + len(report_data['streak_alerts']) * 38
    concept = report_data.get('concept', {})
    if concept.get('increases') or concept.get('decreases'):
        base_height += 260
    if report_data.get('anomalies'):
        base_height += 90 + len(report_data['anomalies']) * 35
    height = base_height + 50

    img = Image.new('RGB', (WIDTH, height), hex_to_rgb(COLORS['bg']))
    draw = ImageDraw.Draw(img)
    y = PADDING

    # 標題區
    draw.rectangle((0, 0, WIDTH, 90), fill=hex_to_rgb(COLORS['card']))
    font_title = get_font(32, bold=True)
    draw.text((PADDING, y), "00981A 經理人日報", font=font_title, fill=hex_to_rgb(COLORS['text']))
    y += 45
    date_str = report_data.get('date', datetime.now().strftime('%Y-%m-%d'))
    draw.text((PADDING, y), date_str, font=get_font(18), fill=hex_to_rgb(COLORS['text_dim']))
    y += 50

    # 資金水位區
    wl = report_data.get('water_level', {})
    y = draw_section_header(draw, y, "資金水位")
    
    alert_text = wl.get('final_alert', '資金流向正常')
    for emoji in ['🚀', '💀', '⚠️', '➡️']:
        alert_text = alert_text.replace(emoji, '')
    alert_text = alert_text.strip()
    
    if '資金派對' in alert_text or '買進' in wl.get('final_alert', ''):
        alert_color, badge, badge_color = COLORS['positive'], "BULLISH", COLORS['positive']
    elif '危機' in alert_text:
        alert_color, badge, badge_color = COLORS['negative'], "CRISIS", COLORS['negative']
    elif '警' in alert_text or '壓力' in alert_text:
        alert_color, badge, badge_color = COLORS['warning'], "WARNING", COLORS['warning']
    else:
        alert_color, badge, badge_color = COLORS['text'], "NEUTRAL", COLORS['text_dim']
    
    badge_w = draw_badge(draw, PADDING, y, badge, badge_color)
    draw.text((PADDING + badge_w + 5, y), alert_text, font=get_font(20, bold=True), fill=hex_to_rgb(alert_color))
    y += 35
    
    op_text = wl.get('operation', '')
    for emoji in ['🔴', '🟢', '🔵', '⚪', '🎮', '🟠', '⚫', '🟡', '🟤', '🟣']:
        op_text = op_text.replace(emoji, '')
    if op_text.strip():
        draw.text((PADDING, y), op_text.strip(), font=get_font(17), fill=hex_to_rgb(COLORS['text_dim']))
        y += 30
    y += 10

    # 統計數值框
    box_y = y
    x = PADDING
    gap = 12
    stock_pct = wl.get('stock_pct', 0)
    w = draw_stat_box(draw, x, box_y, "股票", f"{stock_pct:.1f}%", COLORS['positive'] if stock_pct > 90 else None)
    x += w + gap
    cash_pct = wl.get('cash_pct', 0)
    w = draw_stat_box(draw, x, box_y, "現金", f"{cash_pct:.1f}%", COLORS['warning'] if cash_pct > 6 else None)
    x += w + gap
    w = draw_stat_box(draw, x, box_y, "應收付", f"{wl.get('receivable_pct', 0):+.1f}%")
    x += w + gap
    subs_pct = wl.get('subs_pct', 0)
    draw_stat_box(draw, x, box_y, "申贖", f"{subs_pct:+.1f}%", COLORS['negative'] if subs_pct < -1 else None)
    y = box_y + 75

    # 總曝險進度條
    exp = wl.get('total_exposure', 0)
    bar_width = WIDTH - PADDING * 2
    draw_rounded_rect(draw, (PADDING, y, PADDING + bar_width, y + 20), 5, hex_to_rgb(COLORS['card_light']))
    exp_width = int((exp / 100) * bar_width) if exp <= 100 else bar_width
    exp_color = COLORS['positive'] if exp > 95 else (COLORS['warning'] if exp < 85 else COLORS['accent'])
    draw_rounded_rect(draw, (PADDING, y, PADDING + exp_width, y + 20), 5, hex_to_rgb(exp_color))
    draw.text((PADDING + 10, y + 2), f"總曝險: {exp:.1f}%", font=get_font(14, bold=True), fill=hex_to_rgb('#ffffff'))
    y += 35
    y = draw_divider(draw, y)

    # 變動排行區
    increases = changes.get('increases', [])
    decreases = changes.get('decreases', [])
    if increases or decreases:
        y = draw_section_header(draw, y, "變動排行")
        font_item = get_font(16)
        if increases:
            draw.text((PADDING, y), "▲ 增持 TOP 5", font=get_font(14, bold=True), fill=hex_to_rgb(COLORS['positive']))
            y += 26
            for name, code, diff, weight in increases[:5]:
                draw_indicator(draw, PADDING + 5, y + 2, 'up')
                draw.text((PADDING + 25, y), f"{name} ({code}): +{int(diff/1000):,}張 | {weight:.1f}%", font=font_item, fill=hex_to_rgb(COLORS['text']))
                y += 32  # 增加行距
            y += 10
        if decreases:
            draw.text((PADDING, y), "▼ 減持 TOP 3", font=get_font(14, bold=True), fill=hex_to_rgb(COLORS['negative']))
            y += 26
            for name, code, diff, weight in decreases[:3]:
                draw_indicator(draw, PADDING + 5, y + 2, 'down')
                draw.text((PADDING + 25, y), f"{name} ({code}): {int(diff/1000):,}張 | {weight:.1f}%", font=font_item, fill=hex_to_rgb(COLORS['text']))
                y += 32  # 增加行距
        y += 10
        y = draw_divider(draw, y)

    # 連續加碼警示
    streaks = report_data.get('streak_alerts', [])
    if streaks:
        y = draw_section_header(draw, y, "連續加碼警示", "HOT", COLORS['accent'])
        font_item = get_font(16)
        for item in streaks:
            draw_indicator(draw, PADDING + 5, y + 2, 'fire')
            draw.text((PADDING + 25, y), f"{item['name']} ({item['code']}) | +{int(item['diff']/1000):,}張 (連買 {item['streak']} 天)", font=font_item, fill=hex_to_rgb(COLORS['accent']))
            y += 35  # 增加行距
        y += 10
        y = draw_divider(draw, y)

    # 概念股配置
    concept_inc = concept.get('increases', [])
    concept_dec = concept.get('decreases', [])
    if concept_inc or concept_dec:
        y = draw_section_header(draw, y, "概念股配置")
        font_item = get_font(16)
        if concept_inc:
            draw.text((PADDING, y), "▲ 增持 TOP 3", font=get_font(14, bold=True), fill=hex_to_rgb(COLORS['positive']))
            y += 26
            for name, weight, change in concept_inc[:3]:
                draw_indicator(draw, PADDING + 5, y + 2, 'up')
                draw.text((PADDING + 25, y), f"{name}: {weight:.1f}% ({'↑' if change > 0.1 else '→'} {abs(change):.1f}%)", font=font_item, fill=hex_to_rgb(COLORS['text']))
                y += 32  # 增加行距
            y += 10
        if concept_dec:
            draw.text((PADDING, y), "▼ 減持 TOP 3", font=get_font(14, bold=True), fill=hex_to_rgb(COLORS['negative']))
            y += 26
            for name, weight, change in concept_dec[:3]:
                draw_indicator(draw, PADDING + 5, y + 2, 'down')
                draw.text((PADDING + 25, y), f"{name}: {weight:.1f}% ({'↓' if change < -0.1 else '→'} {abs(change):.1f}%)", font=font_item, fill=hex_to_rgb(COLORS['text']))
                y += 32  # 增加行距
        y += 10
        y = draw_divider(draw, y)

    # 異常警示
    anomalies = report_data.get('anomalies', [])
    if anomalies:
        y = draw_section_header(draw, y, "異常警示", "ALERT", COLORS['warning'])
        font_item = get_font(15)
        for alert in anomalies:
            for emoji in ['🔥', '❄️', '🛡️', '⚠️']:
                alert = alert.replace(emoji, '')
            draw_indicator(draw, PADDING + 5, y + 2, 'warn')
            draw.text((PADDING + 25, y), alert.strip(), font=font_item, fill=hex_to_rgb(COLORS['warning']))
            y += 28

    # 儲存
    output_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(output_dir, f"report_{date_str}.png")
    img.save(output_path, "PNG", quality=95)
    print(f"✅ 圖片報告已生成: {output_path}")
    return output_path

if __name__ == "__main__":
    test_data = {
        'date': '2026-01-26',
        'water_level': {
            'final_alert': '🚀 資金派對 (散戶湧入 + 經理人加碼)',
            'operation': '🔴 強力買進 (高持股續買)',
            'stock_pct': 97.94, 'cash_pct': 4.96,
            'receivable_pct': -2.51, 'subs_pct': -1.73,
            'futures_pct': 0.0, 'total_exposure': 97.94
        },
        'changes': {
            'increases': [('台積電', '2330', 500000, 25.3), ('鴻海', '2317', 300000, 8.5), ('聯電', '2303', 200000, 3.2)],
            'decreases': [('聯發科', '2454', -200000, 8.1), ('緯創', '3231', -150000, 2.1)]
        },
        'streak_alerts': [
            {'name': '鴻海', 'code': '2317', 'streak': 4, 'diff': 300000},
            {'name': '台達電', 'code': '2308', 'streak': 3, 'diff': 150000}
        ],
        'concept': {
            'increases': [('AI伺服器', 35.2, 1.5), ('半導體', 28.1, 0.8)],
            'decreases': [('被動元件', 2.1, -0.8), ('面板', 1.5, -0.3)]
        },
        'anomalies': ['🔥 題材熱度異常: 半導體族群單日暴增 1.2%']
    }
    generate_fund_report_image(test_data)
