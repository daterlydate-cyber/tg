"""YooKassa integration for CIS payments (RUB)."""
from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from typing import Any, Dict, Optional

import yookassa
from yookassa import Configuration, Payment
from loguru import logger

from config import settings, PLAN_PRICES_RUB


def _configure() -> None:
    Configuration.account_id = settings.YOOKASSA_SHOP_ID
    Configuration.secret_key = settings.YOOKASSA_SECRET_KEY


def create_yookassa_payment(
    user_id: int,
    plan: str,
    return_url: str,
) -> Optional[Dict[str, Any]]:
    """Create a YooKassa payment and return {payment_id, confirmation_url}."""
    if not settings.YOOKASSA_SHOP_ID or not settings.YOOKASSA_SECRET_KEY:
        logger.warning("YooKassa credentials are not configured")
        return None

    price_rub = PLAN_PRICES_RUB.get(plan)
    if price_rub is None:
        logger.error(f"No RUB price for plan '{plan}'")
        return None

    _configure()
    idempotence_key = str(uuid.uuid4())
    try:
        payment = Payment.create(
            {
                "amount": {"value": str(price_rub), "currency": "RUB"},
                "confirmation": {"type": "redirect", "return_url": return_url},
                "description": f"Тариф {plan} для пользователя {user_id}",
                "metadata": {"user_id": str(user_id), "plan": plan},
                "capture": True,
            },
            idempotence_key,
        )
        return {
            "payment_id": payment.id,
            "confirmation_url": payment.confirmation.confirmation_url,
        }
    except Exception as exc:
        logger.error(f"YooKassa create payment error: {exc}")
        return None


def verify_yookassa_webhook(body: bytes, signature: str) -> Optional[Dict[str, Any]]:
    """Verify YooKassa webhook signature and return parsed event or None."""
    if not settings.YOOKASSA_SECRET_KEY:
        return None

    expected = hmac.new(
        settings.YOOKASSA_SECRET_KEY.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        logger.warning("YooKassa webhook signature mismatch")
        return None

    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return None
