from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import PLANS, PLAN_PRICE_LABELS


def plans_keyboard() -> InlineKeyboardMarkup:
    """Show paid plan options with prices."""
    builder = InlineKeyboardBuilder()
    paid_plans = [p for p in PLANS if p != "free"]
    for plan in paid_plans:
        info = PLANS[plan]
        labels = PLAN_PRICE_LABELS.get(plan, {})
        rub = labels.get("rub", "—")
        usd = labels.get("usd", "—")
        stars = labels.get("stars", "—")
        builder.row(
            InlineKeyboardButton(
                text=f"💎 {info['name']}  |  {rub} / {usd} / {stars}",
                callback_data=f"buy_plan:{plan}",
            )
        )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")
    )
    return builder.as_markup()


def payment_method_keyboard(plan: str) -> InlineKeyboardMarkup:
    """Choose payment method for a specific plan."""
    builder = InlineKeyboardBuilder()
    labels = PLAN_PRICE_LABELS.get(plan, {})
    builder.row(
        InlineKeyboardButton(
            text=f"🇷🇺 YooKassa  ({labels.get('rub', '—')})",
            callback_data=f"pay_yookassa:{plan}",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=f"💳 Stripe  ({labels.get('usd', '—')})",
            callback_data=f"pay_stripe:{plan}",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=f"⭐ Telegram Stars  ({labels.get('stars', '—')})",
            callback_data=f"pay_stars:{plan}",
        )
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="show_plans")
    )
    return builder.as_markup()
