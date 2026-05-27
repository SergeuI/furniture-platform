from aiogram import Router, F

from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InputMediaPhoto
)

from aiogram.fsm.context import FSMContext

from forms.user import Form

from keyboards.inline import (
    DRAWER_BOTTOMS,
    drawer_bottom_carousel
)
from handlers.materials import (
    show_material_types
)

router = Router()



# =====================================================
# PREV BOTTOM
# =====================================================

@router.callback_query(
    Form.choose_drawer_bottom,
    F.data.startswith("bottom_prev_")
)
async def bottom_prev(
    callback: CallbackQuery,
    state: FSMContext
):

    index = int(
        callback.data.split("_")[-1]
    )

    index -= 1

    if index < 0:
        index = len(DRAWER_BOTTOMS) - 1

    bottom = DRAWER_BOTTOMS[index]

    media = InputMediaPhoto(

        media=FSInputFile(
            bottom["img"]
        ),

        caption=(

            "🗃 <b>Оберіть тип дна шухляди</b>\n\n"

            f"{bottom['name']}\n\n"

            f"{bottom['desc']}"
        ),

        parse_mode="HTML"
    )

    await callback.message.edit_media(

        media=media,

        reply_markup=drawer_bottom_carousel(index)
    )

    await callback.answer()


# =====================================================
# NEXT BOTTOM
# =====================================================

@router.callback_query(
    Form.choose_drawer_bottom,
    F.data.startswith("bottom_next_")
)
async def bottom_next(
    callback: CallbackQuery,
    state: FSMContext
):

    index = int(
        callback.data.split("_")[-1]
    )

    index += 1

    if index >= len(DRAWER_BOTTOMS):
        index = 0

    bottom = DRAWER_BOTTOMS[index]

    media = InputMediaPhoto(

        media=FSInputFile(
            bottom["img"]
        ),

        caption=(

            "🗃 <b>Оберіть тип дна шухляди</b>\n\n"

            f"{bottom['name']}\n\n"

            f"{bottom['desc']}"
        ),

        parse_mode="HTML"
    )

    await callback.message.edit_media(

        media=media,

        reply_markup=drawer_bottom_carousel(index)
    )

    await callback.answer()


# =====================================================
# SELECT BOTTOM
# =====================================================

@router.callback_query(
    Form.choose_drawer_bottom,
    F.data.startswith("bottom_select_")
)
async def choose_drawer_bottom(

    callback: CallbackQuery,

    state: FSMContext
):

    index = int(
        callback.data.split("_")[-1]
    )

    bottom = DRAWER_BOTTOMS[index]

    await state.update_data(

        drawer_bottom_type=bottom["code"]
    )

    await callback.message.delete()

    await callback.message.answer(

        f"✅ Обрано тип дна:\n"
        f"{bottom['name']}"
    )

    from handlers.materials import (
        show_material_types
    )

    await show_material_types(
        callback.message,
        state
    )

    await callback.answer()

