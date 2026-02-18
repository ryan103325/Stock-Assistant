"""
自定義異常類別
"""


class FundamentalMasterError(Exception):
    """基本面評分系統基礎異常類別"""
    pass


class DataCollectionError(FundamentalMasterError):
    """資料採集異常"""
    pass


class DataValidationError(FundamentalMasterError):
    """資料驗證異常"""
    pass


class ScoringEngineError(FundamentalMasterError):
    """評分引擎異常"""
    pass


class AIAnalysisError(FundamentalMasterError):
    """AI 分析異常"""
    pass


class ReportGenerationError(FundamentalMasterError):
    """報告生成異常"""
    pass


class TelegramBotError(FundamentalMasterError):
    """Telegram Bot 異常"""
    pass
