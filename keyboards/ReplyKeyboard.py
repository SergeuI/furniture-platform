from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)


def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Головна")],
            [KeyboardButton(text="Правило"), KeyboardButton(text="Вихід")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="Виберіть щось!",
    )


VIYAR_CITIES = {
    "kyiv": "🏙 Київ",
    "lviv": "🏰 Львів",
    "dnipro": "🌉 Дніпро",
    "odessa": "🌊 Одеса",
    "kharkiv": "🏢 Харків",
    "rivne": "🌲 Рівне",
    "khmelnytskyi": "🏘 Хмельницький",
}


def user_menu(role="user"):
    keyboard = []

    if role != "guest":
        keyboard.append([KeyboardButton(text="🧮 Розпочати прорахунок")])

    keyboard.append(
        [
            KeyboardButton(text="👤 Мої дані"),
            KeyboardButton(text="✏️ Змінити дані профілю"),
        ]
    )
    keyboard.append([KeyboardButton(text="🤖 Допомога")])

    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        input_field_placeholder="Зробіть вибір 👇",
    )


def edit_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Телефон"), KeyboardButton(text="🏙 Місто")],
            [KeyboardButton(text="📧 Email"), KeyboardButton(text="⬅️ Назад")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="Зробіть вибір 👇",
    )


def handles_keyboard(index):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⬅️", callback_data=f"handle_prev_{index}"),
                InlineKeyboardButton(text="➡️", callback_data=f"handle_next_{index}"),
            ],
            [
                InlineKeyboardButton(text="✅ Обрати", callback_data=f"handle_select_{index}")
            ],
        ]
    )
