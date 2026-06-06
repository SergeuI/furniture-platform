from aiogram import Router, F

from aiogram.filters import (
    Command
)

from aiogram.types import (
    Message,
    CallbackQuery,
    FSInputFile
)

from aiogram.fsm.context import FSMContext

from forms.user import (
    Form
)

import re
import aiosqlite
from services.legacy_db_config import (
    DEFAULT_DB_PATH,
    TELEGRAM_USERS_TABLE,
)

from keyboards.ReplyKeyboard import (
    user_menu,
    edit_menu
)

from keyboards.inline import (
    city_keyboard,
    VIYAR_CITIES
)

from services.profile_card import (
    build_profile_card
)

router = Router()

DB_NAME = DEFAULT_DB_PATH



async def user_exists(telegram_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            f"SELECT 1 FROM {TELEGRAM_USERS_TABLE} WHERE telegram_id = ?",
            (telegram_id,)
        )
        return await cursor.fetchone()

async def add_user(telegram_id, name, phone, citi, email):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT INTO telegram_users (telegram_id, name, phone, citi, email)
            VALUES (?, ?, ?, ?, ?)
        """, (telegram_id, name, phone, citi, email))
        await db.commit()

async def get_user(telegram_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            f"SELECT name, phone, citi, email FROM {TELEGRAM_USERS_TABLE} WHERE telegram_id = ?",
            (telegram_id,)
        )
        return await cursor.fetchone()


# -----------Форма реестрації-----------
@router.message(Command("start"))
async def start(message: Message, state: FSMContext):
    tg_id = message.from_user.id

    if await user_exists(tg_id):
        user = await get_user(tg_id)
        name, phone, citi, email = user

        photos = await message.bot.get_user_profile_photos(
            user_id=message.from_user.id,
            limit=1
        )

        caption = (
            f"🙎🏻‍♂️ <b>Ваш профіль:</b>\n\n"
            f"Ім'я: <i>{name}</i>\n"
            f"Телефон: <i>{phone}</i>\n"
            f"Місто: <i>{citi}</i>\n"
            f"Email: <i>{email}</i>"
        )

        # якщо є аватар
        if photos.total_count > 0:

            file_id = photos.photos[0][-1].file_id

            profile_path = await build_profile_card(
                bot=message.bot,
                user_id=message.from_user.id,
                name=name,
                phone=phone,
                city=citi,
                email=email
            )

            photo = FSInputFile(profile_path)

            await message.answer_photo(
                photo=photo,
                caption="✅ Ваш профіль завантажено",
                reply_markup=user_menu()
            )

        # якщо аватару нема
        else:

            await message.answer(
                caption,
                parse_mode="HTML",
                reply_markup=user_menu()
            )
        return

    await message.answer("✍️ Введіть ваше ім'я:")
    await state.set_state(Form.name)


@router.message(Form.name)
async def process_name(message: Message, state: FSMContext):
    name = message.text.strip()

    if len(name) < 2:
        await message.answer("❌ Ім'я занадто коротке")
        return

    await state.update_data(name=name)
    await message.answer("📱 Введіть телефон (+380...):")
    await state.set_state(Form.phone)


@router.message(Form.phone)
async def process_phone(message: Message, state: FSMContext):
    phone = message.text.strip()

    if not re.match(r"^\+380\d{9}$", phone):
        await message.answer("❌ Невірний формат!")
        return

    await state.update_data(phone=phone)

    await message.answer(
        "🏙 Оберіть місто:",
        reply_markup=city_keyboard()
    )

    await state.set_state(Form.citi)


@router.callback_query(Form.citi, F.data.startswith("city_"))
async def process_city_callback(callback: CallbackQuery, state: FSMContext):
    code = callback.data.split("_")[1]
    city_name = VIYAR_CITIES.get(code)

    await state.update_data(citi=city_name)
    await callback.message.edit_text(f"✅ Обрано місто: {city_name}")
    await callback.message.answer("📧 Введіть email:")
    await state.set_state(Form.email)

    try:
        await callback.answer()
    except:
        pass


@router.message(Form.email)
async def process_email(message: Message, state: FSMContext):
    email = message.text.strip()

    if not re.match(r"^[^@]+@[^@]+\.[^@]+$", email):
        await message.answer("❌ Невірний email")
        return

    await state.update_data(email=email)
    data = await state.get_data()

    await add_user(
        message.from_user.id,
        data["name"],
        data["phone"],
        data["citi"],
        data["email"]
    )

    await message.answer("✅ Реєстрація завершена!", reply_markup=user_menu())
    await state.clear()



async def update_user_field(telegram_id, field, value):
    if field not in ("phone", "citi", "email"):
        return

    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            f"UPDATE {TELEGRAM_USERS_TABLE} SET {field} = ? WHERE telegram_id = ?",
            (value, telegram_id)
        )
        await db.commit()


# ----------Зміна данних анкети----------
@router.message(F.text == "✏️ Змінити дані профілю")
async def edit_profile(message: Message, state: FSMContext):
    await message.answer(
        "Що хочете змінити?",
        reply_markup=edit_menu()
    )

@router.message(Form.edit_phone)
async def update_phone(message: Message, state: FSMContext):
    phone = message.text.strip()

    if not re.match(r"^\+380\d{9}$", phone):
        await message.answer("❌ Невірний формат!")
        return

    await update_user_field(message.from_user.id, "phone", phone)
    await message.answer("✅ Телефон оновлено")
    await state.clear()


@router.callback_query(Form.edit_citi, F.data.startswith("city_"))
async def update_city(callback: CallbackQuery, state: FSMContext):
    code = callback.data.split("_")[1]
    city_name = VIYAR_CITIES.get(code)

    if not city_name:
        try:
            await callback.answer("❌ Помилка", show_alert=True)
        except:
            pass
        return

    await update_user_field(callback.from_user.id, "citi", city_name)
    await callback.message.edit_text(f"✅ Місто оновлено: {city_name}")
    await state.clear()
    try:
        await callback.answer()
    except:
        pass


@router.message(Form.edit_email)
async def update_email(message: Message, state: FSMContext):
    email = message.text.strip()

    if not re.match(r"^[^@]+@[^@]+\.[^@]+$", email):
        await message.answer("❌ Невірний email")
        return

    await update_user_field(message.from_user.id, "email", email)
    await message.answer("✅ Email оновлено")
    await state.clear()


@router.message(F.text == "⬅️ Назад")
async def back_to_menu(message: Message):
    await message.answer(
        "Головне меню:",
        reply_markup=user_menu()
    )


@router.message(F.text == "📱 Телефон")
async def edit_phone(message: Message, state: FSMContext):
    await message.answer("Введіть новий телефон:")
    await state.set_state(Form.edit_phone)


@router.message(F.text == "🏙 Місто")
async def edit_city(message: Message, state: FSMContext):
    await message.answer(
        "Оберіть нове місто:",
        reply_markup=city_keyboard()
    )
    await state.set_state(Form.edit_citi)


@router.message(F.text == "📧 Email")
async def edit_email(message: Message, state: FSMContext):
    await message.answer("Введіть новий email:")
    await state.set_state(Form.edit_email)
