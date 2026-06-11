from aiogram import Router, F

from aiogram.types import (
    Message,
    CallbackQuery,
    FSInputFile,
    InputMediaPhoto
)

from aiogram.fsm.context import FSMContext

from forms.user import Form

import logging
from services.telegram_access_service import (
    ensure_calculator_access_for_message,
    ensure_calculator_access_for_callback,
)
from keyboards.inline import (
    CATEGORIES,
    SUBCATEGORIES,
    DIMENSION_HINT_IMAGE,
    category_keyboard,
    subcategory_keyboard
)

router = Router()


# --------------Вибір категорій------------------
@router.message(F.text == "🧮 Розпочати прорахунок")
async def show_categories(message: Message, state: FSMContext):
    if not await ensure_calculator_access_for_message(message):
        return

    await state.clear()
    index = 0
    cat = CATEGORIES[index]

    photo = FSInputFile(cat["img"])

    await message.answer_photo(
        photo=photo,
        caption=f"Оберіть категорію:\n\n{cat['name']}",
        reply_markup=category_keyboard(index)
    )

    await state.update_data(cat_index=index)


@router.callback_query(F.data.startswith("cat_next_") | F.data.startswith("cat_prev_"))
async def category_navigation(callback: CallbackQuery, state: FSMContext):
    if not await ensure_calculator_access_for_callback(callback):
        return

    data = callback.data.split("_")
    action = data[1]
    index = int(data[2])

    if action == "select":
        return

    if action == "next":
        index = (index + 1) % len(CATEGORIES)
    elif action == "prev":
        index = (index - 1) % len(CATEGORIES)

    cat = CATEGORIES[index]
    photo = FSInputFile(cat["img"])

    await callback.message.edit_media(
        InputMediaPhoto(
            media=photo,
            caption=f"Оберіть категорію:\n\n{cat['name']}"
        ),
        reply_markup=category_keyboard(index)
    )

    await state.update_data(cat_index=index)
    try:
        await callback.answer()
    except:
        pass


# Відкриття підкатегорій
@router.callback_query(F.data.startswith("cat_select_"))
async def select_category(callback: CallbackQuery, state: FSMContext):
    if not await ensure_calculator_access_for_callback(callback):
        return

    index = int(callback.data.split("_")[2])
    cat = CATEGORIES[index]

    code = cat.get("code")
    if not code:
        logging.error(f"Category {cat} missing 'code' key!")
        await callback.message.answer("❌ Помилка конфігурації категорії")
        try:
            await callback.answer()
        except:
            pass
        return

    if code not in SUBCATEGORIES:
        await callback.message.answer("❌ Немає підкатегорій")
        try:
            await callback.answer()
        except:
            pass
        return

    sub_index = 0
    sub = SUBCATEGORIES[code][sub_index]
    photo = FSInputFile(sub["img"])

    await callback.message.edit_media(
        InputMediaPhoto(
            media=photo,
            caption=f"Оберіть тип:\n\n{sub['name']}"
        ),
        reply_markup=subcategory_keyboard(sub_index)
    )

    await state.update_data(
        current_category=code,
        sub_index=sub_index
    )
    try:
        await callback.answer()
    except:
        pass


# Навігація підкатегорій
@router.callback_query(F.data.startswith("sub_"))
async def subcategory_navigation(callback: CallbackQuery, state: FSMContext):
    if not await ensure_calculator_access_for_callback(callback):
        return

    data = callback.data.split("_")
    action = data[1]
    index = int(data[2])

    state_data = await state.get_data()
    code = state_data.get("current_category")
    sub_list = SUBCATEGORIES.get(code, [])

    if action == "next":
        index = (index + 1) % len(sub_list)
    elif action == "prev":
        index = (index - 1) % len(sub_list)
    elif action == "select":
        sub = sub_list[index]

        await callback.message.delete()

        await state.update_data(
            current_category=code,
            subcategory=sub["name"],
            sub_type=sub.get("code"),
            has_handles=(sub.get("code") == "handles"),
            current_step=0,
            params={}
        )

        from handlers.dimensions import (
            start_dimensions_flow
        )

        await start_dimensions_flow(
            callback.message,
            state
        )

        try:
            await callback.answer()
        except:
            pass

        return

    sub = sub_list[index]
    photo = FSInputFile(sub["img"])

    await callback.message.edit_media(
        InputMediaPhoto(
            media=photo,
            caption=f"Оберіть тип:\n\n{sub['name']}"
        ),
        reply_markup=subcategory_keyboard(index)
    )

    await state.update_data(sub_index=index)
    try:
        await callback.answer()
    except:
        pass
