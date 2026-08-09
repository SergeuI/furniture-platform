from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from aiogram import Bot, Dispatcher
from aiogram.filters import Command, CommandStart
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram import Router
from aiogram.types import (
    Chat,
    Contact,
    Message,
    MessageOriginUser,
    Update,
    User,
)

from forms.user import Form
from handlers import registration as registration_handlers
from handlers import profile as profile_handlers
from handlers.registration import (
    registration_contact_handler,
    registration_start_deeplink_handler,
    registration_text_handler,
)
from services import registration_onboarding_service as onboarding
from services.registration_identity_service import CHALLENGE_PENDING


class TelegramRegistrationHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_start_without_payload_routes_to_profile_flow_once(self) -> None:
        bot, dispatcher, storage = self._build_dispatcher()
        message_answer = mock.AsyncMock(return_value=None)
        update = self._build_update(message_id=1, text="/start")

        with mock.patch("aiogram.types.message.Message.answer", new=message_answer), mock.patch.object(
            profile_handlers,
            "user_exists",
            new=mock.AsyncMock(return_value=False),
        ):
            await dispatcher.feed_update(bot, update)

        self.assertEqual(message_answer.await_count, 1)
        state = await storage.get_state(self._storage_key(bot, update.message))
        self.assertEqual(state, Form.name.state)

    async def test_start_with_deeplink_routes_to_registration_flow_once(self) -> None:
        bot, dispatcher, storage = self._build_dispatcher()
        message_answer = mock.AsyncMock(return_value=None)
        challenge = SimpleNamespace(
            status=CHALLENGE_PENDING,
            expires_at=datetime.utcnow() + timedelta(minutes=5),
            expected_identity_value_normalized="+380501234567",
        )
        user = SimpleNamespace(
            registration_status=onboarding.REGISTRATION_STATUS_PENDING_PHONE,
            phone="+380501234567",
        )
        update = self._build_update(message_id=2, text="/start registration-payload")

        with mock.patch("aiogram.types.message.Message.answer", new=message_answer), mock.patch.object(
            profile_handlers,
            "user_exists",
            new=mock.AsyncMock(return_value=False),
        ), mock.patch.object(
            registration_handlers,
            "_load_telegram_challenge",
            return_value=(challenge, user),
        ):
            await dispatcher.feed_update(bot, update)

        self.assertEqual(message_answer.await_count, 1)
        state = await storage.get_state(self._storage_key(bot, update.message))
        self.assertEqual(state, Form.telegram_registration.state)

    async def test_text_in_telegram_registration_reprompts_for_contact_button(self) -> None:
        message_answer = mock.AsyncMock(return_value=None)
        message = self._build_message(
            message_id=3,
            text="+380632585040",
        )
        state = mock.AsyncMock()

        with mock.patch("aiogram.types.message.Message.answer", new=message_answer):
            await registration_text_handler(message, state)

        self.assertEqual(message_answer.await_count, 1)
        self.assertIn("натисніть кнопку", message_answer.await_args.args[0].lower())

    async def test_contact_handler_rejects_invalid_contacts_and_accepts_owner(self) -> None:
        message_answer = mock.AsyncMock(return_value=None)
        confirm = mock.Mock(return_value={"success": True, "trial_granted": True, "challenge_status": CHALLENGE_PENDING})

        cases = [
            (
                "non-private",
                self._build_message(
                    message_id=10,
                    text="contact",
                    chat_type="group",
                    contact=Contact(phone_number="+380501234567", first_name="Owner", user_id=123),
                    from_user_id=123,
                ),
                False,
            ),
            (
                "missing-user-id",
                self._build_message(
                    message_id=11,
                    text="contact",
                    contact=Contact(phone_number="+380501234567", first_name="Owner"),
                    from_user_id=123,
                ),
                False,
            ),
            (
                "other-telegram-user",
                self._build_message(
                    message_id=12,
                    text="contact",
                    contact=Contact(phone_number="+380501234567", first_name="Owner", user_id=999),
                    from_user_id=123,
                ),
                False,
            ),
            (
                "forwarded-contact",
                self._build_message(
                    message_id=13,
                    text="contact",
                    contact=Contact(phone_number="+380501234567", first_name="Owner", user_id=999),
                    from_user_id=123,
                    forward_origin=MessageOriginUser(
                        date=datetime.utcnow(),
                        sender_user=User(id=999, is_bot=False, first_name="Other"),
                    ),
                ),
                False,
            ),
            (
                "wrong-phone",
                self._build_message(
                    message_id=14,
                    text="contact",
                    contact=Contact(phone_number="+380501234568", first_name="Owner", user_id=123),
                    from_user_id=123,
                ),
                True,
            ),
            (
                "success",
                self._build_message(
                    message_id=15,
                    text="contact",
                    contact=Contact(phone_number="+380501234567", first_name="Owner", user_id=123),
                    from_user_id=123,
                ),
                True,
            ),
        ]

        with mock.patch.object(
            registration_handlers,
            "confirm_pending_phone_registration_via_telegram",
            new=confirm,
        ), mock.patch("aiogram.types.message.Message.answer", new=message_answer):
            for case_name, message, should_call_confirm in cases:
                with self.subTest(case=case_name):
                    state = mock.AsyncMock()
                    state.get_data = mock.AsyncMock(
                        return_value={"telegram_registration_payload": "opaque-payload"}
                    )
                    state.clear = mock.AsyncMock()
                    state.set_state = mock.AsyncMock()
                    confirm.reset_mock()
                    message_answer.reset_mock()

                    if case_name == "wrong-phone":
                        confirm.return_value = {
                            "success": False,
                            "error": "Phone number does not match pending registration",
                        }
                    else:
                        confirm.return_value = {
                            "success": True,
                            "trial_granted": True,
                            "challenge_status": CHALLENGE_PENDING,
                        }

                    await registration_contact_handler(message, state)

                    if should_call_confirm and case_name in {"wrong-phone", "success"}:
                        confirm.assert_called_once()
                    else:
                        confirm.assert_not_called()

                    if case_name == "success":
                        state.clear.assert_awaited_once()
                        self.assertGreaterEqual(message_answer.await_count, 1)
                    else:
                        state.clear.assert_not_awaited()
                        self.assertEqual(message_answer.await_count, 1)

    async def test_contact_handler_normalizes_phone_without_plus(self) -> None:
        message_answer = mock.AsyncMock(return_value=None)
        confirm = mock.Mock(return_value={"success": True, "trial_granted": False, "challenge_status": CHALLENGE_PENDING})
        message = self._build_message(
            message_id=16,
            text="contact",
            contact=Contact(phone_number="380632585040", first_name="Owner", user_id=123),
            from_user_id=123,
        )
        state = mock.AsyncMock()
        state.get_data = mock.AsyncMock(
            return_value={"telegram_registration_payload": "opaque-payload"}
        )
        state.clear = mock.AsyncMock()
        state.set_state = mock.AsyncMock()

        with mock.patch.object(
            registration_handlers,
            "confirm_pending_phone_registration_via_telegram",
            new=confirm,
        ), mock.patch("aiogram.types.message.Message.answer", new=message_answer):
            await registration_contact_handler(message, state)

        confirm.assert_called_once()
        self.assertEqual(confirm.call_args.kwargs["contact_phone"], "+380632585040")
        state.clear.assert_awaited_once()
        self.assertGreaterEqual(message_answer.await_count, 1)

    def test_registration_handlers_do_not_log_sensitive_values(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            session_factory = self._create_session_factory(Path(tmpdir) / "registration.db")

            with mock.patch.object(onboarding, "SessionLocal", session_factory), mock.patch.dict(
                os.environ,
                {
                    onboarding.TELEGRAM_REGISTRATION_ENV: "true",
                    onboarding.TELEGRAM_BOT_USERNAME_ENV: "furniture_bot",
                    "BOT_TOKEN": "123456:telegram-test-bot-token",
                    "AUTH_SECRET_KEY": "0123456789abcdef0123456789abcdef",
                    onboarding.TELEGRAM_TEST_EMAILS_ENV: "log-safe@example.com",
                },
                clear=True,
            ), self.assertLogs(onboarding.logger.name, level="INFO") as logs:
                start_response = onboarding.start_pending_phone_registration(
                    name="Log Safe",
                    email="log-safe@example.com",
                    password="Password123",
                    phone="+380501234567",
                )
                payload = start_response["telegram_confirmation_url"].split("start=")[1]
                onboarding.confirm_pending_phone_registration_via_telegram(
                    payload=payload,
                    telegram_user_id=987654321,
                    contact_phone="+380501234567",
                )

            log_output = "\n".join(logs.output)
            self.assertIn("Telegram registration: enabled", log_output)
            self.assertIn("AUTH_SECRET_KEY configured: yes", log_output)
            self.assertIn("Telegram bot username configured: yes", log_output)
            self.assertIn("Bot token configured: yes", log_output)
            self.assertNotIn("0123456789abcdef0123456789abcdef", log_output)
            self.assertNotIn("123456:telegram-test-bot-token", log_output)
            self.assertNotIn("log-safe@example.com", log_output)
            self.assertNotIn("opaque-payload", log_output)

    @staticmethod
    def _build_dispatcher() -> tuple[Bot, Dispatcher, MemoryStorage]:
        storage = MemoryStorage()
        dispatcher = Dispatcher(storage=storage)
        router = Router()
        router.message(CommandStart(deep_link=True))(registration_start_deeplink_handler)
        router.message(Command("start"))(profile_handlers.start)
        dispatcher.include_router(router)
        bot = Bot(token="123456:TEST")
        return bot, dispatcher, storage

    @staticmethod
    def _storage_key(bot: Bot, message: Message) -> StorageKey:
        return StorageKey(
            bot_id=bot.id,
            chat_id=message.chat.id,
            user_id=message.from_user.id,
        )

    @staticmethod
    def _build_update(*, message_id: int, text: str) -> Update:
        message = TelegramRegistrationHandlerTests._build_message(
            message_id=message_id,
            text=text,
        )
        return Update(update_id=message_id, message=message)

    @staticmethod
    def _build_message(
        *,
        message_id: int,
        text: str,
        chat_type: str = "private",
        contact: Contact | None = None,
        from_user_id: int = 123,
        forward_origin: MessageOriginUser | None = None,
    ) -> Message:
        return Message(
            message_id=message_id,
            date=datetime.utcnow(),
            chat=Chat(id=from_user_id, type=chat_type),
            from_user=User(id=from_user_id, is_bot=False, first_name="Tester"),
            text=text,
            contact=contact,
            forward_origin=forward_origin,
        )

    @staticmethod
    def _create_session_factory(database_path: Path):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from database.base import Base
        from database.models.registration_identity import (
            RegistrationChallengeModel,
            RegistrationIdentityModel,
        )
        from database.models.user import UserModel

        engine = create_engine(
            f"sqlite:///{database_path.as_posix()}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(
            engine,
            tables=[
                UserModel.__table__,
                RegistrationIdentityModel.__table__,
                RegistrationChallengeModel.__table__,
            ],
        )
        return sessionmaker(bind=engine, autocommit=False, autoflush=False)


if __name__ == "__main__":
    unittest.main()
