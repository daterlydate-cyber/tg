from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from loguru import logger

from config import PLANS, UNCENSORED_MODELS
from database.crud import (
    get_user,
    update_user_model,
    update_user_temperature,
    update_user_system_prompt,
)
from bot.keyboards.models_kb import models_keyboard
from bot.keyboards.settings_kb import settings_keyboard, temperature_keyboard
from bot.keyboards.main_kb import main_keyboard

router = Router(name="settings")


class PromptFSM(StatesGroup):
    waiting_for_prompt = State()


# ---------------------------------------------------------------------------
# Settings menu
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "settings")
async def cb_settings(call: CallbackQuery) -> None:
    user = await get_user(call.from_user.id)
    if not user:
        await call.answer("Сначала напиши /start", show_alert=True)
        return
    model_name = UNCENSORED_MODELS.get(user.selected_model, {}).get("name", user.selected_model)
    await call.message.edit_text(
        f"⚙️ <b>Настройки</b>\n\n"
        f"🤖 Модель: <b>{model_name}</b>\n"
        f"🌡 Температура: <b>{user.temperature}</b>\n"
        f"📝 Системный промпт: {'задан' if user.system_prompt else 'не задан'}\n",
        reply_markup=settings_keyboard(),
    )
    await call.answer()


# ---------------------------------------------------------------------------
# Model selection
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "select_model")
async def cb_select_model(call: CallbackQuery) -> None:
    user = await get_user(call.from_user.id)
    if not user:
        await call.answer("Сначала напиши /start", show_alert=True)
        return
    allowed = PLANS.get(user.plan, PLANS["free"])["allowed_models"]
    await call.message.edit_text(
        "🤖 <b>Выберите модель</b>\n\n"
        "🔒 — недоступна на вашем тарифе\n"
        "✅ — текущая модель",
        reply_markup=models_keyboard(user.selected_model, allowed),
    )
    await call.answer()


@router.callback_query(F.data.startswith("model:"))
async def cb_set_model(call: CallbackQuery) -> None:
    model_id = call.data.split(":", 1)[1]
    user = await get_user(call.from_user.id)
    if not user:
        await call.answer("Сначала напиши /start", show_alert=True)
        return

    allowed = PLANS.get(user.plan, PLANS["free"])["allowed_models"]
    if allowed is not None and model_id not in allowed:
        await call.answer("🔒 Эта модель недоступна на вашем тарифе", show_alert=True)
        return

    if model_id not in UNCENSORED_MODELS:
        await call.answer("Неизвестная модель", show_alert=True)
        return

    await update_user_model(call.from_user.id, model_id)
    model_name = UNCENSORED_MODELS[model_id]["name"]
    logger.info(f"User {call.from_user.id} changed model to {model_id}")
    await call.answer(f"✅ Модель изменена: {model_name}", show_alert=True)
    await call.message.edit_text("🏠 Главное меню", reply_markup=main_keyboard())


# ---------------------------------------------------------------------------
# Temperature
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "set_temperature")
async def cb_temperature_menu(call: CallbackQuery) -> None:
    user = await get_user(call.from_user.id)
    current = user.temperature if user else 0.7
    await call.message.edit_text(
        f"🌡 <b>Выберите температуру</b>\n\n"
        f"Текущее значение: <b>{current}</b>\n\n"
        "Чем выше — тем креативнее (и случайнее) ответы.",
        reply_markup=temperature_keyboard(current),
    )
    await call.answer()


@router.callback_query(F.data.startswith("temperature:"))
async def cb_set_temperature(call: CallbackQuery) -> None:
    try:
        temp = float(call.data.split(":", 1)[1])
    except ValueError:
        await call.answer("Неверное значение", show_alert=True)
        return
    await update_user_temperature(call.from_user.id, temp)
    logger.info(f"User {call.from_user.id} set temperature to {temp}")
    await call.answer(f"✅ Температура установлена: {temp}", show_alert=True)
    await cb_settings(call)


# ---------------------------------------------------------------------------
# System prompt FSM
# ---------------------------------------------------------------------------

@router.message(Command("setprompt"))
async def cmd_setprompt(message: Message, state: FSMContext) -> None:
    await state.set_state(PromptFSM.waiting_for_prompt)
    await message.answer(
        "📝 Введите системный промпт (инструкцию для AI).\n"
        "Отправьте /cancel для отмены."
    )


@router.message(Command("cancel"), PromptFSM.waiting_for_prompt)
async def cmd_cancel_prompt(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("❌ Отменено.", reply_markup=main_keyboard())


@router.message(PromptFSM.waiting_for_prompt)
async def process_system_prompt(message: Message, state: FSMContext) -> None:
    prompt = message.text.strip()
    if len(prompt) > 2000:
        await message.answer("❗ Промпт слишком длинный (максимум 2000 символов).")
        return
    await update_user_system_prompt(message.from_user.id, prompt)
    await state.clear()
    logger.info(f"User {message.from_user.id} set system prompt")
    await message.answer("✅ Системный промпт установлен.", reply_markup=main_keyboard())


@router.callback_query(F.data == "reset_prompt")
async def cb_reset_prompt(call: CallbackQuery) -> None:
    await update_user_system_prompt(call.from_user.id, None)
    await call.answer("✅ Системный промпт сброшен", show_alert=True)
    await cb_settings(call)


@router.callback_query(F.data == "set_system_prompt")
async def cb_set_system_prompt(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(PromptFSM.waiting_for_prompt)
    await call.message.answer(
        "📝 Введите системный промпт (инструкцию для AI).\n"
        "Отправьте /cancel для отмены."
    )
    await call.answer()
