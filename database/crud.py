from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from config import PLANS
from database.db import async_session_maker
from database.models import BroadcastMessage, Conversation, User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_session() -> AsyncSession:
    """Return a new async session (caller must close it)."""
    return async_session_maker()


# ---------------------------------------------------------------------------
# User CRUD
# ---------------------------------------------------------------------------

async def get_or_create_user(
    user_id: int,
    username: Optional[str],
    first_name: Optional[str],
) -> User:
    async with async_session_maker() as session:
        user = await session.get(User, user_id)
        if user is None:
            user = User(
                id=user_id,
                username=username,
                first_name=first_name,
                plan="free",
                tokens_left=PLANS["free"]["tokens"],
                tokens_total=PLANS["free"]["tokens"],
            )
            session.add(user)
        else:
            user.username = username
            user.first_name = first_name
            user.last_active = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(user)
        return user


async def get_user(user_id: int) -> Optional[User]:
    async with async_session_maker() as session:
        return await session.get(User, user_id)


async def update_user_model(user_id: int, model_id: str) -> None:
    async with async_session_maker() as session:
        await session.execute(
            update(User).where(User.id == user_id).values(selected_model=model_id)
        )
        await session.commit()


async def update_user_temperature(user_id: int, temp: float) -> None:
    async with async_session_maker() as session:
        await session.execute(
            update(User).where(User.id == user_id).values(temperature=temp)
        )
        await session.commit()


async def update_user_system_prompt(user_id: int, prompt: Optional[str]) -> None:
    async with async_session_maker() as session:
        await session.execute(
            update(User).where(User.id == user_id).values(system_prompt=prompt)
        )
        await session.commit()


async def deduct_tokens(user_id: int, amount: int) -> None:
    async with async_session_maker() as session:
        await session.execute(
            update(User)
            .where(User.id == user_id)
            .values(
                tokens_left=User.tokens_left - amount,
                total_tokens_used=User.total_tokens_used + amount,
                total_requests=User.total_requests + 1,
                last_active=datetime.now(timezone.utc),
            )
        )
        await session.commit()


async def ban_user(user_id: int, banned: bool) -> None:
    async with async_session_maker() as session:
        await session.execute(
            update(User).where(User.id == user_id).values(is_banned=banned)
        )
        await session.commit()


async def set_user_plan(user_id: int, plan: str) -> None:
    tokens = PLANS[plan]["tokens"]
    async with async_session_maker() as session:
        await session.execute(
            update(User)
            .where(User.id == user_id)
            .values(plan=plan, tokens_left=tokens, tokens_total=tokens)
        )
        await session.commit()


async def add_tokens(user_id: int, amount: int) -> None:
    async with async_session_maker() as session:
        await session.execute(
            update(User)
            .where(User.id == user_id)
            .values(
                tokens_left=User.tokens_left + amount,
                tokens_total=User.tokens_total + amount,
            )
        )
        await session.commit()


async def get_all_users(
    page: int = 1,
    per_page: int = 20,
    search: Optional[str] = None,
) -> Tuple[List[User], int]:
    async with async_session_maker() as session:
        query = select(User)
        if search:
            from sqlalchemy import or_
            try:
                uid = int(search)
                query = query.where(
                    or_(
                        User.username.ilike(f"%{search}%"),
                        User.first_name.ilike(f"%{search}%"),
                        User.id == uid,
                    )
                )
            except ValueError:
                query = query.where(
                    or_(
                        User.username.ilike(f"%{search}%"),
                        User.first_name.ilike(f"%{search}%"),
                    )
                )

        count_result = await session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar_one()

        query = query.order_by(User.last_active.desc())
        query = query.offset((page - 1) * per_page).limit(per_page)
        result = await session.execute(query)
        users = result.scalars().all()
        return list(users), total


async def get_stats() -> dict:
    async with async_session_maker() as session:
        total_users = (await session.execute(select(func.count(User.id)))).scalar_one()
        banned_users = (
            await session.execute(select(func.count(User.id)).where(User.is_banned.is_(True)))
        ).scalar_one()
        total_requests = (
            await session.execute(select(func.sum(User.total_requests)))
        ).scalar_one() or 0
        total_tokens = (
            await session.execute(select(func.sum(User.total_tokens_used)))
        ).scalar_one() or 0

        today = datetime.now(timezone.utc).date()
        active_today = (
            await session.execute(
                select(func.count(User.id)).where(
                    func.date(User.last_active) == today
                )
            )
        ).scalar_one()

        # Top models
        models_result = await session.execute(
            select(Conversation.model_id, func.count(Conversation.id).label("cnt"))
            .group_by(Conversation.model_id)
            .order_by(func.count(Conversation.id).desc())
            .limit(5)
        )
        top_models = [{"model": row[0], "count": row[1]} for row in models_result]

        # Plan distribution
        plans_result = await session.execute(
            select(User.plan, func.count(User.id).label("cnt"))
            .group_by(User.plan)
            .order_by(func.count(User.id).desc())
        )
        plan_dist = [{"plan": row[0], "count": row[1]} for row in plans_result]

        return {
            "total_users": total_users,
            "banned_users": banned_users,
            "total_requests": total_requests,
            "total_tokens": total_tokens,
            "active_today": active_today,
            "top_models": top_models,
            "plan_distribution": plan_dist,
        }


# ---------------------------------------------------------------------------
# Conversation CRUD
# ---------------------------------------------------------------------------

async def get_conversation_history(user_id: int, limit: int = 20) -> List[Conversation]:
    async with async_session_maker() as session:
        result = await session.execute(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.created_at.desc())
            .limit(limit)
        )
        rows = result.scalars().all()
        return list(reversed(rows))


async def save_message(
    user_id: int,
    model_id: str,
    role: str,
    content: str,
    tokens_used: int = 0,
) -> None:
    async with async_session_maker() as session:
        msg = Conversation(
            user_id=user_id,
            model_id=model_id,
            role=role,
            content=content,
            tokens_used=tokens_used,
        )
        session.add(msg)
        await session.commit()


async def clear_history(user_id: int) -> None:
    from sqlalchemy import delete

    async with async_session_maker() as session:
        await session.execute(
            delete(Conversation).where(Conversation.user_id == user_id)
        )
        await session.commit()


# ---------------------------------------------------------------------------
# Broadcast
# ---------------------------------------------------------------------------

async def create_broadcast(text: str) -> BroadcastMessage:
    async with async_session_maker() as session:
        msg = BroadcastMessage(text=text)
        session.add(msg)
        await session.commit()
        await session.refresh(msg)
        return msg


async def update_broadcast_count(broadcast_id: int, sent_count: int) -> None:
    async with async_session_maker() as session:
        await session.execute(
            update(BroadcastMessage)
            .where(BroadcastMessage.id == broadcast_id)
            .values(sent_count=sent_count)
        )
        await session.commit()


async def get_all_user_ids() -> List[int]:
    async with async_session_maker() as session:
        result = await session.execute(
            select(User.id).where(User.is_banned.is_(False))
        )
        return [row[0] for row in result]
