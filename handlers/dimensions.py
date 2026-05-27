from aiogram import Router
from aiogram.types import (
    Message,
    FSInputFile
)
from aiogram.fsm.context import FSMContext

from forms.user import Form

import logging

router = Router()

# =====================================================
# CLEANUP
# =====================================================

async def cleanup_dimension_messages(
    message: Message,
    state: FSMContext
):

    data = await state.get_data()

    ids = data.get(
        "dimension_messages",
        []
    )

    ids.append(message.message_id)

    await state.update_data(
        dimension_messages=ids
    )

# =====================================================
# START DIMENSIONS FLOW
# =====================================================

async def start_dimensions_flow(
    message: Message,
    state: FSMContext
):

    photo = FSInputFile(
        "images/dresser_hint.jpg"
    )

    msg1 = await message.answer_photo(

        photo=photo,

        caption=(

            "📏 Підказка по габаритах\n\n"

            "↔️ Ширина — зліва направо\n"
            "↕️ Висота — знизу вверх\n"
            "↗️ Глибина — від фасаду назад"
        )
    )

    msg2 = await message.answer(

        "📏 Введіть ширину комоду\n\n"

        "Доступна ширина:\n"
        "300–2600 мм"
    )

    await state.update_data(

        dimension_messages=[

            msg1.message_id,
            msg2.message_id
        ]
    )

    await state.set_state(
        Form.width
    )

# =====================================================
# WIDTH
# =====================================================

@router.message(Form.width)
async def process_width(
    message: Message,
    state: FSMContext
):

    await cleanup_dimension_messages(
        message,
        state
    )

    try:

        width = int(
            message.text
            .replace("мм", "")
            .replace("mm", "")
            .strip()
        )

    except Exception:

        msg = await message.answer(

            "❌ Некоректна ширина\n\n"

            "Введіть число від "
            "300 до 2600 мм"
        )

        await cleanup_dimension_messages(
            msg,
            state
        )

        return

    if width < 300 or width > 2600:

        msg = await message.answer(

            "❌ Некоректна ширина\n\n"

            "Допустимо:\n"
            "300–2600 мм"
        )

        await cleanup_dimension_messages(
            msg,
            state
        )

        return

    await state.update_data(
        width=width
    )

    msg = await message.answer(

        "📏 Введіть висоту комоду\n\n"

        "Доступна висота:\n"
        "300–1500 мм"
    )

    await cleanup_dimension_messages(
        msg,
        state
    )

    await state.set_state(
        Form.height
    )

# =====================================================
# HEIGHT
# =====================================================

@router.message(Form.height)
async def process_height(
    message: Message,
    state: FSMContext
):

    await cleanup_dimension_messages(
        message,
        state
    )

    try:

        height = int(
            message.text
            .replace("мм", "")
            .replace("mm", "")
            .strip()
        )

    except Exception:

        msg = await message.answer(

            "❌ Некоректна висота\n\n"

            "Введіть число від "
            "300 до 1500 мм"
        )

        await cleanup_dimension_messages(
            msg,
            state
        )

        return

    if height < 300 or height > 1500:

        msg = await message.answer(

            "❌ Некоректна висота\n\n"

            "Допустимо:\n"
            "300–1500 мм"
        )

        await cleanup_dimension_messages(
            msg,
            state
        )

        return

    await state.update_data(
        height=height
    )

    msg = await message.answer(

        "📏 Введіть глибину комоду\n\n"

        "Доступна глибина:\n"
        "250–650 мм"
    )

    await cleanup_dimension_messages(
        msg,
        state
    )

    await state.set_state(
        Form.depth
    )

# =====================================================
# DEPTH
# =====================================================

@router.message(Form.depth)
async def process_depth(
    message: Message,
    state: FSMContext
):

    await cleanup_dimension_messages(
        message,
        state
    )

    try:

        depth = int(
            message.text
            .replace("мм", "")
            .replace("mm", "")
            .strip()
        )

    except Exception:

        msg = await message.answer(

            "❌ Некоректна глибина\n\n"

            "Введіть число від "
            "250 до 650 мм"
        )

        await cleanup_dimension_messages(
            msg,
            state
        )

        return

    if depth < 250 or depth > 650:

        msg = await message.answer(

            "❌ Некоректна глибина\n\n"

            "Допустимо:\n"
            "250–650 мм"
        )

        await cleanup_dimension_messages(
            msg,
            state
        )

        return

    await state.update_data(
        depth=depth
    )

    data = await state.get_data()

    width = data.get("width")

    height = data.get("height")

    ids = data.get(
        "dimension_messages",
        []
    )

    # =====================================================
    # CLEAN CHAT
    # =====================================================

    for msg_id in ids:

        try:

            await message.bot.delete_message(
                chat_id=message.chat.id,
                message_id=msg_id
            )

        except Exception as e:

            logging.info(
                f"DELETE ERROR: {e}"
            )

    # =====================================================
    # SUCCESS
    # =====================================================

    await message.answer(

        "✅ Габарити збережено\n\n"

        f"📏 Ширина: {width} мм\n"
        f"📏 Висота: {height} мм\n"
        f"📏 Глибина: {depth} мм"
    )

    from handlers.sections import (
        show_sections
    )

    await show_sections(
        message,
        state,
        index=0
    )