import asyncio

from database.repositories.user_repository import (
    get_user_by_telegram_id,
)
from services.user_roles import (
    ROLE_ADMIN,
    ROLE_GUEST,
    ROLE_PREMIUM,
    ROLE_PRO,
    ROLE_USER,
    normalize_user_role,
)
from aiogram.types import (
    Message,
    CallbackQuery,
)


CALCULATOR_ALLOWED_ROLES = {
    ROLE_ADMIN,
    ROLE_PREMIUM,
    ROLE_PRO,
    ROLE_USER,
}


async def get_telegram_platform_role(
    telegram_id: int,
) -> str:
    user = await asyncio.to_thread(
        get_user_by_telegram_id,
        str(telegram_id),
    )

    if not user:
        return ROLE_GUEST

    return normalize_user_role(user.role)


async def can_use_calculator(
    telegram_id: int,
) -> bool:
    role = await get_telegram_platform_role(telegram_id)
    return role in CALCULATOR_ALLOWED_ROLES


async def calculator_access_message(
    telegram_id: int,
) -> str:
    role = await get_telegram_platform_role(telegram_id)

    if role == ROLE_GUEST:
        return (
            "Для доступу до прорахунку потрібно "
            "активувати акаунт до рівня User або PRO."
        )

    return (
        "Прорахунок тимчасово недоступний "
        "для вашого статусу."
    )


async def ensure_calculator_access_for_message(
    message: Message,
) -> bool:
    if await can_use_calculator(message.from_user.id):
        return True

    await message.answer(
        await calculator_access_message(message.from_user.id)
    )
    return False


async def ensure_calculator_access_for_callback(
    callback: CallbackQuery,
) -> bool:
    if await can_use_calculator(callback.from_user.id):
        return True

    await callback.message.answer(
        await calculator_access_message(callback.from_user.id)
    )

    try:
        await callback.answer()
    except Exception:
        pass

    return False
