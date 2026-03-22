"""Telegram Stars (native in-app payments) — works globally, no external PSP required."""
from __future__ import annotations

from typing import Any, Dict

from config import PLAN_PRICES_STARS


def build_stars_invoice(plan: str) -> Dict[str, Any]:
    """Return kwargs for Bot.send_invoice() using Telegram Stars.

    Telegram Stars use currency="XTR" with integer amounts (1 star = 1 unit).
    No provider_token is needed for XTR payments.
    """
    stars = PLAN_PRICES_STARS.get(plan, 100)
    return {
        "title": f"Тариф {plan.capitalize()}",
        "description": f"Активация тарифа {plan.capitalize()} в AI-боте Venice",
        "payload": f"stars:{plan}",
        "currency": "XTR",
        "prices": [{"label": f"Тариф {plan.capitalize()}", "amount": stars}],
        # No provider_token for Telegram Stars
    }
