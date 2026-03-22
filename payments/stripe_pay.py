"""Stripe integration for Europe / USA payments (USD)."""
from __future__ import annotations

from typing import Any, Dict, Optional

import stripe
from loguru import logger

from config import settings, PLAN_PRICES_USD


def _configure() -> None:
    stripe.api_key = settings.STRIPE_SECRET_KEY


def create_stripe_session(
    user_id: int,
    plan: str,
    success_url: str,
    cancel_url: str,
) -> Optional[Dict[str, Any]]:
    """Create a Stripe Checkout Session and return {session_id, checkout_url}."""
    if not settings.STRIPE_SECRET_KEY:
        logger.warning("Stripe secret key is not configured")
        return None

    price_usd_cents = PLAN_PRICES_USD.get(plan)
    if price_usd_cents is None:
        logger.error(f"No USD price for plan '{plan}'")
        return None

    _configure()
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "unit_amount": price_usd_cents,
                        "product_data": {"name": f"AI Bot — план {plan}"},
                    },
                    "quantity": 1,
                }
            ],
            mode="payment",
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"user_id": str(user_id), "plan": plan},
        )
        return {"session_id": session.id, "checkout_url": session.url}
    except stripe.StripeError as exc:
        logger.error(f"Stripe create session error: {exc}")
        return None


def verify_stripe_webhook(payload: bytes, sig_header: str) -> Optional[Dict[str, Any]]:
    """Verify Stripe webhook signature and return the event object or None."""
    if not settings.STRIPE_WEBHOOK_SECRET:
        return None
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
        return event
    except (stripe.SignatureVerificationError, ValueError) as exc:
        logger.warning(f"Stripe webhook verification failed: {exc}")
        return None
