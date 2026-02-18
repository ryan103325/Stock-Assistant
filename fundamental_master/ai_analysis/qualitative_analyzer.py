"""
AI 質化分析引擎
整合 OpenAI GPT-4-mini 進行財務數據深度解讀
"""
import json
from typing import Optional

from openai import OpenAI

from fundamental_master.utils.config import Config
from fundamental_master.utils.logger import setup_logger
from fundamental_master.utils.exceptions import AIAnalysisError
from fundamental_master.ai_analysis.prompt_templates import SYSTEM_PROMPT, build_analysis_prompt

logger = setup_logger('qualitative_analyzer')


class QualitativeAnalyzer:
    """AI 質化分析器"""

    def __init__(self):
        if not Config.OPENAI_API_KEY:
            raise AIAnalysisError("OPENAI_API_KEY 未設定")

        self.client = OpenAI(api_key=Config.OPENAI_API_KEY)
        self.model = Config.OPENAI_MODEL
        logger.info(f"✅ OpenAI 客戶端初始化完成, 模型: {self.model}")

    def analyze(self, stock_data: dict) -> dict:
        """
        執行 AI 質化分析

        Args:
            stock_data: 包含所有評分結果與財務數據

        Returns:
            dict: AI 分析結果
        """
        stock_id = stock_data.get('stock_info', {}).get('股票代號', 'Unknown')
        logger.info(f"🤖 開始 AI 分析: {stock_id}")

        prompt = build_analysis_prompt(stock_data)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=Config.GPT_TEMPERATURE,
                max_tokens=Config.GPT_MAX_TOKENS,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content

            # 解析 JSON
            result = json.loads(content)

            # 記錄 Token 使用量
            usage = response.usage
            logger.info(
                f"✅ AI 分析完成 | "
                f"Tokens: {usage.total_tokens} "
                f"(prompt: {usage.prompt_tokens}, completion: {usage.completion_tokens})"
            )

            return result

        except json.JSONDecodeError as e:
            logger.error(f"❌ AI 回應 JSON 解析失敗: {e}")
            # 嘗試從回應中提取 JSON
            return _extract_json_from_text(content)

        except Exception as e:
            logger.error(f"❌ AI 分析失敗: {e}")
            raise AIAnalysisError(f"AI 分析失敗: {e}")


def _extract_json_from_text(text: str) -> dict:
    """從文字中嘗試提取 JSON"""
    import re
    json_match = re.search(r'\{[\s\S]*\}', text)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    # 返回預設結構
    return {
        'overall_score': None,
        'error': 'AI 回應格式異常',
        'raw_response': text[:500],
    }
