"""
Playwright 圖片生成模組
將 HTML 報告轉換為圖片, 用於 Telegram 發送
"""
import asyncio
from pathlib import Path
from datetime import datetime

from fundamental_master.utils.config import Config
from fundamental_master.utils.logger import setup_logger
from fundamental_master.utils.exceptions import ReportGenerationError

logger = setup_logger('image_generator')


async def _html_to_image_async(html_content: str, output_path: str, width: int = 1200) -> str:
    """
    異步將 HTML 內容轉為圖片

    Args:
        html_content: HTML 字串
        output_path: 輸出圖片路徑
        width: 圖片寬度 (px)

    Returns:
        str: 輸出圖片的完整路徑
    """
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={'width': width, 'height': 800})

        await page.set_content(html_content, wait_until='networkidle')

        # 等待 fonts 載入
        await page.wait_for_timeout(1000)

        # 取得實際內容高度
        content_height = await page.evaluate('document.body.scrollHeight')
        await page.set_viewport_size({'width': width, 'height': content_height + 40})

        # 截圖
        await page.screenshot(
            path=output_path,
            full_page=True,
            type='png',
        )

        await browser.close()

    logger.info(f"✅ 圖片已生成: {output_path}")
    return output_path


def html_to_image(html_content: str, stock_id: str = 'report') -> str:
    """
    將 HTML 內容轉為圖片 (同步介面)

    Args:
        html_content: HTML 字串
        stock_id: 股票代號 (用於檔名)

    Returns:
        str: 輸出圖片的完整路徑
    """
    logger.info(f"🖼️ 開始生成報告圖片: {stock_id}")

    # 確保輸出目錄存在
    output_dir = Config.REPORTS_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    # 產生檔名
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'fundamental_{stock_id}_{timestamp}.png'
    output_path = str(output_dir / filename)

    try:
        # 運行異步函數
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            _html_to_image_async(html_content, output_path, Config.REPORT_IMAGE_WIDTH)
        )
        loop.close()
        return result

    except Exception as e:
        logger.error(f"❌ 圖片生成失敗: {e}")
        raise ReportGenerationError(f"圖片生成失敗: {e}")
