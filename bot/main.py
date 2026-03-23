import asyncio
import sys

from loguru import logger
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import settings
from database.db import engine, Base
from bot.handlers import start, chat, settings as settings_handler, admin
from bot.handlers import payment as payment_handler
from bot.middlewares.auth import AuthMiddleware


async def on_startup(bot: Bot) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables ensured")
    me = await bot.get_me()
    logger.info(f"Bot started: @{me.username}")


async def main() -> None:
    logger.remove()
    logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level} | {message}")
    logger.add("logs/bot.log", rotation="10 MB", retention="7 days", level="DEBUG")

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher(storage=MemoryStorage())

    # Middlewares
    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(AuthMiddleware())

    # Routers
    dp.include_router(start.router)
    dp.include_router(settings_handler.router)
    dp.include_router(admin.router)
    dp.include_router(payment_handler.router)
    dp.include_router(chat.router)  # catch-all last

    await on_startup(bot)
    logger.info("Starting polling...")

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()
        logger.info("Bot stopped")


if __name__ == "__main__":
    import os
    os.makedirs("logs", exist_ok=True)
    asyncio.run(main())
