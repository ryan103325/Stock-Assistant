"""
Telegram 圖片發送模組
將生成的報告圖片發送至 Telegram
"""
import asyncio
from pathlib import Path

from fundamental_master.utils.config import Config
from fundamental_master.utils.logger import setup_logger
from fundamental_master.utils.exceptions import TelegramBotError

logger = setup_logger('telegram_sender')


async def _send_image_async(image_path: str, caption: str = '') -> bool:
    """異步發送圖片至 Telegram"""
    import telegram

    bot = telegram.Bot(token=Config.TELEGRAM_TOKEN)
    chat_id = Config.TELEGRAM_CHAT_ID

    try:
        with open(image_path, 'rb') as photo:
            await bot.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption=caption[:1024],  # Telegram caption 限制
                parse_mode='HTML',
            )
        logger.info(f"✅ 圖片已發送至 Telegram: {Path(image_path).name}")
        return True

    except Exception as e:
        logger.error(f"❌ Telegram 發送失敗: {e}")
        raise TelegramBotError(f"Telegram 發送失敗: {e}")


async def _send_message_async(text: str) -> bool:
    """異步發送文字訊息至 Telegram"""
    import telegram

    bot = telegram.Bot(token=Config.TELEGRAM_TOKEN)
    chat_id = Config.TELEGRAM_CHAT_ID

    try:
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode='HTML',
        )
        return True
    except Exception as e:
        logger.error(f"❌ Telegram 訊息發送失敗: {e}")
        return False


def send_report_image(image_path: str, stock_id: str, stock_name: str = '') -> bool:
    """
    發送報告圖片至 Telegram (同步介面)

    Args:
        image_path: 圖片路徑
        stock_id: 股票代號
        stock_name: 股票名稱

    Returns:
        bool: 是否發送成功
    """
    caption = (
        f"📊 <b>{stock_id} {stock_name}</b> 基本面體檢報告\n\n"
        f"🤖 由基本面評分大師自動生成\n"
        f"⚠️ 僅供投資研究參考, 不構成投資建議"
    )

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(_send_image_async(image_path, caption))
        return result
    except Exception as e:
        logger.error(f"❌ 報告發送失敗: {e}")
        return False
    finally:
        loop.close()


def send_progress_message(text: str) -> bool:
    """發送進度訊息 (同步介面)"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_send_message_async(text))
    except Exception:
        return False
    finally:
        loop.close()
