from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
) 
from aiogram.types import FSInputFile, InputMediaPhoto

def main_menu():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Головна")],
            [KeyboardButton(text="Правило"), KeyboardButton(text="Вихід")]
        ],
        # Налаштовує кнопки
        resize_keyboard=True,
        # Показує один раз
        one_time_keyboard=True,
        # Напис в стрічці вводу
        input_field_placeholder="Виберіть щось!" 
    )

    return keyboard


VIYAR_CITIES = {
    "kyiv": "🏙 Київ",
    "lviv": "🏰 Львів",
    "dnipro": "🌉 Дніпро",
    "odessa": "🌊 Одеса",
    "kharkiv": "🏢 Харків",
    "rivne": "🌲 Рівне",
    "khmelnytskyi": "🏘 Хмельницький"
}

#                                  Головне меню

def user_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🧮 Розпочати прорахунок")],
            [KeyboardButton(text="✏️ Змінити дані профілю"), KeyboardButton(text="🤖 Допомога")],
            
        ],
        resize_keyboard=True,
        input_field_placeholder="Зробіть вибір 👇"
    )

#                              /    Головне меню


#                                  Меню при зміні анкети

def edit_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Телефон"), KeyboardButton(text="🏙 Місто")],
            [KeyboardButton(text="📧 Email"), KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="Зробіть вибір 👇"
    )

#                                  /Меню при зміні анкети



def handles_keyboard(index):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⬅️", callback_data=f"handle_prev_{index}"),
            InlineKeyboardButton(text="➡️", callback_data=f"handle_next_{index}")
        ],
        [
            InlineKeyboardButton(text="✅ Обрати", callback_data=f"handle_select_{index}")
        ]
    ])