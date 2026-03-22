from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from loguru import logger

from config import PLANS, UNCENSORED_MODELS
from database.crud import get_or_create_user, get_user, clear_history
from bot.keyboards.main_kb import main_keyboard

router = Router(name="start")


def _account_text(user) -> str:
    plan_info = PLANS.get(user.plan, PLANS["free"])
    model_name = UNCENSORED_MODELS.get(user.selected_model, {}).get("name", user.selected_model)
    tokens_pct = (
        int(user.tokens_left / user.tokens_total * 100) if user.tokens_total > 0 else 0
    )
    return (
        f"👤 <b>Ваш аккаунт</b>\n\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"👤 Имя: {user.first_name or '—'}\n"
        f"📋 Тариф: <b>{plan_info['name']}</b>\n"
        f"🤖 Модель: <b>{model_name}</b>\n"
        f"🌡 Температура: <b>{user.temperature}</b>\n"
        f"🪙 Токенов: <b>{user.tokens_left:,}</b> / {user.tokens_total:,} ({tokens_pct}%)\n"
        f"📨 Запросов всего: <b>{user.total_requests}</b>\n"
    )


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    user = await get_or_create_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
    )
    logger.info(f"User {user.id} started the bot")
    await message.answer(
        f"👋 Привет, <b>{message.from_user.first_name}</b>!\n\n"
        "Я — AI-бот на базе <b>Venice.ai</b> с uncensored нейросетями.\n"
        "Просто напиши мне что угодно, и я отвечу без цензуры.\n\n"
        "🔹 Тариф: <b>Free</b> (10 000 токенов)\n"
        "🔹 Модель: <b>Venice Uncensored</b>\n\n"
        "Используй кнопки ниже для управления:",
        reply_markup=main_keyboard(),
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "📖 <b>Список команд</b>\n\n"
        "/start — главное меню\n"
        "/help — эта справка\n"
        "/account — информация об аккаунте\n"
        "/clear — очистить историю диалога\n"
        "/setprompt — установить системный промпт\n\n"
        "<b>Команды администратора:</b>\n"
        "/admin — панель администратора\n"
        "/stats — статистика\n"
        "/ban [id] — забанить пользователя\n"
        "/unban [id] — разбанить\n"
        "/addtokens [id] [amount] — добавить токены\n"
        "/setplan [id] [plan] — изменить тариф\n"
        "/broadcast — рассылка сообщений",
    )


@router.message(Command("account"))
async def cmd_account(message: Message) -> None:
    user = await get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала напиши /start")
        return
    await message.answer(_account_text(user))


@router.message(Command("clear"))
async def cmd_clear(message: Message) -> None:
    await clear_history(message.from_user.id)
    await message.answer("🗑 История диалога очищена.")


@router.callback_query(F.data == "back_main")
async def cb_back_main(call: CallbackQuery) -> None:
    await call.message.edit_text(
        "🏠 Главное меню",
        reply_markup=main_keyboard(),
    )
    await call.answer()


@router.callback_query(F.data == "my_account")
async def cb_my_account(call: CallbackQuery) -> None:
    user = await get_user(call.from_user.id)
    if not user:
        await call.answer("Сначала напиши /start", show_alert=True)
        return
    await call.message.edit_text(_account_text(user), reply_markup=main_keyboard())
    await call.answer()


@router.callback_query(F.data == "clear_history")
async def cb_clear_history(call: CallbackQuery) -> None:
    await clear_history(call.from_user.id)
    await call.answer("🗑 История очищена!", show_alert=True)
