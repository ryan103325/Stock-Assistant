# -*- coding: utf-8 -*-
"""
族群資金動能策略 V2.0 - 圖片生成模組
使用 HTML + CSS + imgkit 生成美觀的圖片報表
"""

import os
import imgkit
from datetime import datetime

# 支援直接執行和模組導入
try:
    from .html_templates import generate_html
except ImportError:
    from html_templates import generate_html


def get_wkhtmltopdf_path():
    """
    獲取 wkhtmltopdf 執行檔路徑
    
    Returns:
        str: wkhtmltopdf 路徑，未找到則返回 None
    """
    # Windows 常見安裝路徑
    common_paths = [
        r'C:\Program Files\wkhtmltopdf\bin\wkhtmltoimage.exe',
        r'C:\Program Files (x86)\wkhtmltopdf\bin\wkhtmltoimage.exe',
        r'D:\Program Files\wkhtmltopdf\bin\wkhtmltoimage.exe',
    ]
    
    for path in common_paths:
        if os.path.exists(path):
            return path
    
    # 嘗試從 PATH 環境變數找
    import shutil
    wkhtmltoimage = shutil.which('wkhtmltoimage')
    if wkhtmltoimage:
        return wkhtmltoimage
    
    return None


def render_to_image(html_content: str, output_path: str, config: dict = None) -> bool:
    """
    將 HTML 內容渲染成 PNG 圖片
    
    Args:
        html_content: HTML 字串
        output_path: 輸出圖片路徑
        config: 可選配置
    
    Returns:
        bool: 成功返回 True，失敗返回 False
    """
    # 預設配置（優化檔案大小，符合 Telegram 10MB 限制）
    default_options = {
        'format': 'png',
        'width': 800,        # 縮小寬度
        'quality': 80,       # 降低品質（減少檔案大小）
        'encoding': 'UTF-8',
        'enable-local-file-access': None,
        'quiet': '',
    }
    
    if config:
        default_options.update(config)
    
    # 檢查 wkhtmltopdf 路徑
    wkhtmltoimage_path = get_wkhtmltopdf_path()
    
    imgkit_config = None
    if wkhtmltoimage_path:
        imgkit_config = imgkit.config(wkhtmltoimage=wkhtmltoimage_path)
    
    try:
        if imgkit_config:
            imgkit.from_string(html_content, output_path, options=default_options, config=imgkit_config)
        else:
            imgkit.from_string(html_content, output_path, options=default_options)
        return True
    except OSError as e:
        print(f"❌ wkhtmltopdf 可能未安裝或未加入 PATH")
        print(f"   請至 https://wkhtmltopdf.org/downloads.html 下載安裝")
        print(f"   錯誤詳情: {e}")
        return False
    except Exception as e:
        print(f"❌ 圖片渲染失敗: {e}")
        return False


def generate_image_report(
    filtered_sectors: list,
    date_str: str,
    output_dir: str = None,
    config: dict = None
) -> str:
    """
    主入口函數：生成族群動能圖片報表
    
    Args:
        filtered_sectors: 篩選後的族群資料列表
        date_str: 報表日期
        output_dir: 輸出目錄（預設為 reports/）
        config: 可選配置
    
    Returns:
        str: 成功返回圖片路徑，失敗返回 None
    """
    # 設定輸出目錄
    if output_dir is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(script_dir)
        output_dir = os.path.join(parent_dir, 'reports')
    
    # 確保目錄存在
    os.makedirs(output_dir, exist_ok=True)
    
    # 準備報表資料
    report_data = {
        'date': date_str,
        'sectors': filtered_sectors[:5],  # 只取 Top 5
        'summary': {
            'total_passed': len(filtered_sectors),
            'mode_counts': {}
        }
    }
    
    # 統計模式分布
    for sector in filtered_sectors:
        mode = sector.get('score', {}).get('mode', '其他')
        report_data['summary']['mode_counts'][mode] = \
            report_data['summary']['mode_counts'].get(mode, 0) + 1
    
    # 生成 HTML
    try:
        html_content = generate_html(report_data)
    except Exception as e:
        print(f"❌ HTML 生成失敗: {e}")
        return None
    
    # 生成輸出檔名
    date_clean = date_str.replace('/', '-').replace('.', '-')
    timestamp = datetime.now().strftime('%H%M%S')
    output_filename = f"sector_report_{date_clean}_{timestamp}.png"
    output_path = os.path.join(output_dir, output_filename)
    
    # 渲染成圖片
    if render_to_image(html_content, output_path, config):
        # 檢查檔案大小，如果超過 9MB 則壓縮
        file_size = os.path.getsize(output_path)
        max_size = 9 * 1024 * 1024  # 9MB
        
        if file_size > max_size:
            print(f"⚠️ 圖片過大 ({file_size/1024/1024:.1f}MB)，正在壓縮...")
            try:
                from PIL import Image
                img = Image.open(output_path)
                
                # 縮小尺寸
                width, height = img.size
                new_width = int(width * 0.7)
                new_height = int(height * 0.7)
                img = img.resize((new_width, new_height), Image.LANCZOS)
                
                # 轉換為 JPEG 格式（更小）
                jpg_path = output_path.replace('.png', '.jpg')
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                img.save(jpg_path, 'JPEG', quality=85, optimize=True)
                
                # 刪除原始 PNG
                os.remove(output_path)
                output_path = jpg_path
                
                new_size = os.path.getsize(output_path)
                print(f"✅ 壓縮完成: {new_size/1024/1024:.1f}MB")
            except Exception as e:
                print(f"⚠️ 壓縮失敗: {e}")
        
        print(f"✅ 圖片報告已生成: {output_path}")
        return output_path
    else:
        return None


# 測試用
if __name__ == '__main__':
    # 測試資料
    test_sectors = [
        {
            'metrics': {
                'sector_name': 'AI伺服器',
                'total_stocks': 12,
                'active_stocks': 8,
                'up_ratio': 0.875,
                'median_change': 2.3,
                'avg_volume_ratio': 1.45,
                'fund_flow': 12500.0,
                'margin_change': 350,
                'short_change': -80,
                'member_stocks': [
                    {'code': '3711', 'name': '日月光', 'change': 6.5, 'volume_ratio': 2.1},
                    {'code': '2330', 'name': '台積電', 'change': 3.2, 'volume_ratio': 1.8},
                    {'code': '6770', 'name': '力積電', 'change': 2.8, 'volume_ratio': 1.5},
                ]
            },
            'score': {
                'total_score': 86,
                'mode': '主流強勢型',
                'signals': ['族群同步', '資金集中', '融資進場']
            }
        },
        {
            'metrics': {
                'sector_name': '電動車',
                'total_stocks': 15,
                'active_stocks': 6,
                'up_ratio': 0.833,
                'median_change': 1.8,
                'avg_volume_ratio': 1.25,
                'fund_flow': 5000.0,
                'margin_change': 200,
                'short_change': 50,
                'member_stocks': [
                    {'code': '2308', 'name': '台達電', 'change': 4.2, 'volume_ratio': 1.6},
                    {'code': '1590', 'name': '亞德客', 'change': 2.1, 'volume_ratio': 1.3},
                ]
            },
            'score': {
                'total_score': 68,
                'mode': '同步上漲型',
                'signals': ['資金集中', '融資進場']
            }
        },
    ]
    
    result = generate_image_report(test_sectors, '2026-01-27')
    if result:
        print(f"測試成功: {result}")
    else:
        print("測試失敗")
