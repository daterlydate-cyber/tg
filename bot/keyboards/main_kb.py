from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🤖 Выбрать модель", callback_data="select_model"),
        InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings"),
    )
    builder.row(
        InlineKeyboardButton(text="📊 Мой аккаунт", callback_data="my_account"),
        InlineKeyboardButton(text="🗑 Очистить историю", callback_data="clear_history"),
    )
    builder.row(
        InlineKeyboardButton(text="💎 Купить тариф", callback_data="show_plans"),
    )
    return builder.as_markup()
