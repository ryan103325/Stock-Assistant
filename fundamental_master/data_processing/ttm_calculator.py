"""
TTM 計算模組
計算 Trailing Twelve Months (近四季加總) 數據
"""
from typing import Optional

from fundamental_master.utils.logger import setup_logger

logger = setup_logger('ttm_calculator')


def calculate_ttm(quarterly_values: list, start_index: int = 0) -> Optional[float]:
    """
    計算 TTM (近四季加總)

    Args:
        quarterly_values: 季度數據列表 (由新到舊排列)
        start_index: 起始位置 (0 = 最新四季, 4 = 前期四季)

    Returns:
        float: TTM 值, 若數據不足則返回 None
    """
    if len(quarterly_values) < start_index + 4:
        return None

    segment = quarterly_values[start_index:start_index + 4]

    # 檢查是否有 None 值
    if any(v is None for v in segment):
        return None

    return sum(segment)


def calculate_ttm_pair(quarterly_values: list) -> dict:
    """
    計算當期與前期 TTM

    Args:
        quarterly_values: 季度數據列表 (由新到舊排列, 至少 8 季)

    Returns:
        dict: {'current': float, 'previous': float}
    """
    return {
        'current': calculate_ttm(quarterly_values, start_index=0),
        'previous': calculate_ttm(quarterly_values, start_index=4),
    }


def build_ttm_dataset(income_data: dict, cashflow_data: dict) -> dict:
    """
    從損益表和現金流量表建立完整的 TTM 數據集

    Args:
        income_data: 損益表數據 {'data': {'營業收入': [q1, q2, ...], ...}}
        cashflow_data: 現金流量表數據

    Returns:
        dict: {
            '營業收入': {'current': float, 'previous': float},
            '營業成本': {'current': float, 'previous': float},
            ...
        }
    """
    result = {}

    # 損益表 TTM 項目
    income_fields = ['營業收入', '營業成本', '營業利益', '稅後淨利', '營業費用', '營業毛利']
    for field in income_fields:
        values = income_data.get('data', {}).get(field, [])
        if values:
            result[field] = calculate_ttm_pair(values)
            if result[field]['current'] is not None:
                logger.info(f"  TTM {field}: {result[field]['current']:,.0f}")

    # 現金流量表 TTM 項目
    cashflow_fields = ['營運現金流', '資本支出', '折舊費用']
    for field in cashflow_fields:
        values = cashflow_data.get('data', {}).get(field, [])
        if values:
            result[field] = calculate_ttm_pair(values)
            if result[field]['current'] is not None:
                logger.info(f"  TTM {field}: {result[field]['current']:,.0f}")

    return result
