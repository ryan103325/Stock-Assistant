# -*- coding: utf-8 -*-
"""
HTML 渲染工具模組
負責將 HTML 字串轉換為圖片，支援 Windows/Linux 環境自動切換
"""

import os
import sys
import imgkit
import platform
import shutil

class HTMLRenderer:
    def __init__(self):
        self.config = self._get_config()
        self.options = self._get_default_options()

    def _get_wkhtmltopdf_path(self):
        """取得 wkhtmltopdf 執行檔路徑"""
        # 1. 檢查系統 PATH
        path = shutil.which('wkhtmltoimage')
        if path:
            return path

        # 2. Windows 常見路徑
        if platform.system() == 'Windows':
            common_paths = [
                r'C:\Program Files\wkhtmltopdf\bin\wkhtmltoimage.exe',
                r'C:\Program Files (x86)\wkhtmltopdf\bin\wkhtmltoimage.exe',
            ]
            for p in common_paths:
                if os.path.exists(p):
                    return p
        
        # 3. Linux (通常在 /usr/bin)
        if platform.system() == 'Linux':
            if os.path.exists('/usr/bin/wkhtmltoimage'):
                return '/usr/bin/wkhtmltoimage'
                
        return None

    def _get_config(self):
        """設定 imgkit config"""
        path = self._get_wkhtmltopdf_path()
        if path:
            print(f"✅ 偵測到 wkhtmltoimage: {path}")
            return imgkit.config(wkhtmltoimage=path)
        else:
            print("⚠️ 未偵測到 wkhtmltoimage，將嘗試使用系統預設值 (可能失敗)")
            return None

    def _get_default_options(self):
        """預設轉換選項"""
        return {
            'format': 'png',
            'encoding': 'UTF-8',
            'quality': 100,
            'enable-local-file-access': None,
            'quiet': '',
            # 針對大尺寸報表優化
            'zoom': 2.0,            # 提高解析度
            'disable-smart-width': '',
        }

    def render(self, html_content, output_path, options=None, css_file=None):
        """
        渲染 HTML 為圖片
        
        Args:
            html_content (str): HTML 完整內容
            output_path (str): 輸出圖片路徑
            options (dict): 覆蓋預設選項
            css_file (str): 額外的 CSS 檔案路徑
        """
        opts = self.options.copy()
        if options:
            opts.update(options)

        try:
            imgkit.from_string(
                html_content, 
                output_path, 
                options=opts, 
                config=self.config,
                css=css_file
            )
            return True
        except Exception as e:
            print(f"❌ 圖片生成失敗: {e}")
            # 如果是 Windows 且找不到路徑，給出具體建議
            if platform.system() == 'Windows' and not self._get_wkhtmltopdf_path():
                print("💡 請安裝 wkhtmltopdf: https://wkhtmltopdf.org/downloads.html")
            return False

# 共用的 CSS 風格 (深色模式)
COMMON_STYLE = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;700&family=Roboto:wght@400;700&display=swap');
    
    body {
        font-family: 'Roboto', 'Noto Sans TC', sans-serif;
        background-color: #1a1a2e;
        color: #eaeaea;
        margin: 0;
        padding: 20px;
    }
    
    .card {
        background-color: #16213e;
        border-radius: 15px;
        padding: 25px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
        margin-bottom: 20px;
    }
    
    .header {
        border-bottom: 2px solid #2d3a5a;
        padding-bottom: 15px;
        margin-bottom: 20px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    
    .title {
        font-size: 28px;
        font-weight: 700;
        color: #fff;
    }
    
    .subtitle {
        font-size: 16px;
        color: #8892a0;
    }
    
    .tag {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 14px;
        font-weight: bold;
        margin-left: 8px;
    }
    
    .tag-red { background-color: #e94560; color: #fff; }
    .tag-green { background-color: #00d9a0; color: #000; }
    .tag-yellow { background-color: #ffc107; color: #000; }
    .tag-blue { background-color: #4ecca3; color: #000; }
    
    table {
        width: 100%;
        border-collapse: collapse;
        margin-top: 10px;
    }
    
    th {
        text-align: left;
        color: #8892a0;
        padding: 10px 5px;
        border-bottom: 1px solid #2d3a5a;
        font-size: 14px;
    }
    
    td {
        padding: 12px 5px;
        border-bottom: 1px solid #232d4b;
        font-size: 16px;
    }
    
    .up { color: #ff6b6b; }     /* 台股紅漲 */
    .down { color: #00d9a0; }   /* 台股綠跌 */
    .neutral { color: #eaeaea; }
    
    .highlight {
        font-weight: 700;
        color: #ffd700;
    }
    
    .footer {
        margin-top: 20px;
        text-align: right;
        font-size: 12px;
        color: #555;
    }
</style>
"""
