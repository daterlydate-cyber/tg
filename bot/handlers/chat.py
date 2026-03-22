from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from loguru import logger

from config import PLANS, UNCENSORED_MODELS
from database.crud import (
    get_or_create_user,
    get_user,
    save_message,
    get_conversation_history,
    deduct_tokens,
)
from api.venice import chat_completion

router = Router(name="chat")

MAX_MESSAGE_LENGTH = 4000


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: words * 1.3.

    This is a heuristic approximation. Actual token usage from Venice.ai
    may differ. For a more accurate count, use a tokenizer library.
    """
    return max(1, int(len(text.split()) * 1.3))


def _split_message(text: str, chunk_size: int = MAX_MESSAGE_LENGTH) -> list[str]:
    if len(text) <= chunk_size:
        return [text]
    parts = []
    while text:
        parts.append(text[:chunk_size])
        text = text[chunk_size:]
    return parts


@router.message(F.text & ~F.text.startswith("/"))
async def handle_chat_message(message: Message) -> None:
    user_id = message.from_user.id
    user = await get_or_create_user(
        user_id,
        message.from_user.username,
        message.from_user.first_name,
    )

    # Check if user has tokens
    if user.plan != "unlimited" and user.tokens_left <= 0:
        await message.answer(
            "❌ <b>У вас закончились токены.</b>\n\n"
            "Обратитесь к администратору для пополнения."
        )
        return

    # Typing indicator
    status_msg = await message.answer("⏳ <i>Генерирую ответ...</i>")
    await message.bot.send_chat_action(message.chat.id, "typing")

    # Build history
    plan_info = PLANS.get(user.plan, PLANS["free"])
    history_limit = plan_info["history_messages"]
    history = await get_conversation_history(user_id, limit=history_limit)
    messages = [{"role": row.role, "content": row.content} for row in history]
    messages.append({"role": "user", "content": message.text})

    try:
        response_text = await chat_completion(
            model_id=user.selected_model,
            messages=messages,
            temperature=user.temperature,
            max_tokens=2048,
            system_prompt=user.system_prompt,
        )
    except RuntimeError as exc:
        logger.warning(f"Venice API error for user {user_id}: {exc}")
        await status_msg.edit_text(f"❌ Ошибка: {exc}")
        return
    except Exception as exc:
        logger.error(f"Unexpected error for user {user_id}: {exc}")
        await status_msg.edit_text("❌ Произошла непредвиденная ошибка. Попробуйте позже.")
        return

    # Calculate tokens used
    tokens_used = _estimate_tokens(message.text) + _estimate_tokens(response_text)

    # Save messages to DB
    await save_message(user_id, user.selected_model, "user", message.text, _estimate_tokens(message.text))
    await save_message(user_id, user.selected_model, "assistant", response_text, _estimate_tokens(response_text))

    # Deduct tokens
    await deduct_tokens(user_id, tokens_used)

    logger.info(f"User {user_id} | model={user.selected_model} | tokens={tokens_used}")

    # Delete "generating..." message
    await status_msg.delete()

    # Send response (split if needed)
    parts = _split_message(response_text)
    for part in parts:
        await message.answer(part)
