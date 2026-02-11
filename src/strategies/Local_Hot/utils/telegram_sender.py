# -*- coding: utf-8 -*-
"""
統一動能策略 - Telegram 發送器
"""

import os
import requests


def send_telegram_photo(photo_path, caption="", token=None, chat_id=None):
    """
    發送圖片至 Telegram
    
    Args:
        photo_path: 圖片檔案路徑
        caption: 圖片說明文字
        token: Telegram Bot Token（可選，預設從環境變數讀取）
        chat_id: Telegram Chat ID（可選，預設從環境變數讀取）
    
    Returns:
        bool: 成功返回 True，失敗返回 False
    """
    # 從環境變數讀取（GitHub Actions 兼容）
    if token is None:
        token = os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN", "")
    if chat_id is None:
        chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    
    if not token or not chat_id:
        print("⚠️ 未設定 TELEGRAM_BOT_TOKEN 或 TELEGRAM_CHAT_ID")
        print("   請在 .env 或 GitHub Secrets 中設定")
        return False
    
    if not os.path.exists(photo_path):
        print(f"❌ 圖片檔案不存在: {photo_path}")
        return False
    
    try:
        url = f"https://api.telegram.org/bot{token}/sendPhoto"
        with open(photo_path, 'rb') as photo:
            files = {'photo': photo}
            data = {'chat_id': chat_id, 'caption': caption}
            resp = requests.post(url, files=files, data=data, timeout=30)
        
        if resp.status_code == 200:
            print("✅ Telegram 圖片發送成功")
            return True
        else:
            print(f"❌ Telegram 圖片發送失敗: {resp.status_code}")
            try:
                print(f"   回應: {resp.json()}")
            except:
                print(f"   回應: {resp.text[:500]}")
            return False
    except Exception as e:
        print(f"❌ Telegram 發送錯誤: {e}")
        return False
