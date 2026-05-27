from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


VIYAR_CITIES = {
    "kyiv": "🏙 Київ",
    "lviv": "🏰 Львів",
    "dnipro": "🌉 Дніпро",
    "odessa": "🌊 Одеса",
    "kharkiv": "🏢 Харків"
}


def city_keyboard():
    buttons = []
    row = []

    for i, (code, name) in enumerate(VIYAR_CITIES.items(), start=1):
        row.append(InlineKeyboardButton(
            text=name,
            callback_data=f"city_{code}"
        ))

        if i % 2 == 0:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def category_keyboard(index: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⬅️", callback_data=f"cat_prev_{index}"),
            InlineKeyboardButton(text="➡️", callback_data=f"cat_next_{index}")
        ],
        [
            InlineKeyboardButton(text="✅ Обрати", callback_data=f"cat_select_{index}")
        ]
    ])

#                                    Карусель підкатегорій


def subcategory_keyboard(index: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⬅️", callback_data=f"sub_prev_{index}"),
            InlineKeyboardButton(text="➡️", callback_data=f"sub_next_{index}")
        ],
        [
            InlineKeyboardButton(text="✅ Обрати", callback_data=f"sub_select_{index}")
        ]
    ])


#                                           Категорії меблів

CATEGORIES = [
    {"code": "dresser", "name": "🗄 Комоди", "img": "images/dresser.jpg"},
    {"code": "wardrobe", "name": "🚪 Шафи", "img": "images/wardrobe.jpg"},
    {"code": "table", "name": "🪑 Столи", "img": "images/table.jpg"},  # ✅ ИСПРАВЛЕНО: добавлен "code"
]

#                                           Підкатегорії комода

SUBCATEGORIES = {
    "dresser": [
        {"name": "👉 Комод с Tip-on", "img": "images/dresser_tipon.jpg", "code": "tipon"},
        {"name": "👉 З ручками", "img": "images/dresser_handles.jpg", "code": "handles"},
        {"name": "👉 Зазори між фасадами", "img": "images/dresser_gaps.jpg", "code": "gaps"},
        {"name": "👉 Gola", "img": "images/dresser_gola.jpg", "code": "gola"},
    ]
}


DIMENSION_FLOW = {
    "dresser": ["width", "height", "depth"],
    "wardrobe": ["width", "height", "depth"],
    "kitchen": ["width", "height", "depth"],
    "table": ["width", "height", "depth"]  # ✅ ИСПРАВЛЕНО: добавлен "table"
}

DIMENSION_LABELS = {
    "width": "ширину",
    "height": "висоту",
    "depth": "глибину"
}

DIMENSION_HINT_IMAGE = "images/dresser_hint.jpg"
DIMENSION_IMAGES = {
    "width": "images/help_width.jpg",
    "height": "images/help_height.jpg",
    "depth": "images/help_depth.jpg"
}


MATERIALS = [
    {"article": "215557", "name": "Матеріал 1", "img": "images/mat1.jpg"},
    {"article": "43102", "name": "Матеріал 2", "img": "images/mat2.jpg"},
    {"article": "45791", "name": "Матеріал 3", "img": "images/mat3.jpg"},
    {"article": "77792", "name": "Матеріал 4", "img": "images/mat4.jpg"},
]


def material_keyboard(index):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⬅️", callback_data=f"mat_prev_{index}"),
            InlineKeyboardButton(text="➡️", callback_data=f"mat_next_{index}")
        ],
        [
            InlineKeyboardButton(text="✅ Обрати", callback_data=f"mat_select_{index}")
        ]
    ])


MATERIAL_TYPES = [
    {
        "code": "single",
        "name": "🎨 Один колір",
        "img": "images/material_single.jpg"
    },
    {
        "code": "double",
        "name": "🎭 Два кольори",
        "img": "images/material_double.jpg"
    }
]


def material_type_keyboard(index: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⬅️", callback_data=f"mtype_prev_{index}"),
            InlineKeyboardButton(text="➡️", callback_data=f"mtype_next_{index}")
        ],
        [
            InlineKeyboardButton(text="✅ Обрати", callback_data=f"mtype_select_{index}")
        ]
    ])


def fittings_keyboard(index):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⬅️", callback_data=f"fit_prev_{index}"),
            InlineKeyboardButton(text="➡️", callback_data=f"fit_next_{index}")
        ],
        [
            InlineKeyboardButton(text="✅ Обрати", callback_data=f"fit_select_{index}")
        ]
    ])


from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton


def fitting_carousel_keyboard():

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⬅️",
                    callback_data="fit_prev"
                ),

                InlineKeyboardButton(
                    text="✅ Обрати",
                    callback_data="fit_select"
                ),

                InlineKeyboardButton(
                    text="➡️",
                    callback_data="fit_next"
                )
            ]
        ]
    )

    return keyboard

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


# =====================================================
# КАРУСЕЛЬ СЕКЦІЙ
# =====================================================

def sections_keyboard(current_index: int, total: int):

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[

            [
                InlineKeyboardButton(
                    text="⬅️",
                    callback_data=f"sec_prev_{current_index}"
                ),

                InlineKeyboardButton(
                    text=f"{current_index + 1}/{total}",
                    callback_data="ignore"
                ),

                InlineKeyboardButton(
                    text="➡️",
                    callback_data=f"sec_next_{current_index}"
                )
            ],

            [
                InlineKeyboardButton(
                    text="✅ Обрати",
                    callback_data=f"select_section_{current_index}"
                )
            ]
        ]
    )

    return keyboard


# =====================================================
# КАРУСЕЛЬ ШУХЛЯД
# =====================================================

def drawers_keyboard(current_index: int, total: int):

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[

            [
                InlineKeyboardButton(
                    text="⬅️",
                    callback_data=f"draw_prev_{current_index}"
                ),

                InlineKeyboardButton(
                    text=f"{current_index + 1}/{total}",
                    callback_data="ignore"
                ),

                InlineKeyboardButton(
                    text="➡️",
                    callback_data=f"draw_next_{current_index}"
                )
            ],

            [
                InlineKeyboardButton(
                    text="✅ Обрати",
                    callback_data=f"select_drawers_{current_index}"
                )
            ]
        ]
    )

    return keyboard


DRAWER_BOTTOMS = [

    {
        "code": "dsp",

        "name": "🟫 ДСП",

        "desc":
            "• міцніше\n"
            "• дорожче\n"
            "• більше вага",

        "img": "images/drawers/drawer_dsp.jpg"
    },

    {
        "code": "hdf",

        "name": "⬜ ДВП / HDF",

        "desc":
            "• дешевше\n"
            "• легше\n"
            "• потрібен паз",

        "img": "images/drawers/drawer_hdf.jpg"
    }
]


def drawer_bottom_carousel(index: int):

    from aiogram.types import (
        InlineKeyboardMarkup,
        InlineKeyboardButton
    )

    return InlineKeyboardMarkup(

        inline_keyboard=[

            [

                InlineKeyboardButton(
                    text="⬅️",
                    callback_data=f"bottom_prev_{index}"
                ),

                InlineKeyboardButton(
                    text="✅ Обрати",
                    callback_data=f"bottom_select_{index}"
                ),

                InlineKeyboardButton(
                    text="➡️",
                    callback_data=f"bottom_next_{index}"
                )

            ]

        ]
    )