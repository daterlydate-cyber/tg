from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

TEMPERATURE_VALUES = [0.1, 0.3, 0.5, 0.7, 0.9, 1.0]


def settings_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🤖 Выбрать модель", callback_data="select_model"),
    )
    builder.row(
        InlineKeyboardButton(text="🌡 Температура", callback_data="set_temperature"),
    )
    builder.row(
        InlineKeyboardButton(text="📝 Системный промпт", callback_data="set_system_prompt"),
        InlineKeyboardButton(text="🗑 Сбросить промпт", callback_data="reset_prompt"),
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="back_main"),
    )
    return builder.as_markup()


def temperature_keyboard(current: float) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    buttons = []
    for val in TEMPERATURE_VALUES:
        label = f"✅ {val}" if abs(val - current) < 0.01 else str(val)
        buttons.append(InlineKeyboardButton(text=label, callback_data=f"temperature:{val}"))
    # 3 per row
    builder.row(*buttons[:3])
    builder.row(*buttons[3:])
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="settings"))
    return builder.as_markup()
