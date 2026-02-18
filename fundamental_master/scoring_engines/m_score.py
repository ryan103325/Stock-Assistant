"""
Beneish M-Score 評分模組
偵測財務報表操縱風險

判定標準:
- M-Score > -1.78 → FAIL (疑似操縱)
- M-Score ≤ -1.78 → PASS (財報可信)
"""
from typing import Optional

from fundamental_master.utils.config import Config
from fundamental_master.utils.logger import setup_logger

logger = setup_logger('m_score')


def calculate_m_score(data: dict) -> dict:
    """
    計算 Beneish M-Score

    Args:
        data: {
            'ttm': {
                '營業收入': {'current': float, 'previous': float},
                '營業成本': {'current': float, 'previous': float},
                '營業費用': {'current': float, 'previous': float},
            },
            'balance_current': {
                '應收帳款': float, '總資產': float, '流動資產': float,
                '不動產廠房設備': float, '總負債': float,
            },
            'balance_previous': {
                '應收帳款': float, '總資產': float, '流動資產': float,
                '不動產廠房設備': float, '總負債': float,
            },
            'depreciation_current': float,  # TTM 折舊
            'depreciation_previous': float, # 前期 TTM 折舊
            'cfo_current': float,           # TTM 營運現金流
        }

    Returns:
        dict: {
            'score': float,
            'judgment': str ('PASS' / 'FAIL'),
            'indicators': dict (8 個指標的詳細數據),
            'description': str,
        }
    """
    logger.info("🔍 計算 Beneish M-Score...")

    ttm = data.get('ttm', {})
    bc = data.get('balance_current', {})
    bp = data.get('balance_previous', {})
    dep_cur = data.get('depreciation_current')
    dep_prev = data.get('depreciation_previous')
    cfo = data.get('cfo_current')

    # 取得 TTM 數據
    rev_cur = ttm.get('營業收入', {}).get('current')
    rev_prev = ttm.get('營業收入', {}).get('previous')
    cogs_cur = ttm.get('營業成本', {}).get('current')
    cogs_prev = ttm.get('營業成本', {}).get('previous')
    sgna_cur = ttm.get('營業費用', {}).get('current')
    sgna_prev = ttm.get('營業費用', {}).get('previous')
    net_income_cur = ttm.get('稅後淨利', {}).get('current')

    indicators = {}

    # 1. DSRI: 應收帳款天數指數
    dsri = _safe_divide(
        _safe_divide(bc.get('應收帳款'), rev_cur),
        _safe_divide(bp.get('應收帳款'), rev_prev)
    )
    indicators['DSRI'] = {'value': dsri, 'name': '應收帳款天數指數', 'weight': 0.920}

    # 2. GMI: 毛利率指數
    gm_prev = _safe_divide(rev_prev - cogs_prev if rev_prev and cogs_prev else None, rev_prev)
    gm_cur = _safe_divide(rev_cur - cogs_cur if rev_cur and cogs_cur else None, rev_cur)
    gmi = _safe_divide(gm_prev, gm_cur)
    indicators['GMI'] = {'value': gmi, 'name': '毛利率指數', 'weight': 0.528}

    # 3. AQI: 資產品質指數
    aqi_cur = _asset_quality(bc.get('流動資產'), bc.get('不動產廠房設備'), bc.get('總資產'))
    aqi_prev = _asset_quality(bp.get('流動資產'), bp.get('不動產廠房設備'), bp.get('總資產'))
    aqi = _safe_divide(aqi_cur, aqi_prev)
    indicators['AQI'] = {'value': aqi, 'name': '資產品質指數', 'weight': 0.404}

    # 4. SGI: 營收成長指數
    sgi = _safe_divide(rev_cur, rev_prev)
    indicators['SGI'] = {'value': sgi, 'name': '營收成長指數', 'weight': 0.892}

    # 5. DEPI: 折舊指數
    depi_prev = _depreciation_rate(dep_prev, bp.get('不動產廠房設備'))
    depi_cur = _depreciation_rate(dep_cur, bc.get('不動產廠房設備'))
    depi = _safe_divide(depi_prev, depi_cur)
    indicators['DEPI'] = {'value': depi, 'name': '折舊指數', 'weight': 0.115}

    # 6. SGAI: 營業費用指數
    sgai_cur = _safe_divide(sgna_cur, rev_cur)
    sgai_prev = _safe_divide(sgna_prev, rev_prev)
    sgai = _safe_divide(sgai_cur, sgai_prev)
    indicators['SGAI'] = {'value': sgai, 'name': '營業費用指數', 'weight': -0.172}

    # 7. TATA: 總應計項目比率
    tata = None
    if net_income_cur is not None and cfo is not None and bc.get('總資產'):
        tata = (net_income_cur - cfo) / bc['總資產']
    indicators['TATA'] = {'value': tata, 'name': '總應計項目', 'weight': 4.679}

    # 8. LVGI: 槓桿指數
    lev_cur = _safe_divide(bc.get('總負債'), bc.get('總資產'))
    lev_prev = _safe_divide(bp.get('總負債'), bp.get('總資產'))
    lvgi = _safe_divide(lev_cur, lev_prev)
    indicators['LVGI'] = {'value': lvgi, 'name': '槓桿指數', 'weight': -0.327}

    # 計算 M-Score
    m_score = _compute_m_score(indicators)

    # 判定
    if m_score is not None:
        judgment = 'FAIL' if m_score > Config.M_SCORE_THRESHOLD else 'PASS'
        emoji = '⚠️' if judgment == 'FAIL' else '✅'
        description = '疑似財報操縱,需進一步調查' if judgment == 'FAIL' else '財報數據可信,無明顯操縱跡象'
    else:
        judgment = 'N/A'
        emoji = '❓'
        description = '數據不足,無法計算'

    logger.info(f"{emoji} M-Score: {m_score:.4f} → {judgment}" if m_score else f"{emoji} M-Score: N/A")

    return {
        'score': m_score,
        'judgment': judgment,
        'threshold': Config.M_SCORE_THRESHOLD,
        'indicators': indicators,
        'description': description,
    }


def _compute_m_score(indicators: dict) -> Optional[float]:
    """計算 M-Score 綜合分數"""
    coefficients = {
        'DSRI': 0.920, 'GMI': 0.528, 'AQI': 0.404, 'SGI': 0.892,
        'DEPI': 0.115, 'SGAI': -0.172, 'TATA': 4.679, 'LVGI': -0.327,
    }
    intercept = -4.84

    score = intercept
    missing_count = 0

    for key, coeff in coefficients.items():
        value = indicators.get(key, {}).get('value')
        if value is not None:
            score += coeff * value
        else:
            missing_count += 1

    # 如果超過 3 個指標缺失, 視為無法計算
    if missing_count > 3:
        return None

    return score


def _safe_divide(a: Optional[float], b: Optional[float]) -> Optional[float]:
    """安全除法"""
    if a is None or b is None or b == 0:
        return None
    return a / b


def _asset_quality(current_assets: Optional[float],
                   ppe: Optional[float],
                   total_assets: Optional[float]) -> Optional[float]:
    """計算資產品質比率: 1 - (流動資產 + PPE) / 總資產"""
    if current_assets is None or ppe is None or total_assets is None or total_assets == 0:
        return None
    return 1 - (current_assets + ppe) / total_assets


def _depreciation_rate(depreciation: Optional[float],
                       ppe: Optional[float]) -> Optional[float]:
    """計算折舊率: 折舊 / (PPE + 折舊)"""
    if depreciation is None or ppe is None:
        return None
    denominator = ppe + depreciation
    if denominator == 0:
        return None
    return depreciation / denominator
