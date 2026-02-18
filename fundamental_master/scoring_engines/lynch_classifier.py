"""
Peter Lynch Classification 評分模組
依據企業成長特性進行分類定位

五大類別:
- 快速成長股: EPS CAGR > 20%
- 穩定成長股: 10% < CAGR ≤ 20%
- 景氣循環股: 特定產業
- 資產股: PB < 1, 高股息
- 轉機股: 連續虧損後轉盈
"""
from typing import Optional

from fundamental_master.utils.logger import setup_logger
from fundamental_master.data_processing.ratio_calculator import cagr

logger = setup_logger('lynch_classifier')

# 景氣循環產業關鍵字
CYCLICAL_INDUSTRIES = [
    '鋼鐵', '水泥', '航運', '化工', '塑膠', '紡織',
    '造紙', '玻璃陶瓷', '橡膠', '營建', '汽車',
]


def classify_lynch(data: dict) -> dict:
    """
    Peter Lynch 企業分類

    Args:
        data: {
            'historical_eps': {
                '年度': [2024, 2023, 2022, 2021, 2020],
                'EPS': [10.5, 9.2, 8.0, 6.5, 5.0],
            },
            'stock_info': {
                '收盤價': float,
                '每股淨值': float,
                '殖利率': float,
                '本益比': float,
                '產業分類': str,
            },
            'ttm': {
                '營業收入': {'current': float, 'previous': float},
                '稅後淨利': {'current': float, 'previous': float},
            }
        }

    Returns:
        dict: {
            'category': str,
            'eps_cagr': float (%),
            'fair_pe_range': tuple,
            'description': str,
            'strategy': str,
        }
    """
    logger.info("🎯 執行 Peter Lynch 分類...")

    eps_data = data.get('historical_eps', {})
    stock_info = data.get('stock_info', {})
    ttm = data.get('ttm', {})

    eps_list = eps_data.get('EPS', [])
    years = eps_data.get('年度', [])
    industry = stock_info.get('產業分類', '')
    price = stock_info.get('收盤價')
    nav = stock_info.get('每股淨值')
    div_yield = stock_info.get('殖利率')
    pe = stock_info.get('本益比')

    ni_cur = ttm.get('稅後淨利', {}).get('current')
    ni_prev = ttm.get('稅後淨利', {}).get('previous')

    # ==================== 計算 EPS CAGR ====================
    eps_growth = None
    if len(eps_list) >= 3:
        start_eps = eps_list[-1]  # 最早年度
        end_eps = eps_list[0]    # 最新年度
        num_years = len(eps_list) - 1
        if start_eps and end_eps and start_eps > 0 and end_eps > 0:
            eps_growth = cagr(start_eps, end_eps, num_years)

    # ==================== 分類邏輯 ====================

    # 1. 轉機股: 連續虧損後首次轉盈
    if _is_turnaround(eps_list):
        category = '轉機股'
        fair_pe = None
        strategy = '高風險高報酬,設好停損,關注營收與毛利率改善趨勢'
        description = '企業正從虧損轉向獲利,具有轉型潛力'

    # 2. 景氣循環股: 特定產業
    elif _is_cyclical(industry):
        category = '景氣循環股'
        fair_pe = (8, 12)
        strategy = '逆向操作,在景氣低谷 (PE 低/營收下滑) 時買入,景氣高峰時賣出'
        description = f'屬於景氣循環產業 ({industry}),獲利隨景氣波動劇烈'

    # 3. 資產股: PB < 1 且高股息
    elif _is_asset_play(price, nav, div_yield):
        category = '資產股'
        fair_pe = None
        strategy = '長期持有,領取穩定股息,等待資產重估'
        pb = price / nav if price and nav and nav > 0 else None
        description = f'股價低於淨值 (PB={pb:.2f}),適合價值投資' if pb else '股價低於淨值,適合價值投資'

    # 4. 快速成長股: CAGR > 20%
    elif eps_growth is not None and eps_growth > 20:
        category = '快速成長股'
        fair_pe = (eps_growth * 1.0, eps_growth * 2.0)
        strategy = '短中期持有,密切關注成長率是否放緩,設定嚴格停利'
        description = f'EPS 年複合成長率 {eps_growth:.1f}%,成長動能強勁'

    # 5. 穩定成長股: 10% < CAGR ≤ 20%
    elif eps_growth is not None and eps_growth > 10:
        category = '穩定成長股'
        fair_pe = (eps_growth * 1.0, eps_growth * 1.5)
        strategy = '中長期持有,適合作為投資組合的核心部位'
        description = f'EPS 年複合成長率 {eps_growth:.1f}%,穩定成長'

    # 6. 預設
    else:
        category = '穩定成長股'
        fair_pe = (12, 18)
        strategy = '中長期持有,關注股利政策與營收趨勢'
        description = f'EPS CAGR {eps_growth:.1f}%' if eps_growth else '數據不足以精確分類,暫歸為穩定成長股'

    # 估值分析
    valuation = None
    if pe and fair_pe:
        if pe < fair_pe[0]:
            valuation = '低估'
        elif pe > fair_pe[1]:
            valuation = '高估'
        else:
            valuation = '合理'

    logger.info(f"🎯 Lynch 分類: {category}")
    logger.info(f"  EPS CAGR: {eps_growth:.1f}%" if eps_growth else "  EPS CAGR: N/A")
    logger.info(f"  合理 PE: {fair_pe}" if fair_pe else "  合理 PE: N/A")
    logger.info(f"  當前 PE: {pe}, 估值: {valuation}" if pe and valuation else "")

    return {
        'category': category,
        'eps_cagr': eps_growth,
        'fair_pe_range': fair_pe,
        'current_pe': pe,
        'valuation': valuation,
        'description': description,
        'strategy': strategy,
    }


def _is_turnaround(eps_list: list) -> bool:
    """判斷是否為轉機股: 之前連續虧損, 最近轉正"""
    if len(eps_list) < 3:
        return False

    latest_eps = eps_list[0]
    if latest_eps is None or latest_eps <= 0:
        return False

    # 至少前兩年有虧損
    loss_count = sum(1 for e in eps_list[1:3] if e is not None and e < 0)
    return loss_count >= 1


def _is_cyclical(industry: str) -> bool:
    """判斷是否為景氣循環產業"""
    if not industry:
        return False
    return any(keyword in industry for keyword in CYCLICAL_INDUSTRIES)


def _is_asset_play(price: Optional[float], nav: Optional[float],
                   div_yield: Optional[float]) -> bool:
    """判斷是否為資產股: PB < 1 且殖利率 > 5%"""
    if price is None or nav is None or nav <= 0:
        return False

    pb = price / nav
    if pb >= 1.0:
        return False

    # 殖利率 > 5% (如果有數據)
    if div_yield is not None and div_yield >= 5:
        return True

    # 即使沒有殖利率數據, PB < 0.7 也視為資產股
    if pb < 0.7:
        return True

    return False
