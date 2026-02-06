"""
台股新聞情緒分析 - LLM Client
"""

import os
import asyncio
import json
import re
from typing import Any, Optional
import google.generativeai as genai

from .config import GOOGLE_API_KEY, WORKER_MODEL_NAME, REFLECTOR_MODEL_NAME


class GeminiClient:
    def __init__(self, model_name: str = WORKER_MODEL_NAME):
        self.model_name = model_name
        genai.configure(api_key=GOOGLE_API_KEY)
        self.model = genai.GenerativeModel(model_name)
    
    async def generate(self, system_prompt: str, user_prompt: str, max_retries: int = 5) -> Optional[Any]:
        """生成回應 (含重試機制)"""
        
        full_prompt = f"{system_prompt}\n\n---\n\n{user_prompt}"
        
        for attempt in range(max_retries):
            try:
                response = await asyncio.to_thread(
                    self.model.generate_content,
                    full_prompt,
                    generation_config={
                        "temperature": 0.2,
                        "response_mime_type": "application/json"
                    }
                )
                
                if response.text:
                    return self._parse_json(response.text)
                else:
                    print("⚠️ Empty response from LLM")
                    return None
                    
            except Exception as e:
                error_str = str(e)
                
                # 處理 Rate Limit
                if "429" in error_str or "quota" in error_str.lower():
                    # 嘗試解析等待時間
                    wait_match = re.search(r'retry.*?(\d+)', error_str)
                    wait_time = float(wait_match.group(1)) + 1 if wait_match else (5 * (2 ** attempt))
                    print(f"⏳ Rate limited. Waiting {wait_time:.0f}s... (attempt {attempt+1}/{max_retries})")
                    await asyncio.sleep(wait_time)
                else:
                    print(f"❌ LLM Error: {e}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2)
                    else:
                        raise
        
        return None
    
    def _parse_json(self, text: str) -> Any:
        """解析 JSON 回應"""
        # 移除可能的 markdown code block
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r'^```\w*\n?', '', text)
            text = re.sub(r'\n?```$', '', text)
        
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            print(f"⚠️ JSON Parse Error: {e}")
            print(f"Raw text: {text[:500]}...")
            return None


# 便捷函數
def get_worker_client() -> GeminiClient:
    return GeminiClient(WORKER_MODEL_NAME)

def get_reflector_client() -> GeminiClient:
    return GeminiClient(REFLECTOR_MODEL_NAME)
