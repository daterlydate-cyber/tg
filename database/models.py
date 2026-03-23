from datetime import datetime
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from database.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # Telegram user ID
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Plan & tokens
    plan: Mapped[str] = mapped_column(String(32), default="free", server_default="free")
    tokens_left: Mapped[int] = mapped_column(Integer, default=10_000, server_default="10000")
    tokens_total: Mapped[int] = mapped_column(Integer, default=10_000, server_default="10000")

    # AI settings
    selected_model: Mapped[str] = mapped_column(
        String(128), default="venice-uncensored", server_default="venice-uncensored"
    )
    temperature: Mapped[float] = mapped_column(Float, default=0.7, server_default="0.7")
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Statistics
    total_requests: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    total_tokens_used: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    # Status
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_active: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    model_id: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class BroadcastMessage(Base):
    __tablename__ = "broadcast_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    sent_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Payment(Base):
    """Records every payment attempt regardless of provider."""

    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    plan: Mapped[str] = mapped_column(String(32), nullable=False)

    # Provider: "yookassa" | "stripe" | "stars"
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    # External payment/session ID from the provider
    external_id: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)

    # "pending" | "succeeded" | "failed" | "cancelled"
    status: Mapped[str] = mapped_column(String(32), default="pending", server_default="pending")

    # Amount in the smallest unit (kopecks for RUB, cents for USD, stars for XTR)
    amount: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(8), default="RUB", server_default="RUB")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
