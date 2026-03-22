from typing import Any, Awaitable, Callable, Dict

import redis.asyncio as aioredis
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
from loguru import logger

from config import settings
from database.crud import get_user

RATE_LIMIT = 10  # max requests per minute
RATE_WINDOW = 60  # seconds


class AuthMiddleware(BaseMiddleware):
    def __init__(self) -> None:
        super().__init__()
        self._redis: aioredis.Redis | None = None

    def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        return self._redis

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # Determine user_id from the event
        if isinstance(event, (Message, CallbackQuery)):
            user = event.from_user
        else:
            return await handler(event, data)

        if user is None:
            return await handler(event, data)

        user_id = user.id

        # Check ban
        db_user = await get_user(user_id)
        if db_user and db_user.is_banned:
            logger.warning(f"Blocked banned user {user_id}")
            if isinstance(event, CallbackQuery):
                await event.answer("🚫 Вы заблокированы.", show_alert=True)
            return  # silently ignore

        # Rate limiting via Redis
        try:
            redis = self._get_redis()
            key = f"rate:{user_id}"
            count = await redis.incr(key)
            if count == 1:
                await redis.expire(key, RATE_WINDOW)
            if count > RATE_LIMIT:
                logger.warning(f"Rate limit hit for user {user_id} ({count} req/min)")
                if isinstance(event, Message):
                    await event.answer(
                        f"⏱ Слишком много запросов. Подождите немного (лимит: {RATE_LIMIT}/мин)."
                    )
                elif isinstance(event, CallbackQuery):
                    await event.answer("⏱ Слишком много запросов.", show_alert=True)
                return
        except Exception as exc:
            logger.error(f"Redis rate limit error: {exc}")
            # If Redis is unavailable, allow the request

        return await handler(event, data)
