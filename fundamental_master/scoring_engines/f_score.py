"""
Piotroski F-Score 評分模組
判斷企業基本面是改善或惡化

九大檢測項目 (每項 0 或 1 分):
- 獲利能力: ROA > 0, CFO > 0, ΔROA > 0, CFO > NI
- 財務槓桿: 長期負債下降, 流動比率上升, 無增資
- 營運效率: 毛利率上升, 資產周轉率上升

評級:
- 8-9 分 → 強勢改善
- 4-7 分 → 中性
- 0-3 分 → 顯著惡化
"""
from typing import Optional

from fundamental_master.utils.config import Config
from fundamental_master.utils.logger import setup_logger

logger = setup_logger('f_score')


def calculate_f_score(data: dict) -> dict:
    """
    計算 Piotroski F-Score

    Args:
        data: {
            'ttm': {
                '稅後淨利': {'current': float, 'previous': float},
                '營運現金流': {'current': float, 'previous': float},
                '營業收入': {'current': float, 'previous': float},
                '營業成本': {'current': float, 'previous': float},
            },
            'balance_current': {
                '總資產': float, '長期負債': float,
                '流動資產': float, '流動負債': float,
            },
            'balance_previous': {
                '總資產': float, '長期負債': float,
                '流動資產': float, '流動負債': float,
            },
            'shares_current': float,
            'shares_previous': float,
        }

    Returns:
        dict: {
            'score': int (0-9),
            'judgment': str,
            'details': list of dict,
            'description': str,
        }
    """
    logger.info("📈 計算 Piotroski F-Score...")

    ttm = data.get('ttm', {})
    bc = data.get('balance_current', {})
    bp = data.get('balance_previous', {})

    details = []
    total_score = 0

    # ==================== 獲利能力 (4 項) ====================

    # 1. ROA > 0
    ni_cur = ttm.get('稅後淨利', {}).get('current')
    ta_cur = bc.get('總資產')
    roa_cur = _safe_divide(ni_cur, ta_cur)
    score1 = 1 if roa_cur is not None and roa_cur > 0 else 0
    details.append({
        'category': '獲利能力',
        'indicator': 'ROA > 0',
        'value': f"{roa_cur * 100:.2f}%" if roa_cur else 'N/A',
        'score': score1,
        'passed': score1 == 1,
    })
    total_score += score1

    # 2. CFO > 0
    cfo_cur = ttm.get('營運現金流', {}).get('current')
    score2 = 1 if cfo_cur is not None and cfo_cur > 0 else 0
    details.append({
        'category': '獲利能力',
        'indicator': '營運現金流 > 0',
        'value': f"{cfo_cur:,.0f}" if cfo_cur else 'N/A',
        'score': score2,
        'passed': score2 == 1,
    })
    total_score += score2

    # 3. ΔROA > 0 (ROA 提升)
    ni_prev = ttm.get('稅後淨利', {}).get('previous')
    ta_prev = bp.get('總資產')
    roa_prev = _safe_divide(ni_prev, ta_prev)
    score3 = 1 if roa_cur is not None and roa_prev is not None and roa_cur > roa_prev else 0
    details.append({
        'category': '獲利能力',
        'indicator': 'ΔROA > 0',
        'value': f"{(roa_cur - roa_prev) * 100:.2f}%" if roa_cur and roa_prev else 'N/A',
        'score': score3,
        'passed': score3 == 1,
    })
    total_score += score3

    # 4. CFO > NI (盈餘含金量)
    score4 = 1 if cfo_cur is not None and ni_cur is not None and cfo_cur > ni_cur else 0
    details.append({
        'category': '獲利能力',
        'indicator': 'CFO > 淨利 (盈餘含金量)',
        'value': f"CFO={cfo_cur:,.0f}, NI={ni_cur:,.0f}" if cfo_cur and ni_cur else 'N/A',
        'score': score4,
        'passed': score4 == 1,
    })
    total_score += score4

    # ==================== 財務槓桿 (3 項) ====================

    # 5. 長期負債比率下降
    ltd_cur = bc.get('長期負債')
    ltd_prev = bp.get('長期負債')
    ltd_ratio_cur = _safe_divide(ltd_cur, ta_cur)
    ltd_ratio_prev = _safe_divide(ltd_prev, ta_prev)
    score5 = 1 if ltd_ratio_cur is not None and ltd_ratio_prev is not None and ltd_ratio_cur < ltd_ratio_prev else 0
    details.append({
        'category': '財務槓桿',
        'indicator': '長期負債比率下降',
        'value': f"{ltd_ratio_cur * 100:.2f}% → {ltd_ratio_prev * 100:.2f}%" if ltd_ratio_cur and ltd_ratio_prev else 'N/A',
        'score': score5,
        'passed': score5 == 1,
    })
    total_score += score5

    # 6. 流動比率上升
    cr_cur = _safe_divide(bc.get('流動資產'), bc.get('流動負債'))
    cr_prev = _safe_divide(bp.get('流動資產'), bp.get('流動負債'))
    score6 = 1 if cr_cur is not None and cr_prev is not None and cr_cur > cr_prev else 0
    details.append({
        'category': '財務槓桿',
        'indicator': '流動比率上升',
        'value': f"{cr_cur:.2f} → {cr_prev:.2f}" if cr_cur and cr_prev else 'N/A',
        'score': score6,
        'passed': score6 == 1,
    })
    total_score += score6

    # 7. 無增資 (發行股數未增加)
    shares_cur = data.get('shares_current')
    shares_prev = data.get('shares_previous')
    score7 = 1 if shares_cur is not None and shares_prev is not None and shares_cur <= shares_prev else 0
    if shares_cur is None or shares_prev is None:
        score7 = 1  # 預設為通過 (數據不足時)
    details.append({
        'category': '財務槓桿',
        'indicator': '無增資 (股數未增加)',
        'value': f"{shares_cur:,.0f} → {shares_prev:,.0f}" if shares_cur and shares_prev else '預設通過',
        'score': score7,
        'passed': score7 == 1,
    })
    total_score += score7

    # ==================== 營運效率 (2 項) ====================

    # 8. 毛利率上升
    rev_cur = ttm.get('營業收入', {}).get('current')
    cogs_cur = ttm.get('營業成本', {}).get('current')
    rev_prev = ttm.get('營業收入', {}).get('previous')
    cogs_prev = ttm.get('營業成本', {}).get('previous')

    gm_cur = _safe_divide(_safe_subtract(rev_cur, cogs_cur), rev_cur)
    gm_prev = _safe_divide(_safe_subtract(rev_prev, cogs_prev), rev_prev)
    score8 = 1 if gm_cur is not None and gm_prev is not None and gm_cur > gm_prev else 0
    details.append({
        'category': '營運效率',
        'indicator': '毛利率上升',
        'value': f"{gm_cur * 100:.2f}% → {gm_prev * 100:.2f}%" if gm_cur and gm_prev else 'N/A',
        'score': score8,
        'passed': score8 == 1,
    })
    total_score += score8

    # 9. 資產周轉率上升
    at_cur = _safe_divide(rev_cur, ta_cur)
    at_prev = _safe_divide(rev_prev, ta_prev)
    score9 = 1 if at_cur is not None and at_prev is not None and at_cur > at_prev else 0
    details.append({
        'category': '營運效率',
        'indicator': '資產周轉率上升',
        'value': f"{at_cur:.4f} → {at_prev:.4f}" if at_cur and at_prev else 'N/A',
        'score': score9,
        'passed': score9 == 1,
    })
    total_score += score9

    # 判定
    if total_score >= Config.F_SCORE_STRONG:
        judgment = '🟢 基本面強勢改善'
        description = f'得分 {total_score}/9,經營體質正在顯著改善'
    elif total_score <= Config.F_SCORE_WEAK:
        judgment = '🔴 基本面顯著惡化'
        description = f'得分 {total_score}/9,經營體質呈現惡化趨勢'
    else:
        judgment = '🟡 基本面中性'
        description = f'得分 {total_score}/9,經營體質變化不大'

    logger.info(f"{judgment}: F-Score = {total_score}/9")

    return {
        'score': total_score,
        'max_score': 9,
        'judgment': judgment,
        'details': details,
        'description': description,
    }


def _safe_divide(a, b):
    if a is None or b is None or b == 0:
        return None
    return a / b


def _safe_subtract(a, b):
    if a is None or b is None:
        return None
    return a - b
