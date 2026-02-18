"""
數據驗證模組
驗證爬取數據的完整性與合理性
"""
from typing import Optional

from fundamental_master.utils.logger import setup_logger
from fundamental_master.utils.exceptions import DataValidationError

logger = setup_logger('data_validator')


class DataValidator:
    """財務數據驗證器"""

    # 各模型最少需要的季度數
    MIN_QUARTERS_FOR_TTM = 4  # TTM 需要 4 季
    MIN_QUARTERS_FOR_COMPARE = 8  # 比較性數據需要 8 季 (當期 + 去年同期)

    # 資產負債表必要欄位
    REQUIRED_BALANCE_SHEET = [
        '總資產', '總負債', '流動資產', '流動負債',
        '現金及約當現金', '股東權益',
    ]

    # 損益表必要欄位
    REQUIRED_INCOME_STATEMENT = [
        '營業收入', '營業成本', '營業利益', '稅後淨利',
    ]

    # 現金流量表必要欄位
    REQUIRED_CASHFLOW = [
        '營運現金流',
    ]

    # 個股首頁必要欄位
    REQUIRED_STOCK_INFO = [
        '收盤價', '市值_億',
    ]

    @classmethod
    def validate_stock_info(cls, data: dict) -> dict:
        """
        驗證個股首頁數據

        Args:
            data: 個股首頁數據

        Returns:
            dict: {'valid': bool, 'missing': list, 'warnings': list}
        """
        result = {'valid': True, 'missing': [], 'warnings': []}

        for field in cls.REQUIRED_STOCK_INFO:
            if data.get(field) is None:
                result['missing'].append(field)
                result['valid'] = False

        # 合理性檢查
        price = data.get('收盤價')
        if price is not None and (price <= 0 or price > 50000):
            result['warnings'].append(f"收盤價異常: {price}")

        market_cap = data.get('市值_億')
        if market_cap is not None and market_cap <= 0:
            result['warnings'].append(f"市值異常: {market_cap}")

        return result

    @classmethod
    def validate_financial_table(cls, data: dict, required_fields: list, table_name: str) -> dict:
        """
        驗證財務報表數據

        Args:
            data: 包含 'quarters' 和 'data' 的字典
            required_fields: 必要欄位列表
            table_name: 表格名稱 (用於日誌)

        Returns:
            dict: {'valid': bool, 'missing': list, 'warnings': list, 'quarter_count': int}
        """
        result = {'valid': True, 'missing': [], 'warnings': [], 'quarter_count': 0}

        quarters = data.get('quarters', [])
        table_data = data.get('data', {})

        result['quarter_count'] = len(quarters)

        # 檢查季度數量
        if len(quarters) < cls.MIN_QUARTERS_FOR_TTM:
            result['warnings'].append(
                f"{table_name}: 季度數不足 ({len(quarters)} < {cls.MIN_QUARTERS_FOR_TTM})"
            )

        # 檢查必要欄位
        for field in required_fields:
            if field not in table_data:
                result['missing'].append(field)
                result['valid'] = False
            else:
                # 檢查是否有數據
                values = table_data[field]
                non_null_count = sum(1 for v in values if v is not None)
                if non_null_count == 0:
                    result['warnings'].append(f"{table_name}.{field}: 全部為空值")
                elif non_null_count < len(quarters) * 0.5:
                    result['warnings'].append(
                        f"{table_name}.{field}: 空值過多 ({len(quarters) - non_null_count}/{len(quarters)})"
                    )

        return result

    @classmethod
    def validate_all(cls, data: dict) -> dict:
        """
        驗證完整財務數據集

        Args:
            data: fetch_all_financial_data 的回傳值

        Returns:
            dict: 驗證結果摘要
        """
        results = {}

        # 驗證個股首頁
        results['stock_info'] = cls.validate_stock_info(data.get('stock_info', {}))

        # 驗證資產負債表
        results['balance_sheet'] = cls.validate_financial_table(
            data.get('balance_sheet', {}),
            cls.REQUIRED_BALANCE_SHEET,
            '資產負債表'
        )

        # 驗證損益表
        results['income_statement'] = cls.validate_financial_table(
            data.get('income_statement', {}),
            cls.REQUIRED_INCOME_STATEMENT,
            '損益表'
        )

        # 驗證現金流量表
        results['cashflow'] = cls.validate_financial_table(
            data.get('cashflow', {}),
            cls.REQUIRED_CASHFLOW,
            '現金流量表'
        )

        # 整體驗證結果
        all_valid = all(r['valid'] for r in results.values())
        all_missing = []
        all_warnings = []

        for section, r in results.items():
            for m in r.get('missing', []):
                all_missing.append(f"{section}.{m}")
            all_warnings.extend(r.get('warnings', []))

        # 輸出日誌
        if all_valid:
            logger.info("✅ 數據驗證通過")
        else:
            logger.warning(f"⚠️ 數據驗證不完全, 缺少欄位: {all_missing}")

        for w in all_warnings:
            logger.warning(f"  ⚠️ {w}")

        return {
            'valid': all_valid,
            'missing': all_missing,
            'warnings': all_warnings,
            'details': results,
        }
