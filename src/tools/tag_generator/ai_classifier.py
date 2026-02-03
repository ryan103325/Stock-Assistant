"""
AI 輔助標籤分類模組
使用 OpenAI API 進行標籤分類
"""

import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

# API 設定
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")  # 預設用便宜的模型

# 可用的族群類別
AVAILABLE_GROUPS = [
    "AI", "記憶體", "被動元件", "PCB", "IC設計", "IC代工", "封測",
    "半導體設備", "光通訊", "電動車", "網通", "面板", "航運", "金融",
    "蘋果供應鏈", "電源供應器", "連接器", "散熱", "伺服器",
    "食品", "水泥", "塑膠", "紡織", "鋼鐵", "建材", "機械",
    "營建", "化學", "生技醫療", "電子通路", "運動休閒",
    "電信服務", "百貨零售", "觀光旅遊", "電機電纜", "橡膠輪胎", "造紙"
]


def _call_openai(prompt: str) -> str:
    """呼叫 OpenAI API"""
    if not OPENAI_API_KEY:
        raise Exception("未設定 OPENAI_API_KEY")
    
    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": OPENAI_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 50
        },
        timeout=30
    )
    
    if response.status_code == 200:
        result = response.json()
        return result['choices'][0]['message']['content'].strip()
    else:
        raise Exception(f"API 錯誤 ({response.status_code}): {response.text[:100]}")


def classify_tag_with_ai(tag: str, max_retries: int = 2) -> str:
    """
    使用 OpenAI API 自動分類標籤
    
    Args:
        tag: 要分類的標籤名稱
        max_retries: 最大重試次數
        
    Returns:
        分類後的族群名稱
    """
    prompt = f"""你是台股產業分類專家。請將以下標籤分類到最適合的族群。

標籤：{tag}

可選族群：{', '.join(AVAILABLE_GROUPS)}

規則：
1. 只回傳族群名稱，不要其他文字
2. 如果是科技相關但無法精確歸類，選擇最接近的
3. 如果是傳統產業但無法精確歸類，選擇最接近的
4. 只能選擇上面列出的族群名稱

回答："""

    for attempt in range(max_retries):
        try:
            answer = _call_openai(prompt)
            
            # 驗證回答是否在可選族群中
            if answer in AVAILABLE_GROUPS:
                return answer
            
            # 嘗試模糊匹配
            for group in AVAILABLE_GROUPS:
                if group in answer or answer in group:
                    return group
            
            print(f"⚠️ AI 回傳非預期結果: {answer}，使用預設分類")
                
        except requests.exceptions.ConnectionError:
            print(f"⚠️ 無法連接 OpenAI API，請檢查網路")
            break
        except Exception as e:
            print(f"⚠️ AI 分類錯誤: {e}")
    
    return "傳產其他"  # 預設 fallback


def classify_tags_batch(tags: list, use_cache: bool = True) -> dict:
    """
    批次分類多個標籤
    
    Args:
        tags: 標籤列表
        use_cache: 是否使用快取避免重複呼叫
        
    Returns:
        dict: {標籤: 族群}
    """
    cache_file = os.path.join(os.path.dirname(__file__), "ai_tag_cache.json")
    
    # 載入快取
    cache = {}
    if use_cache and os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache = json.load(f)
        except:
            pass
    
    results = {}
    new_classifications = 0
    
    for tag in tags:
        if tag in cache:
            results[tag] = cache[tag]
        else:
            print(f"🤖 AI 分類: {tag}...", end=" ")
            group = classify_tag_with_ai(tag)
            results[tag] = group
            cache[tag] = group
            new_classifications += 1
            print(f"→ {group}")
    
    # 儲存快取
    if new_classifications > 0 and use_cache:
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)
            print(f"✅ 已儲存 {new_classifications} 筆新分類到快取")
            
            # 產生程式碼片段供手動整合到 GROUP_MAPPING
            _generate_code_snippet(cache)
        except Exception as e:
            print(f"⚠️ 快取儲存失敗: {e}")
    
    return results


def _generate_code_snippet(cache: dict):
    """產生可貼到 GROUP_MAPPING 的程式碼片段"""
    snippet_file = os.path.join(os.path.dirname(__file__), "ai_learned_tags.py")
    
    # 按族群分組
    group_tags = {}
    for tag, group in cache.items():
        if group not in group_tags:
            group_tags[group] = []
        group_tags[group].append(tag)
    
    # 產生程式碼
    lines = [
        '"""',
        'AI 學習到的標籤分類',
        '可手動整合到 GROUP_MAPPING 中的 AUTO_MATCH_KEYWORDS',
        f'產生時間: {__import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M")}',
        f'總計: {len(cache)} 個標籤',
        '"""',
        '',
        'AI_LEARNED_TAGS = {'
    ]
    
    for group, tags in sorted(group_tags.items()):
        tags_str = ', '.join([f'"{t}"' for t in sorted(tags)])
        lines.append(f'    "{group}": [{tags_str}],')
    
    lines.append('}')
    
    try:
        with open(snippet_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        print(f"📝 已產生程式碼片段: ai_learned_tags.py")
    except:
        pass


def get_ai_learned_tags() -> dict:
    """取得 AI 學習到的標籤對照表（從快取載入）"""
    cache_file = os.path.join(os.path.dirname(__file__), "ai_tag_cache.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {}


def test_connection():
    """測試 OpenAI API 連線"""
    print(f"🔌 測試 OpenAI API 連線...")
    print(f"   模型: {OPENAI_MODEL}")
    
    if not OPENAI_API_KEY:
        print("❌ 未設定 OPENAI_API_KEY")
        return False
    
    try:
        answer = _call_openai("回覆 OK")
        print(f"✅ OpenAI API 連線成功")
        return True
            
    except requests.exceptions.ConnectionError:
        print(f"❌ 無法連接 OpenAI API，請檢查網路")
        return False
    except Exception as e:
        print(f"❌ 連線錯誤: {e}")
        return False


if __name__ == "__main__":
    print(f"📡 使用 OpenAI API")
    print(f"   OPENAI_API_KEY: {'已設定' if OPENAI_API_KEY else '未設定'}")
    print(f"   模型: {OPENAI_MODEL}")
    print()
    
    if test_connection():
        # 測試分類
        test_tags = ["無人機", "元宇宙", "高爾夫球", "碳權", "3D列印"]
        print(f"\n🤖 測試 AI 分類...")
        results = classify_tags_batch(test_tags)
        print(f"\n📊 分類結果:")
        for tag, group in results.items():
            print(f"   {tag} → {group}")
