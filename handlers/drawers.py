from aiogram import Router, F

from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InputMediaPhoto
)

from aiogram.fsm.context import FSMContext

from forms.user import Form
from keyboards.inline import (
    drawers_keyboard,
    drawer_bottom_carousel,
    DRAWER_BOTTOMS
)
from services.callback_lock import (
    acquire_lock,
    release_lock
)
from core.geometry.drawers import (
    calculate_drawer_geometry
)
from core.validation.drawers import (
    validate_drawers_configuration
)
import logging
import os
from services.telegram_access_service import (
    ensure_calculator_access_for_message,
    ensure_calculator_access_for_callback,
)

router = Router()




# =====================================================
# ДОСТУПНІ ШУХЛЯДИ
# =====================================================

def get_available_drawers(height: int):

    result = []

    for drawers in [2, 3, 4, 5, 6]:

        geometry = calculate_drawer_geometry(

            cabinet_height=height,

            drawers_count=drawers
        )

        drawer_height = geometry[
            "drawer_height"
        ]

        # мінімум 120 мм
        validation = validate_drawers_configuration(

            cabinet_height=height,

            drawers_count=drawers
        )

        if validation["success"]:

            result.append({

                "count": drawers,

                "drawer_height": drawer_height,

                "image": (
                    f"images/drawers/"
                    f"drawers_{drawers}.jpg"
                )
            })

    return result

async def show_drawers(message, state, index=0):
    if not await ensure_calculator_access_for_message(message):
        return

    data = await state.get_data()

    height = data.get("height")

    if not height:

        await message.answer(
            "❌ Не знайдена висота"
        )

        return

    current_section = data.get(
        "current_section",
        1
    )

    sections_count = data.get(
        "sections_count",
        1
    )

    variants = get_available_drawers(height)

    # =====================================
    # НЕМАЄ ВАРІАНТІВ
    # =====================================

    if not variants:

        await message.answer(
            "❌ Для цієї висоти немає доступних шухляд"
        )

        return

    # =====================================
    # ЗАХИСТ ІНДЕКСУ
    # =====================================

    if index >= len(variants):

        index = 0

    current = variants[index]

    image_path = os.path.join(
        "images",
        "drawers",
        f"drawers_{current['count']}.jpg"
    )

    logging.info(f"DRAWER IMAGE: {image_path}")

    logging.info(
        f"IMAGE EXISTS: {os.path.exists(image_path)}"
    )

    text = (

        f"🗄 <b>Секція "
        f"{current_section} з {sections_count}</b>\n\n"

        f"Шухляд:\n"
        f"<b>{current['count']}</b>\n\n"

        f"Висота шухляди:\n"
        f"<b>{current['drawer_height']} мм</b>"
    )

    await message.answer_photo(

        photo=FSInputFile(image_path),

        caption=text,

        parse_mode="HTML",

        reply_markup=drawers_keyboard(
            current_index=index,
            total=len(variants)
        )
    )

    await state.update_data(
        drawers_variants=variants
    )

    await state.set_state(
        Form.choose_drawers
    )

# =====================================================
# PREV DRAWER
# =====================================================

@router.callback_query(F.data.startswith("draw_prev_"))
async def prev_drawer(callback: CallbackQuery, state: FSMContext):
    if not await ensure_calculator_access_for_callback(callback):
        return

    data = await state.get_data()

    variants = data["drawers_variants"]

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
        index = len(variants) - 1

    current = variants[index]

    media = InputMediaPhoto(
        media=FSInputFile(current["image"]),
        caption=(
            f"🗄 <b>Оберіть кількість шухляд</b>\n\n"

            f"Шухляд:\n"
            f"<b>{current['count']}</b>\n\n"

            f"Висота:\n"
            f"<b>{current['drawer_height']} мм</b>"
        ),
        parse_mode="HTML"
    )

    await callback.message.edit_media(
        media=media,
        reply_markup=drawers_keyboard(
            current_index=index,
            total=len(variants)
        )
    )
    await callback.answer()


# =====================================================
# NEXT DRAWER
# =====================================================

@router.callback_query(F.data.startswith("draw_next_"))
async def next_drawer(callback: CallbackQuery, state: FSMContext):
    if not await ensure_calculator_access_for_callback(callback):
        return

    data = await state.get_data()

    variants = data["drawers_variants"]

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

    if index >= len(variants):
        index = 0

    current = variants[index]

    media = InputMediaPhoto(
        media=FSInputFile(current["image"]),
        caption=(
            f"🗄 <b>Оберіть кількість шухляд</b>\n\n"

            f"Шухляд:\n"
            f"<b>{current['count']}</b>\n\n"

            f"Висота:\n"
            f"<b>{current['drawer_height']} мм</b>"
        ),
        parse_mode="HTML"
    )

    await callback.message.edit_media(
        media=media,
        reply_markup=drawers_keyboard(
            current_index=index,
            total=len(variants)
        )
    )

    await callback.answer()


# =====================================================
# ВИБІР ШУХЛЯД
# =====================================================

@router.callback_query(F.data.startswith("select_drawers_"))
async def select_drawers(
    callback: CallbackQuery,
    state: FSMContext
):
    if not await ensure_calculator_access_for_callback(callback):
        return

    data = await state.get_data()

    lock = await acquire_lock(

        callback.from_user.id,

        "select_drawers"
    )

    if not lock:

        await callback.answer(
            "⏳ Зачекайте..."
        )

        return

    try:

        variants = data.get(
            "drawers_variants",
            []
        )

        if not variants:

            await callback.answer(
                "❌ Немає варіантів",
                show_alert=True
            )

            return

        index = int(
            callback.data.split("_")[-1]
        )

        if index >= len(variants):

            index = 0

        current = variants[index]

        drawers_config = data.get(
            "drawers_config",
            []
        )

        drawers_config.append(
            current["count"]
        )

        current_section = data.get(
            "current_section",
            1
        )

        sections_count = data.get(
            "sections_count",
            1
        )

        msg = callback.message

        # =====================================
        # ВИДАЛЯЄМО КАРУСЕЛЬ
        # =====================================

        try:
            await msg.delete()
        except Exception as e:
            logging.info(f"DELETE ERROR: {e}")

        # =====================================
        # SUCCESS
        # =====================================

        await msg.answer(

            f"✅ Секція "
            f"{current_section}: "
            f"{current['count']} шухляд"
        )

        current_section += 1

        # =====================================
        # ЩЕ Є СЕКЦІЇ
        # =====================================

        if current_section <= sections_count:

            await state.update_data(

                drawers_config=drawers_config,

                current_section=current_section
            )

            await show_drawers(
                msg,
                state,
                index=0
            )

            await callback.answer()

            return

        # =====================================
        # ВСЕ ГОТОВО
        # =====================================

        params = dict(
            data.get("params", {})
        )

        params["sections"] = sections_count

        params["facade_type"] = "inset"

        await state.update_data(

            drawers_config=drawers_config,

            params=params
        )

        await msg.answer(

            f"✅ Конфігурацію створено\n\n"

            f"Секцій: {sections_count}\n"

            f"Шухляди: {drawers_config}"
        )

        # =====================================
        # КАРУСЕЛЬ ДНА
        # =====================================

        index = 0

        bottom = DRAWER_BOTTOMS[index]

        photo = FSInputFile(bottom["img"])

        await msg.answer_photo(

            photo=photo,

            caption=(

                "🗃 <b>Оберіть тип дна шухляди</b>\n\n"

                f"{bottom['name']}\n\n"

                f"{bottom['desc']}"
            ),

            parse_mode="HTML",

            reply_markup=drawer_bottom_carousel(index)
        )

        await state.update_data(
            bottom_index=index
        )

        await state.set_state(
            Form.choose_drawer_bottom
        )

        await callback.answer()

    finally:

        await release_lock(
            callback.from_user.id,
            "select_drawers"
        )
