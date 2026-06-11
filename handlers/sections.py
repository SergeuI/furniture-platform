from aiogram import Router, F

from aiogram.types import (
    CallbackQuery,
    Message,
    FSInputFile,
    InputMediaPhoto
)

from aiogram.fsm.context import FSMContext

from forms.user import Form

from keyboards.inline import (
    sections_keyboard
)

from services.callback_lock import (
    acquire_lock,
    release_lock
)
from core.geometry.sections import (
    build_sections_geometry
)
from services.telegram_access_service import (
    ensure_calculator_access_for_message,
    ensure_calculator_access_for_callback,
)


router = Router()


def get_available_sections(width: int):

    result = []

    for sections in [2, 3, 4, 5]:

        geometry = build_sections_geometry(

            total_width=width,

            sections_count=sections
        )

        section_width = geometry[
            "section_width"
        ]

        # мінімум 200 мм
        if section_width >= 200:

            result.append({

                "count": sections,

                "section_width": section_width,

                "image": (
                    f"images/sections/"
                    f"section_{sections}.jpg"
                )
            })

    return result

# =====================================================
# ПОКАЗ СЕКЦІЙ
# =====================================================

async def show_sections(message, state, index=0):
    if not await ensure_calculator_access_for_message(message):
        return

    data = await state.get_data()

    width = data.get("width")

    sections = get_available_sections(width)

    current = sections[index]

    text = (
        f"📦 <b>Оберіть кількість секцій</b>\n\n"

        f"Кількість секцій: "
        f"<b>{current['count']}</b>\n\n"

        f"Ширина секції:\n"
        f"<b>{current['section_width']} мм</b>"
    )

    photo = FSInputFile(current["image"])

    await message.answer_photo(
        photo=photo,
        caption=text,
        parse_mode="HTML",
        reply_markup=sections_keyboard(
            current_index=index,
            total=len(sections)
        )
    )

    await state.update_data(
        sections_variants=sections,
        section_index=index
    )

    await state.set_state(Form.choose_sections)

# =====================================================
# PREV SECTION
# =====================================================

@router.callback_query(F.data.startswith("sec_prev_"))
async def prev_section(callback: CallbackQuery, state: FSMContext):
    if not await ensure_calculator_access_for_callback(callback):
        return

    data = await state.get_data()

    sections = data["sections_variants"]

    try:

        index = int(
            callback.data.split("_")[-1]
        )

    except ValueError:

        await callback.answer(
            "❌ Помилка callback"
        )

        return

    index -= 1

    if index < 0:
        index = len(sections) - 1

    current = sections[index]

    media = InputMediaPhoto(
        media=FSInputFile(current["image"]),
        caption=(
            f"📦 <b>Оберіть кількість секцій</b>\n\n"

            f"Кількість секцій: "
            f"<b>{current['count']}</b>\n\n"

            f"Ширина секції:\n"
            f"<b>{current['section_width']} мм</b>"
        ),
        parse_mode="HTML"
    )

    await callback.message.edit_media(
        media=media,
        reply_markup=sections_keyboard(
            current_index=index,
            total=len(sections)
        )
    )

    await callback.answer()

# =====================================================
# NEXT SECTION
# =====================================================

@router.callback_query(F.data.startswith("sec_next_"))
async def next_section(callback: CallbackQuery, state: FSMContext):
    if not await ensure_calculator_access_for_callback(callback):
        return

    data = await state.get_data()

    sections = data["sections_variants"]

    try:

        index = int(
            callback.data.split("_")[-1]
        )

    except ValueError:

        await callback.answer(
            "❌ Помилка callback"
        )

        return

    index += 1

    if index >= len(sections):
        index = 0

    current = sections[index]

    media = InputMediaPhoto(
        media=FSInputFile(current["image"]),
        caption=(
            f"📦 <b>Оберіть кількість секцій</b>\n\n"

            f"Кількість секцій: "
            f"<b>{current['count']}</b>\n\n"

            f"Ширина секції:\n"
            f"<b>{current['section_width']} мм</b>"
        ),
        parse_mode="HTML"
    )

    await callback.message.edit_media(
        media=media,
        reply_markup=sections_keyboard(
            current_index=index,
            total=len(sections)
        )
    )

    await callback.answer()


# =====================================================
# ВИБІР СЕКЦІЇ
# =====================================================

@router.callback_query(F.data.startswith("select_section_"))
async def select_section(callback: CallbackQuery, state: FSMContext):
    if not await ensure_calculator_access_for_callback(callback):
        return

    data = await state.get_data()

    sections = data["sections_variants"]

    try:

        index = int(
            callback.data.split("_")[-1]
        )

    except ValueError:

        await callback.answer(
            "❌ Помилка callback"
        )

        return

    current = sections[index]

    await state.update_data(
        sections_count=current["count"],
        drawers_config=[],
        current_section=1
    )

    await callback.message.delete()

    await callback.message.answer(
        f"✅ Обрано секцій: "
        f"<b>{current['count']}</b>",
        parse_mode="HTML"
    )

    from handlers.drawers import (
        show_drawers
    )

    await show_drawers(
        callback.message,
        state,
        index=0
    )

    await callback.answer()
