from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from loguru import logger

from config import settings, PLANS
from database.crud import (
    get_stats,
    get_user,
    ban_user,
    set_user_plan,
    add_tokens,
    get_all_user_ids,
    create_broadcast,
    update_broadcast_count,
)

router = Router(name="admin")


def _is_admin(user_id: int) -> bool:
    return user_id in settings.admin_ids


class BroadcastFSM(StatesGroup):
    waiting_for_text = State()


# ---------------------------------------------------------------------------
# Guard
# ---------------------------------------------------------------------------

async def _admin_only(message: Message) -> bool:
    if not _is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещён.")
        return False
    return True


# ---------------------------------------------------------------------------
# /admin
# ---------------------------------------------------------------------------

@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    if not await _admin_only(message):
        return
    stats = await get_stats()
    text = (
        "🛠 <b>Панель администратора</b>\n\n"
        f"👥 Пользователей: <b>{stats['total_users']}</b>\n"
        f"🚫 Забанено: <b>{stats['banned_users']}</b>\n"
        f"📨 Запросов всего: <b>{stats['total_requests']}</b>\n"
        f"🪙 Токенов использовано: <b>{stats['total_tokens']:,}</b>\n"
        f"🟢 Активных сегодня: <b>{stats['active_today']}</b>\n"
    )
    await message.answer(text)


# ---------------------------------------------------------------------------
# /stats
# ---------------------------------------------------------------------------

@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    if not await _admin_only(message):
        return
    stats = await get_stats()
    models_text = "\n".join(
        f"  • {m['model']}: {m['count']}" for m in stats["top_models"]
    ) or "нет данных"
    plans_text = "\n".join(
        f"  • {p['plan']}: {p['count']}" for p in stats["plan_distribution"]
    ) or "нет данных"
    text = (
        "📊 <b>Статистика</b>\n\n"
        f"👥 Всего пользователей: <b>{stats['total_users']}</b>\n"
        f"🚫 Забанено: <b>{stats['banned_users']}</b>\n"
        f"🟢 Активных сегодня: <b>{stats['active_today']}</b>\n"
        f"📨 Запросов всего: <b>{stats['total_requests']}</b>\n"
        f"🪙 Токенов использовано: <b>{stats['total_tokens']:,}</b>\n\n"
        f"🤖 Топ моделей:\n{models_text}\n\n"
        f"📋 Тарифы:\n{plans_text}"
    )
    await message.answer(text)


# ---------------------------------------------------------------------------
# /ban and /unban
# ---------------------------------------------------------------------------

@router.message(Command("ban"))
async def cmd_ban(message: Message) -> None:
    if not await _admin_only(message):
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Использование: /ban {user_id}")
        return
    try:
        uid = int(parts[1])
    except ValueError:
        await message.answer("❗ user_id должен быть числом")
        return
    user = await get_user(uid)
    if not user:
        await message.answer(f"❗ Пользователь {uid} не найден")
        return
    await ban_user(uid, True)
    logger.info(f"Admin {message.from_user.id} banned user {uid}")
    await message.answer(f"🚫 Пользователь <code>{uid}</code> забанен.")


@router.message(Command("unban"))
async def cmd_unban(message: Message) -> None:
    if not await _admin_only(message):
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Использование: /unban {user_id}")
        return
    try:
        uid = int(parts[1])
    except ValueError:
        await message.answer("❗ user_id должен быть числом")
        return
    await ban_user(uid, False)
    logger.info(f"Admin {message.from_user.id} unbanned user {uid}")
    await message.answer(f"✅ Пользователь <code>{uid}</code> разбанен.")


# ---------------------------------------------------------------------------
# /addtokens
# ---------------------------------------------------------------------------

@router.message(Command("addtokens"))
async def cmd_add_tokens(message: Message) -> None:
    if not await _admin_only(message):
        return
    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("Использование: /addtokens {user_id} {amount}")
        return
    try:
        uid = int(parts[1])
        amount = int(parts[2])
    except ValueError:
        await message.answer("❗ Неверный формат")
        return
    await add_tokens(uid, amount)
    logger.info(f"Admin {message.from_user.id} added {amount} tokens to user {uid}")
    await message.answer(f"✅ Добавлено <b>{amount:,}</b> токенов пользователю <code>{uid}</code>.")


# ---------------------------------------------------------------------------
# /setplan
# ---------------------------------------------------------------------------

@router.message(Command("setplan"))
async def cmd_set_plan(message: Message) -> None:
    if not await _admin_only(message):
        return
    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("Использование: /setplan {user_id} {plan}")
        return
    try:
        uid = int(parts[1])
    except ValueError:
        await message.answer("❗ user_id должен быть числом")
        return
    plan = parts[2].lower()
    if plan not in PLANS:
        await message.answer(f"❗ Неизвестный тариф. Доступные: {', '.join(PLANS.keys())}")
        return
    await set_user_plan(uid, plan)
    logger.info(f"Admin {message.from_user.id} set plan {plan} for user {uid}")
    await message.answer(
        f"✅ Тариф пользователя <code>{uid}</code> изменён на <b>{plan}</b>."
    )


# ---------------------------------------------------------------------------
# /broadcast — FSM
# ---------------------------------------------------------------------------

@router.message(Command("broadcast"))
async def cmd_broadcast_start(message: Message, state: FSMContext) -> None:
    if not await _admin_only(message):
        return
    await state.set_state(BroadcastFSM.waiting_for_text)
    await message.answer(
        "📢 Введите текст для рассылки.\n"
        "Отправьте /cancel для отмены."
    )


@router.message(Command("cancel"), BroadcastFSM.waiting_for_text)
async def cmd_broadcast_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("❌ Рассылка отменена.")


@router.message(BroadcastFSM.waiting_for_text)
async def process_broadcast(message: Message, state: FSMContext, bot: Bot) -> None:
    if not _is_admin(message.from_user.id):
        await state.clear()
        return

    text = message.text or message.caption or ""
    if not text:
        await message.answer("❗ Сообщение не может быть пустым.")
        return

    await state.clear()
    broadcast = await create_broadcast(text)

    user_ids = await get_all_user_ids()
    sent = 0
    failed = 0
    status_msg = await message.answer(f"📤 Начинаю рассылку для {len(user_ids)} пользователей...")

    for uid in user_ids:
        try:
            await bot.send_message(uid, text)
            sent += 1
        except Exception as exc:
            logger.warning(f"Broadcast: failed to send to {uid}: {exc}")
            failed += 1

    await update_broadcast_count(broadcast.id, sent)
    logger.info(f"Broadcast {broadcast.id}: sent={sent}, failed={failed}")
    await status_msg.edit_text(
        f"✅ Рассылка завершена.\n"
        f"📤 Отправлено: <b>{sent}</b>\n"
        f"❌ Ошибок: <b>{failed}</b>"
    )
