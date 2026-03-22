"""Payment handler: YooKassa (CIS/RUB), Stripe (EU/USA/USD), Telegram Stars."""
from __future__ import annotations

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    Message,
    PreCheckoutQuery,
    SuccessfulPayment,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from loguru import logger

from config import settings, PLANS, PLAN_PRICES_RUB, PLAN_PRICES_USD, PLAN_PRICES_STARS
from database.crud import (
    get_user,
    set_user_plan,
    create_payment,
    get_payment_by_external_id,
    update_payment_status,
    get_user_payments,
)
from bot.keyboards.payment_kb import plans_keyboard, payment_method_keyboard
from payments.yookassa_pay import create_yookassa_payment
from payments.stripe_pay import create_stripe_session
from payments.telegram_stars import build_stars_invoice

router = Router(name="payment")


# ---------------------------------------------------------------------------
# /buy — show available plans
# ---------------------------------------------------------------------------

@router.message(Command("buy"))
async def cmd_buy(message: Message) -> None:
    await message.answer(
        "💎 <b>Выбери тариф</b>\n\n"
        "📌 Цены указаны за разовую покупку токенов и доступа к моделям.\n"
        "• 🇷🇺 YooKassa — оплата в рублях (СНГ)\n"
        "• 💳 Stripe — оплата картой (Европа / США)\n"
        "• ⭐ Telegram Stars — встроенная оплата Telegram\n",
        reply_markup=plans_keyboard(),
    )


@router.callback_query(F.data == "show_plans")
async def cb_show_plans(call: CallbackQuery) -> None:
    await call.message.edit_text(
        "💎 <b>Выбери тариф</b>\n\n"
        "📌 Цены указаны за разовую покупку токенов и доступа к моделям.\n"
        "• 🇷🇺 YooKassa — оплата в рублях (СНГ)\n"
        "• 💳 Stripe — оплата картой (Европа / США)\n"
        "• ⭐ Telegram Stars — встроенная оплата Telegram\n",
        reply_markup=plans_keyboard(),
    )
    await call.answer()


@router.callback_query(F.data.startswith("buy_plan:"))
async def cb_buy_plan(call: CallbackQuery) -> None:
    plan = call.data.split(":")[1]
    if plan not in PLANS or plan == "free":
        await call.answer("❗ Неизвестный тариф", show_alert=True)
        return
    plan_info = PLANS[plan]
    await call.message.edit_text(
        f"💎 <b>{plan_info['name']}</b>\n\n"
        f"🪙 Токенов: <b>{plan_info['tokens']:,}</b>\n"
        f"📜 История: <b>{plan_info['history_messages']} сообщений</b>\n"
        f"🤖 Все модели: {'✅' if plan_info['allowed_models'] is None else '❌'}\n\n"
        "Выбери способ оплаты:",
        reply_markup=payment_method_keyboard(plan),
    )
    await call.answer()


# ---------------------------------------------------------------------------
# YooKassa
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("pay_yookassa:"))
async def cb_pay_yookassa(call: CallbackQuery) -> None:
    plan = call.data.split(":")[1]
    user_id = call.from_user.id

    result = create_yookassa_payment(
        user_id=user_id,
        plan=plan,
        return_url=settings.YOOKASSA_RETURN_URL,
    )
    if result is None:
        await call.answer(
            "⚠️ YooKassa временно недоступна. Попробуйте другой способ оплаты.",
            show_alert=True,
        )
        return

    await create_payment(
        user_id=user_id,
        plan=plan,
        provider="yookassa",
        amount=PLAN_PRICES_RUB.get(plan, 0),
        currency="RUB",
        external_id=result["payment_id"],
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить", url=result["confirmation_url"])],
            [InlineKeyboardButton(text="✅ Я оплатил", callback_data=f"check_yookassa:{result['payment_id']}")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data=f"buy_plan:{plan}")],
        ]
    )
    await call.message.edit_text(
        "🏦 <b>Оплата через YooKassa</b>\n\n"
        "1. Нажми «Оплатить» и заверши оплату на сайте YooKassa.\n"
        "2. После оплаты нажми «Я оплатил» — бот проверит статус.",
        reply_markup=kb,
    )
    await call.answer()


@router.callback_query(F.data.startswith("check_yookassa:"))
async def cb_check_yookassa(call: CallbackQuery) -> None:
    payment_id = call.data.split(":")[1]
    payment = await get_payment_by_external_id(payment_id)
    if not payment:
        await call.answer("❗ Платёж не найден", show_alert=True)
        return

    if payment.status == "succeeded":
        await call.answer("✅ Тариф уже активирован!", show_alert=True)
        return

    # Check YooKassa status via API
    try:
        import yookassa
        from yookassa import Configuration, Payment as YKPayment
        Configuration.account_id = settings.YOOKASSA_SHOP_ID
        Configuration.secret_key = settings.YOOKASSA_SECRET_KEY
        yk_payment = YKPayment.find_one(payment_id)
        status = yk_payment.status  # "pending" | "waiting_for_capture" | "succeeded" | "cancelled"
    except Exception as exc:
        logger.error(f"YooKassa status check error: {exc}")
        await call.answer("⚠️ Не удалось проверить статус. Попробуйте позже.", show_alert=True)
        return

    if status == "succeeded":
        await update_payment_status(payment.id, "succeeded")
        await set_user_plan(call.from_user.id, payment.plan)
        await call.message.edit_text(
            f"🎉 <b>Оплата подтверждена!</b>\n\nТариф <b>{payment.plan}</b> активирован."
        )
        logger.info(f"User {call.from_user.id} upgraded to plan {payment.plan} via YooKassa")
    elif status == "cancelled":
        await update_payment_status(payment.id, "cancelled")
        await call.answer("❌ Платёж отменён.", show_alert=True)
    else:
        await call.answer(
            "⏳ Платёж ещё не подтверждён. Попробуйте чуть позже.",
            show_alert=True,
        )


# ---------------------------------------------------------------------------
# Stripe
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("pay_stripe:"))
async def cb_pay_stripe(call: CallbackQuery) -> None:
    plan = call.data.split(":")[1]
    user_id = call.from_user.id

    result = create_stripe_session(
        user_id=user_id,
        plan=plan,
        success_url=settings.STRIPE_SUCCESS_URL,
        cancel_url=settings.STRIPE_CANCEL_URL,
    )
    if result is None:
        await call.answer(
            "⚠️ Stripe временно недоступен. Попробуйте другой способ оплаты.",
            show_alert=True,
        )
        return

    await create_payment(
        user_id=user_id,
        plan=plan,
        provider="stripe",
        amount=PLAN_PRICES_USD.get(plan, 0),
        currency="USD",
        external_id=result["session_id"],
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить картой", url=result["checkout_url"])],
            [InlineKeyboardButton(text="🔙 Назад", callback_data=f"buy_plan:{plan}")],
        ]
    )
    await call.message.edit_text(
        "💳 <b>Оплата через Stripe</b>\n\n"
        "Нажми «Оплатить картой» и заверши оплату.\n"
        "После успешной оплаты тариф будет активирован автоматически через webhook.",
        reply_markup=kb,
    )
    await call.answer()


# ---------------------------------------------------------------------------
# Telegram Stars
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("pay_stars:"))
async def cb_pay_stars(call: CallbackQuery, bot: Bot) -> None:
    plan = call.data.split(":")[1]
    invoice_kwargs = build_stars_invoice(plan)

    # Record pending payment before sending invoice
    await create_payment(
        user_id=call.from_user.id,
        plan=plan,
        provider="stars",
        amount=PLAN_PRICES_STARS.get(plan, 0),
        currency="XTR",
    )

    await bot.send_invoice(
        chat_id=call.from_user.id,
        **invoice_kwargs,
    )
    await call.answer()


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery) -> None:
    """Must answer within 10 seconds — always accept valid Stars invoices."""
    if query.invoice_payload.startswith("stars:"):
        await query.answer(ok=True)
    else:
        await query.answer(ok=False, error_message="Неизвестный платёж")


@router.message(F.successful_payment)
async def successful_payment_handler(message: Message) -> None:
    payment_data = message.successful_payment
    payload = payment_data.invoice_payload
    if not payload.startswith("stars:"):
        return
    plan = payload.split(":")[1]
    user_id = message.from_user.id
    charge_id = payment_data.provider_payment_charge_id

    # Mark most recent pending Stars payment as succeeded, using charge_id as external_id
    payments = await get_user_payments(user_id, limit=5)
    for p in payments:
        if p.provider == "stars" and p.plan == plan and p.status == "pending":
            await update_payment_status(p.id, "succeeded")
            # Store the Telegram charge_id for traceability (best-effort update)
            from sqlalchemy import update as sa_update
            from database.db import async_session_maker
            from database.models import Payment
            async with async_session_maker() as session:
                await session.execute(
                    sa_update(Payment).where(Payment.id == p.id).values(external_id=charge_id)
                )
                await session.commit()
            break

    await set_user_plan(user_id, plan)
    logger.info(f"User {user_id} upgraded to plan {plan} via Telegram Stars (charge {charge_id})")
    await message.answer(
        f"🌟 <b>Оплата через Telegram Stars подтверждена!</b>\n\n"
        f"Тариф <b>{plan}</b> активирован. Спасибо!"
    )


# ---------------------------------------------------------------------------
# /payments — payment history for the user
# ---------------------------------------------------------------------------

@router.message(Command("payments"))
async def cmd_payments(message: Message) -> None:
    payments = await get_user_payments(message.from_user.id, limit=10)
    if not payments:
        await message.answer("📄 У вас пока нет платежей.")
        return

    lines = ["📄 <b>История платежей</b>\n"]
    for p in payments:
        status_icon = {"succeeded": "✅", "pending": "⏳", "failed": "❌", "cancelled": "🚫"}.get(
            p.status, "❓"
        )
        created = p.created_at.strftime("%d.%m.%Y %H:%M") if p.created_at else "—"
        lines.append(
            f"{status_icon} <b>{p.plan}</b> — {p.provider} — "
            f"{p.amount} {p.currency} — {created}"
        )

    await message.answer("\n".join(lines))
