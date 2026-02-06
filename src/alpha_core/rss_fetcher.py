"""
台股新聞情緒分析 - RSS 抓取模組
"""

import httpx
import feedparser
from trafilatura import fetch_url, extract
from datetime import datetime
from typing import Optional, List, Dict
import time
import re


def fetch_feed(feed_url: str, timeout: int = 15) -> list:
    """抓取 RSS Feed"""
    try:
        # 嘗試使用 httpx
        resp = httpx.get(feed_url, timeout=timeout, follow_redirects=True)
        feed = feedparser.parse(resp.text)
        return feed.entries
    except Exception as e:
        print(f"⚠️ RSS Fetch Error ({feed_url}): {e}")
        # Fallback: 嘗試 curl_cffi (SSL bypass)
        try:
            from curl_cffi import requests as curl_requests
            resp = curl_requests.get(feed_url, timeout=timeout, impersonate="chrome", verify=False)
            feed = feedparser.parse(resp.text)
            return feed.entries
        except Exception as e2:
            print(f"❌ RSS Fetch Failed: {e2}")
            return []


def parse_publish_time(entry) -> str:
    """解析發布時間"""
    if hasattr(entry, 'published_parsed') and entry.published_parsed:
        return datetime(*entry.published_parsed[:6]).isoformat()
    elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
        return datetime(*entry.updated_parsed[:6]).isoformat()
    else:
        return datetime.now().isoformat()


def extract_full_content(url: str, max_retries: int = 3) -> Optional[str]:
    """提取全文內容"""
    for attempt in range(max_retries):
        try:
            downloaded = fetch_url(url)
            if downloaded:
                content = extract(downloaded, include_comments=False, include_tables=False)
                if content and len(content) > 100:
                    return content
            return None
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                print(f"⚠️ Content Extract Failed ({url}): {e}")
                return None
    return None


def clean_text(text: str) -> str:
    """清理文字"""
    if not text:
        return ""
    # 移除多餘空白
    text = re.sub(r'\s+', ' ', text)
    # 移除常見的網站雜訊
    text = re.sub(r'(延伸閱讀|相關新聞|推薦閱讀|更多內容).*$', '', text, flags=re.IGNORECASE)
    return text.strip()


def fetch_all_feeds(feed_list: List[tuple]) -> List[Dict]:
    """抓取所有 RSS 來源的新聞"""
    all_news = []
    
    for source_name, feed_url in feed_list:
        print(f"📡 Fetching: {source_name}...")
        entries = fetch_feed(feed_url)
        
        for entry in entries:
            url = entry.get('link', '')
            if not url:
                continue
            
            title = entry.get('title', '').strip()
            publish_time = parse_publish_time(entry)
            
            # 取得全文
            full_content = extract_full_content(url)
            if not full_content:
                # 使用 RSS summary 作為備用
                full_content = entry.get('summary', entry.get('description', ''))
            
            full_content = clean_text(full_content)
            
            # 過濾太短的內容
            if len(full_content) < 50:
                continue
            
            all_news.append({
                'url': url,
                'title': title,
                'source': source_name,
                'publish_time': publish_time,
                'content': full_content
            })
        
        time.sleep(1)  # 禮貌性延遲
    
    print(f"✅ Total fetched: {len(all_news)} articles")
    return all_news
