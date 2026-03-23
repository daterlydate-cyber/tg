from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import List, Dict, Any


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Telegram
    BOT_TOKEN: str = Field(..., description="Telegram Bot Token")
    ADMIN_IDS: str = Field("", description="Comma-separated admin Telegram IDs")

    # Venice.ai
    VENICE_API_KEY: str = Field(..., description="Venice.ai API Key")

    # Database
    DATABASE_URL: str = Field(
        "postgresql+asyncpg://aibot_user:password@localhost/aibot_db",
        description="PostgreSQL async URL",
    )

    # Redis
    REDIS_URL: str = Field("redis://localhost:6379", description="Redis URL")

    # Admin panel
    ADMIN_SECRET_KEY: str = Field("changeme", description="Admin panel password")
    ADMIN_PORT: int = Field(8080, description="Admin panel port")

    # YooKassa (CIS payments in RUB)
    YOOKASSA_SHOP_ID: str = Field("", description="YooKassa shop ID")
    YOOKASSA_SECRET_KEY: str = Field("", description="YooKassa secret key")
    YOOKASSA_RETURN_URL: str = Field(
        "https://t.me/your_bot",
        description="URL to redirect after YooKassa payment",
    )

    # Stripe (Europe / USA payments in USD)
    STRIPE_SECRET_KEY: str = Field("", description="Stripe secret key")
    STRIPE_WEBHOOK_SECRET: str = Field("", description="Stripe webhook signing secret")
    STRIPE_SUCCESS_URL: str = Field(
        "https://t.me/your_bot?start=paid",
        description="Stripe success redirect URL",
    )
    STRIPE_CANCEL_URL: str = Field(
        "https://t.me/your_bot",
        description="Stripe cancel redirect URL",
    )

    # Webhook host (used to build URLs for payment providers)
    WEBHOOK_HOST: str = Field("", description="Public HTTPS host for webhooks, e.g. https://bot.example.com")

    @property
    def admin_ids(self) -> List[int]:
        if not self.ADMIN_IDS:
            return []
        return [int(x.strip()) for x in self.ADMIN_IDS.split(",") if x.strip()]


settings = Settings()

# ---------------------------------------------------------------------------
# Tariff plans
# ---------------------------------------------------------------------------
PLANS: Dict[str, Dict[str, Any]] = {
    "free": {
        "name": "Free",
        "tokens": 10_000,
        "history_messages": 10,
        "allowed_models": ["venice-uncensored", "llama-3.2-3b"],
    },
    "basic": {
        "name": "Basic",
        "tokens": 500_000,
        "history_messages": 30,
        "allowed_models": None,  # all models
    },
    "premium": {
        "name": "Premium",
        "tokens": 3_000_000,
        "history_messages": 50,
        "allowed_models": None,
    },
    "unlimited": {
        "name": "Unlimited",
        "tokens": 999_999_999,
        "history_messages": 100,
        "allowed_models": None,
    },
}

# ---------------------------------------------------------------------------
# Uncensored Venice.ai models
# ---------------------------------------------------------------------------
UNCENSORED_MODELS: Dict[str, Dict[str, str]] = {
    "venice-uncensored": {
        "name": "Venice Uncensored",
        "description": "Флагманская uncensored модель Venice.ai",
        "plan_required": "free",
    },
    "llama-3.3-70b": {
        "name": "Llama 3.3 70B",
        "description": "Meta Llama 3.3 — 70 млрд параметров",
        "plan_required": "basic",
    },
    "hermes-3-llama-3.1-405b": {
        "name": "Hermes 3 Llama 3.1 405B",
        "description": "Hermes 3 на базе Llama 3.1 — 405 млрд параметров",
        "plan_required": "basic",
    },
    "deepseek-v3": {
        "name": "DeepSeek V3",
        "description": "DeepSeek V3 — мощная открытая модель",
        "plan_required": "basic",
    },
    "qwen3-235b-a22b-instruct": {
        "name": "Qwen3 235B",
        "description": "Qwen3 — 235 млрд параметров, instruct",
        "plan_required": "basic",
    },
    "llama-3.2-3b": {
        "name": "Llama 3.2 3B",
        "description": "Meta Llama 3.2 — лёгкая 3B модель",
        "plan_required": "free",
    },
}

# ---------------------------------------------------------------------------
# Payment prices
# ---------------------------------------------------------------------------

# YooKassa prices in RUB (whole rubles)
PLAN_PRICES_RUB: Dict[str, int] = {
    "basic": 399,
    "premium": 999,
    "unlimited": 1999,
}

# Stripe prices in USD cents (e.g. 499 = $4.99)
PLAN_PRICES_USD: Dict[str, int] = {
    "basic": 499,
    "premium": 1499,
    "unlimited": 2999,
}

# Telegram Stars (1 star ≈ $0.013 as of 2024)
PLAN_PRICES_STARS: Dict[str, int] = {
    "basic": 350,
    "premium": 1000,
    "unlimited": 2000,
}

# Human-readable price strings for the bot UI
PLAN_PRICE_LABELS: Dict[str, Dict[str, str]] = {
    "basic": {"rub": "399 ₽", "usd": "$4.99", "stars": "350 ⭐"},
    "premium": {"rub": "999 ₽", "usd": "$14.99", "stars": "1 000 ⭐"},
    "unlimited": {"rub": "1 999 ₽", "usd": "$29.99", "stars": "2 000 ⭐"},
}
