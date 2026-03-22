from typing import List, Optional

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import UNCENSORED_MODELS


def models_keyboard(
    current_model: str,
    allowed_models: Optional[List[str]] = None,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    for model_id, info in UNCENSORED_MODELS.items():
        is_allowed = allowed_models is None or model_id in allowed_models
        is_current = model_id == current_model

        label_parts = []
        if not is_allowed:
            label_parts.append("🔒")
        elif is_current:
            label_parts.append("✅")
        else:
            label_parts.append("🤖")
        label_parts.append(info["name"])
        label = " ".join(label_parts)

        builder.row(
            InlineKeyboardButton(text=label, callback_data=f"model:{model_id}")
        )

    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")
    )
    return builder.as_markup()
