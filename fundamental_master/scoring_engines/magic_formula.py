"""
Greenblatt Magic Formula 評分模組
尋找兼具優質經營與合理價格的投資標的

核心指標:
- ROIC (資本回報率): 企業運用資本創造利潤的效率
- Earnings Yield (盈餘殖利率): 當前價格相對盈餘的吸引力
"""
from typing import Optional

from fundamental_master.utils.logger import setup_logger

logger = setup_logger('magic_formula')


def calculate_magic_formula(data: dict) -> dict:
    """
    計算 Greenblatt Magic Formula 指標

    Args:
        data: {
            'ttm': {
                '營業利益': {'current': float},  # EBIT (TTM)
            },
            'balance': {
                '流動資產': float, '流動負債': float,
                '不動產廠房設備': float, '總負債': float,
                '現金及約當現金': float,
            },
            'market_cap_billion': float,  # 市值 (億元)
        }

    Returns:
        dict: {
            'roic': float (%), ROIC 資本回報率
            'earnings_yield': float (%), 盈餘殖利率
            'description': str,
        }
    """
    logger.info("💎 計算 Greenblatt Magic Formula...")

    ttm = data.get('ttm', {})
    bs = data.get('balance', {})
    market_cap = data.get('market_cap_billion')

    ebit = ttm.get('營業利益', {}).get('current')

    # ==================== ROIC 計算 ====================
    # ROIC = EBIT / (淨營運資本 + 固定資產淨值)
    # 淨營運資本 = 流動資產 - 流動負債
    # 固定資產淨值 = 不動產廠房設備

    net_wc = _safe_subtract(bs.get('流動資產'), bs.get('流動負債'))
    # 用「固定資產」替代「不動產廠房設備」(Goodinfo 欄位名稱)
    ppe = bs.get('固定資產') or bs.get('不動產廠房設備')

    invested_capital = None
    if net_wc is not None and ppe is not None:
        invested_capital = net_wc + ppe

    roic = None
    if ebit is not None and invested_capital is not None and invested_capital > 0:
        roic = (ebit / invested_capital) * 100

    # ==================== 盈餘殖利率計算 ====================
    # EY = EBIT / EV
    # EV = 市值 + 總負債 - 現金

    ev = None
    if market_cap is not None and bs.get('總負債') is not None and bs.get('現金及約當現金') is not None:
        # 市值、總負債、現金都是億元, 直接計算
        ev = market_cap + bs['總負債'] - bs['現金及約當現金']

    earnings_yield = None
    if ebit is not None and ev is not None and ev > 0:
        earnings_yield = (ebit / ev) * 100

    # 評估
    descriptions = []
    if roic is not None:
        if roic > 25:
            descriptions.append(f'ROIC {roic:.1f}%,資本回報率優異')
        elif roic > 15:
            descriptions.append(f'ROIC {roic:.1f}%,資本回報率良好')
        elif roic > 10:
            descriptions.append(f'ROIC {roic:.1f}%,資本回報率一般')
        else:
            descriptions.append(f'ROIC {roic:.1f}%,資本回報率偏低')

    if earnings_yield is not None:
        if earnings_yield > 10:
            descriptions.append(f'盈餘殖利率 {earnings_yield:.1f}%,估值極具吸引力')
        elif earnings_yield > 6:
            descriptions.append(f'盈餘殖利率 {earnings_yield:.1f}%,估值合理')
        elif earnings_yield > 3:
            descriptions.append(f'盈餘殖利率 {earnings_yield:.1f}%,估值偏高')
        else:
            descriptions.append(f'盈餘殖利率 {earnings_yield:.1f}%,估值過高')

    description = '; '.join(descriptions) if descriptions else '數據不足,無法評估'

    logger.info(f"  ROIC: {roic:.2f}%" if roic else "  ROIC: N/A")
    logger.info(f"  盈餘殖利率: {earnings_yield:.2f}%" if earnings_yield else "  盈餘殖利率: N/A")

    return {
        'roic': roic,
        'earnings_yield': earnings_yield,
        'enterprise_value': ev,
        'invested_capital': invested_capital,
        'ebit': ebit,
        'description': description,
    }


def _safe_subtract(a, b):
    if a is None or b is None:
        return None
    return a - b
