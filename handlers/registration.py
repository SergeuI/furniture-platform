from __future__ import annotations

import os
import re
from datetime import datetime

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from database.models.registration_identity import RegistrationChallengeModel
from database.models.user import UserModel
from database.session import SessionLocal
from forms.user import Form
from services.registration_identity_service import (
    CHALLENGE_BLOCKED,
    CHALLENGE_CONSUMED,
    hash_registration_token,
)
from services.registration_onboarding_service import (
    PUBLIC_APP_URL_ENV,
    TELEGRAM_CHANNEL,
    confirm_pending_phone_registration_via_telegram,
)


router = Router()


def _telegram_contact_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Поділитися номером телефону", request_contact=True)],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def _normalize_telegram_contact_phone(phone: str) -> str:
    text = str(phone or "").strip()
    if not text:
        raise ValueError("Phone number is required")

    if text.startswith("+"):
        return text

    digits = re.sub(r"\D+", "", text)
    if not digits:
        raise ValueError("Phone number is required")

    return f"+{digits}"


def _success_markup() -> InlineKeyboardMarkup | None:
    public_app_url = os.getenv(PUBLIC_APP_URL_ENV, "").strip()
    if not public_app_url:
        return None

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Повернутися на сайт",
                    url=public_app_url,
                )
            ]
        ]
    )


def _load_telegram_challenge(payload: str):
    db = SessionLocal()

    try:
        challenge = (
            db.query(RegistrationChallengeModel)
            .filter(RegistrationChallengeModel.channel == TELEGRAM_CHANNEL)
            .filter(RegistrationChallengeModel.token_hash == hash_registration_token(payload))
            .first()
        )

        if not challenge:
            return None, None

        user = (
            db.query(UserModel)
            .filter(UserModel.id == challenge.user_id)
            .first()
        )

        return challenge, user
    finally:
        db.close()


@router.message(CommandStart(deep_link=True))
async def registration_start_deeplink_handler(message: Message, state: FSMContext):
    if message.chat.type != "private":
        await message.answer("Використовуйте Telegram у приватному чаті.")
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Неправильне посилання для підтвердження.")
        return

    payload = parts[1].strip()
    challenge, user = _load_telegram_challenge(payload)

    if not challenge or not user:
        await message.answer("Неправильне або застаріле посилання для підтвердження.")
        return

    if challenge.status in {CHALLENGE_BLOCKED, CHALLENGE_CONSUMED}:
        await message.answer("Посилання вже використано або заблоковано.")
        return

    if challenge.expires_at and challenge.expires_at <= datetime.utcnow():
        await message.answer("Посилання вже прострочене. Поверніться на сайт і почніть ще раз.")
        return

    if (user.registration_status or "").strip().lower() != "pending_phone":
        await message.answer("Реєстрація вже не очікує підтвердження.")
        return

    if challenge.expected_identity_value_normalized != user.phone:
        await message.answer("Номер для підтвердження вже не збігається.")
        return

    await state.update_data(telegram_registration_payload=payload)
    await state.set_state(Form.telegram_registration)
    await message.answer(
        "Щоб завершити реєстрацію, поділіться номером телефону.",
        reply_markup=_telegram_contact_keyboard(),
    )


@router.message(Form.telegram_registration, F.text)
async def registration_text_handler(message: Message, state: FSMContext):
    if message.chat.type != "private":
        await message.answer("Реєстрація через Telegram працює тільки в приватному чаті.")
        return

    await message.answer(
        "Номер вручну вводити не потрібно. Будь ласка, натисніть кнопку під повідомленням.",
        reply_markup=_telegram_contact_keyboard(),
    )


@router.message(Form.telegram_registration, F.contact)
async def registration_contact_handler(message: Message, state: FSMContext):
    if message.chat.type != "private":
        await message.answer("Реєстрація через Telegram працює тільки в приватному чаті.")
        return

    contact = message.contact
    if not contact:
        await message.answer("Надішліть номер телефону через кнопку під повідомленням.")
        return

    if contact.user_id != message.from_user.id:
        await message.answer("Підтвердження приймається тільки для вашого власного номера.")
        return

    data = await state.get_data()
    payload = str(data.get("telegram_registration_payload") or "").strip()
    if not payload:
        await state.clear()
        await message.answer("Сеанс підтвердження завершився. Почніть ще раз із сайту.")
        return

    try:
        normalized_contact_phone = _normalize_telegram_contact_phone(contact.phone_number)
    except ValueError:
        await message.answer(
            "Не вдалося прочитати номер з Telegram contact. Будь ласка, натисніть кнопку під повідомленням ще раз.",
            reply_markup=_telegram_contact_keyboard(),
        )
        return

    result = confirm_pending_phone_registration_via_telegram(
        payload=payload,
        telegram_user_id=message.from_user.id,
        contact_phone=normalized_contact_phone,
    )

    if not result.get("success"):
        error = result.get("error") or "Не вдалося підтвердити номер."
        if result.get("error") in {
            "Phone number must start with +",
            "Phone number may contain only digits after +",
            "Phone number must contain 8 to 15 digits after +",
            "Phone number is required",
        }:
            await message.answer(
                "Номер з Telegram contact не вдалося підтвердити. Будь ласка, натисніть кнопку під повідомленням ще раз.",
                reply_markup=_telegram_contact_keyboard(),
            )
            return

        if result.get("error") in {
            "Challenge not found",
            f"Challenge is {CHALLENGE_CONSUMED}",
            f"Challenge is {CHALLENGE_BLOCKED}",
            "Challenge expired",
            "User not found",
            "User registration is not pending",
        }:
            await state.clear()

        await message.answer(error, reply_markup=ReplyKeyboardRemove())
        return

    await state.clear()

    markup = _success_markup()
    message_text = (
        "Номер підтверджено. Пробний доступ активовано на 7 днів."
        if result.get("trial_granted")
        else "Номер підтверджено. Доступ Free."
    )

    if markup:
        await message.answer(message_text, reply_markup=ReplyKeyboardRemove())
        await message.answer("Поверніться на сайт.", reply_markup=markup)
        return

    await message.answer(message_text, reply_markup=ReplyKeyboardRemove())
