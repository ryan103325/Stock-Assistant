"""
Altman Z-Score 評分模組
預測企業未來 2 年內的破產機率

判定標準:
- Z > 2.99  → Safe Zone (財務安全)
- 1.81 ≤ Z ≤ 2.99 → Grey Zone (需關注)
- Z < 1.81  → Distress Zone (高風險)
"""
from typing import Optional

from fundamental_master.utils.config import Config
from fundamental_master.utils.logger import setup_logger

logger = setup_logger('z_score')


def calculate_z_score(data: dict) -> dict:
    """
    計算 Altman Z-Score (上市公司版本)

    Z = 1.2×X1 + 1.4×X2 + 3.3×X3 + 0.6×X4 + 1.0×X5

    Args:
        data: {
            'balance': {
                '流動資產': float, '流動負債': float,
                '總資產': float, '保留盈餘': float, '總負債': float,
            },
            'ttm': {
                '營業利益': {'current': float},
                '營業收入': {'current': float},
            },
            'market_cap_billion': float,  # 市值 (億元)
        }

    Returns:
        dict: {
            'score': float,
            'judgment': str,
            'zone': str,
            'indicators': dict,
            'description': str,
        }
    """
    logger.info("💪 計算 Altman Z-Score...")

    bs = data.get('balance', {})
    ttm = data.get('ttm', {})
    market_cap = data.get('market_cap_billion')

    total_assets = bs.get('總資產')

    # 指標計算
    indicators = {}

    # X1: 營運資金 / 總資產
    wc = _safe_subtract(bs.get('流動資產'), bs.get('流動負債'))
    x1 = _safe_divide(wc, total_assets)
    indicators['X1'] = {
        'value': x1,
        'name': '營運資金/總資產',
        'weight': 1.2,
        'formula': '(流動資產 - 流動負債) / 總資產',
    }

    # X2: 保留盈餘 / 總資產
    x2 = _safe_divide(bs.get('保留盈餘'), total_assets)
    indicators['X2'] = {
        'value': x2,
        'name': '保留盈餘/總資產',
        'weight': 1.4,
        'formula': '保留盈餘 / 總資產',
    }

    # X3: EBIT / 總資產
    ebit = ttm.get('營業利益', {}).get('current')
    x3 = _safe_divide(ebit, total_assets)
    indicators['X3'] = {
        'value': x3,
        'name': 'EBIT/總資產',
        'weight': 3.3,
        'formula': '營業利益(TTM) / 總資產',
    }

    # X4: 市值 / 總負債
    total_debt = bs.get('總負債')
    # 市值和總負債都是億元單位, 直接相除
    x4 = _safe_divide(market_cap, total_debt)
    indicators['X4'] = {
        'value': x4,
        'name': '市值/總負債',
        'weight': 0.6,
        'formula': '市值 / 總負債',
    }

    # X5: 營收 / 總資產
    revenue = ttm.get('營業收入', {}).get('current')
    x5 = _safe_divide(revenue, total_assets)
    indicators['X5'] = {
        'value': x5,
        'name': '營收/總資產',
        'weight': 1.0,
        'formula': '營業收入(TTM) / 總資產',
    }

    # 計算 Z-Score
    z_score = _compute_z_score(indicators)

    # 判定
    if z_score is not None:
        if z_score > Config.Z_SCORE_SAFE_ZONE:
            zone = 'Safe'
            judgment = '🟢 Safe Zone'
            description = '財務體質健康,破產風險極低'
        elif z_score >= Config.Z_SCORE_GREY_ZONE:
            zone = 'Grey'
            judgment = '🟡 Grey Zone'
            description = '財務處於灰色地帶,需持續關注'
        else:
            zone = 'Distress'
            judgment = '🔴 Distress Zone'
            description = '高度財務風險,有破產可能'
    else:
        zone = 'N/A'
        judgment = '❓ 無法計算'
        description = '數據不足,無法評估'

    logger.info(f"{judgment}: Z-Score = {z_score:.4f}" if z_score else f"{judgment}")

    return {
        'score': z_score,
        'judgment': judgment,
        'zone': zone,
        'thresholds': {
            'safe': Config.Z_SCORE_SAFE_ZONE,
            'grey': Config.Z_SCORE_GREY_ZONE,
        },
        'indicators': indicators,
        'description': description,
    }


def _compute_z_score(indicators: dict) -> Optional[float]:
    """計算 Z-Score"""
    weights = {'X1': 1.2, 'X2': 1.4, 'X3': 3.3, 'X4': 0.6, 'X5': 1.0}

    score = 0
    missing_count = 0

    for key, weight in weights.items():
        value = indicators.get(key, {}).get('value')
        if value is not None:
            score += weight * value
        else:
            missing_count += 1

    if missing_count > 2:
        return None

    return score


def _safe_divide(a: Optional[float], b: Optional[float]) -> Optional[float]:
    """安全除法"""
    if a is None or b is None or b == 0:
        return None
    return a / b


def _safe_subtract(a: Optional[float], b: Optional[float]) -> Optional[float]:
    """安全減法"""
    if a is None or b is None:
        return None
    return a - b
