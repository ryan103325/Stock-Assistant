"""
成長率與財務比率計算模組
"""
from typing import Optional

from fundamental_master.utils.logger import setup_logger

logger = setup_logger('ratio_calculator')


# ==================== 成長率計算 ====================

def growth_rate(current: Optional[float], previous: Optional[float]) -> Optional[float]:
    """
    計算年增率 (YoY Growth Rate)

    Args:
        current: 當期值
        previous: 前期值

    Returns:
        float: 成長率 (百分比), 無法計算則返回 None
    """
    if current is None or previous is None or previous == 0:
        return None
    return ((current - previous) / abs(previous)) * 100


def cagr(start_value: float, end_value: float, years: int) -> Optional[float]:
    """
    計算複合年增長率 (CAGR)

    Args:
        start_value: 起始值
        end_value: 結束值
        years: 年數

    Returns:
        float: CAGR (百分比)
    """
    if start_value is None or end_value is None or years <= 0:
        return None
    if start_value <= 0 or end_value <= 0:
        return None

    return ((end_value / start_value) ** (1 / years) - 1) * 100


# ==================== 財務比率計算 ====================

def gross_margin(revenue: Optional[float], cogs: Optional[float]) -> Optional[float]:
    """毛利率 (%)"""
    if revenue is None or cogs is None or revenue == 0:
        return None
    return ((revenue - cogs) / revenue) * 100


def operating_margin(revenue: Optional[float], operating_income: Optional[float]) -> Optional[float]:
    """營業利益率 (%)"""
    if revenue is None or operating_income is None or revenue == 0:
        return None
    return (operating_income / revenue) * 100


def net_margin(revenue: Optional[float], net_income: Optional[float]) -> Optional[float]:
    """稅後淨利率 (%)"""
    if revenue is None or net_income is None or revenue == 0:
        return None
    return (net_income / revenue) * 100


def roa(net_income: Optional[float], total_assets: Optional[float]) -> Optional[float]:
    """總資產報酬率 ROA (%)"""
    if net_income is None or total_assets is None or total_assets == 0:
        return None
    return (net_income / total_assets) * 100


def roe(net_income: Optional[float], equity: Optional[float]) -> Optional[float]:
    """股東權益報酬率 ROE (%)"""
    if net_income is None or equity is None or equity == 0:
        return None
    return (net_income / equity) * 100


def current_ratio(current_assets: Optional[float], current_liabilities: Optional[float]) -> Optional[float]:
    """流動比率"""
    if current_assets is None or current_liabilities is None or current_liabilities == 0:
        return None
    return current_assets / current_liabilities


def debt_ratio(total_liabilities: Optional[float], total_assets: Optional[float]) -> Optional[float]:
    """負債比率 (%)"""
    if total_liabilities is None or total_assets is None or total_assets == 0:
        return None
    return (total_liabilities / total_assets) * 100


def asset_turnover(revenue: Optional[float], total_assets: Optional[float]) -> Optional[float]:
    """資產周轉率"""
    if revenue is None or total_assets is None or total_assets == 0:
        return None
    return revenue / total_assets


def enterprise_value(market_cap_billion: Optional[float],
                     total_debt: Optional[float],
                     cash: Optional[float]) -> Optional[float]:
    """
    計算企業價值 (EV)

    Args:
        market_cap_billion: 市值 (億元)
        total_debt: 總負債 (億元)
        cash: 現金及約當現金 (億元)

    Returns:
        float: 企業價值 (億元)
    """
    if market_cap_billion is None or total_debt is None or cash is None:
        return None
    return market_cap_billion + total_debt - cash


def working_capital(current_assets: Optional[float], current_liabilities: Optional[float]) -> Optional[float]:
    """營運資金"""
    if current_assets is None or current_liabilities is None:
        return None
    return current_assets - current_liabilities


# ==================== 整合計算 ====================

def calculate_all_ratios(stock_info: dict, balance_data: dict, ttm_data: dict) -> dict:
    """
    計算所有財務比率

    Args:
        stock_info: 個股首頁數據
        balance_data: 資產負債表數據 (最新一季)
        ttm_data: TTM 數據

    Returns:
        dict: 包含所有計算比率
    """
    # 取得最新一季資產負債表數據
    bs = {}
    for field, values in balance_data.get('data', {}).items():
        bs[field] = values[0] if values else None

    # 取得 TTM 數據
    revenue = ttm_data.get('營業收入', {}).get('current')
    cogs = ttm_data.get('營業成本', {}).get('current')
    op_income = ttm_data.get('營業利益', {}).get('current')
    ni = ttm_data.get('稅後淨利', {}).get('current')
    cfo = ttm_data.get('營運現金流', {}).get('current')

    prev_revenue = ttm_data.get('營業收入', {}).get('previous')

    result = {
        # 獲利能力
        '毛利率': gross_margin(revenue, cogs),
        '營業利益率': operating_margin(revenue, op_income),
        '稅後淨利率': net_margin(revenue, ni),
        'ROA': roa(ni, bs.get('總資產')),
        'ROE': roe(ni, bs.get('股東權益')),

        # 成長性
        '營收成長率': growth_rate(revenue, prev_revenue),

        # 財務結構
        '流動比率': current_ratio(bs.get('流動資產'), bs.get('流動負債')),
        '負債比率': debt_ratio(bs.get('總負債'), bs.get('總資產')),
        '資產周轉率': asset_turnover(revenue, bs.get('總資產')),

        # 企業價值
        '營運資金': working_capital(bs.get('流動資產'), bs.get('流動負債')),
        '企業價值': enterprise_value(
            stock_info.get('市值_億'),
            bs.get('總負債'),
            bs.get('現金及約當現金')
        ),
    }

    logger.info("📊 財務比率計算完成")
    for key, value in result.items():
        if value is not None:
            if '率' in key and key != '流動比率' or 'RO' in key:
                logger.info(f"  {key}: {value:.2f}%")
            else:
                logger.info(f"  {key}: {value:,.2f}")

    return result
