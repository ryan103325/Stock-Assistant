"""
HTML 報告生成模組
將分析結果渲染為 HTML
"""
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from fundamental_master.utils.logger import setup_logger

logger = setup_logger('html_generator')

TEMPLATE_DIR = Path(__file__).parent / 'templates'


def generate_html_report(analysis_data: dict) -> str:
    """
    生成 HTML 報告

    Args:
        analysis_data: 完整的分析數據

    Returns:
        str: 渲染後的 HTML 內容
    """
    logger.info("📄 生成 HTML 報告...")

    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    template = env.get_template('report_template.html')

    # 準備模板數據
    stock_info = analysis_data.get('stock_info', {})
    scores = analysis_data.get('scores', {})
    ratios = analysis_data.get('ratios', {})
    ai_result = analysis_data.get('ai_analysis', {})

    # M-Score
    m_data = scores.get('m_score', {})
    m_judgment = m_data.get('judgment', 'N/A')
    m_status = 'status-pass' if m_judgment == 'PASS' else 'status-fail'

    # Z-Score
    z_data = scores.get('z_score', {})
    z_zone = z_data.get('zone', 'N/A')
    z_status_map = {'Safe': 'status-safe', 'Grey': 'status-grey', 'Distress': 'status-distress'}
    z_status = z_status_map.get(z_zone, 'status-neutral')

    # F-Score
    f_data = scores.get('f_score', {})
    f_score_val = f_data.get('score', 0)
    f_status = 'status-safe' if f_score_val >= 8 else ('status-fail' if f_score_val <= 3 else 'status-grey')

    # Magic Formula
    mf_data = scores.get('magic_formula', {})

    # Lynch
    lynch_data = scores.get('lynch', {})

    template_data = {
        # 基本資訊
        'stock_id': stock_info.get('股票代號', ''),
        'stock_name': stock_info.get('股票名稱', ''),
        'industry': stock_info.get('產業分類', 'N/A'),
        'price': _fmt_num(stock_info.get('收盤價')),
        'market_cap': _fmt_num(stock_info.get('市值_億')),
        'pe_ratio': _fmt_num(stock_info.get('本益比')),
        'dividend_yield': _fmt_num(stock_info.get('殖利率')),
        'roe': _fmt_num(ratios.get('ROE')),
        'revenue_growth': _fmt_num(ratios.get('營收成長率')),

        # 綜合評分
        'overall_score': ai_result.get('overall_score', 'N/A'),

        # M-Score
        'm_score_value': _fmt_num(m_data.get('score'), decimals=2),
        'm_score_judgment': m_judgment,
        'm_score_status_class': m_status,
        'm_score_analysis': ai_result.get('m_score_analysis', m_data.get('description', '')),

        # Z-Score
        'z_score_value': _fmt_num(z_data.get('score'), decimals=2),
        'z_score_judgment': z_data.get('judgment', 'N/A'),
        'z_score_status_class': z_status,
        'z_score_analysis': ai_result.get('z_score_analysis', z_data.get('description', '')),

        # F-Score
        'f_score_value': f_score_val,
        'f_score_judgment': f_data.get('judgment', 'N/A'),
        'f_score_status_class': f_status,
        'f_score_analysis': ai_result.get('f_score_analysis', f_data.get('description', '')),
        'f_score_details': f_data.get('details', []),

        # Magic Formula
        'roic': _fmt_num(mf_data.get('roic')),
        'earnings_yield': _fmt_num(mf_data.get('earnings_yield')),
        'magic_formula_analysis': ai_result.get('magic_formula_analysis', mf_data.get('description', '')),

        # Lynch
        'lynch_category': lynch_data.get('category', 'N/A'),
        'lynch_valuation': lynch_data.get('valuation', 'N/A'),
        'lynch_analysis': ai_result.get('lynch_analysis', lynch_data.get('description', '')),

        # AI 分析結果
        'strengths': ai_result.get('strengths', ['數據不足']),
        'risks': ai_result.get('risks', ['數據不足']),
        'investment_suggestion': ai_result.get('investment_suggestion', '數據不足, 無法提供建議'),
        'target_action': ai_result.get('target_action', '觀望'),
        'key_monitoring': ai_result.get('key_monitoring', '持續追蹤財報更新'),

        # 報告資訊
        'report_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }

    html = template.render(**template_data)
    logger.info("✅ HTML 報告生成完成")
    return html


def _fmt_num(value, decimals=1) -> str:
    """格式化數值"""
    if value is None:
        return 'N/A'
    if isinstance(value, (int, float)):
        return f'{value:.{decimals}f}'
    return str(value)
