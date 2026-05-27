from aiogram import Router, F

from aiogram.types import (
    Message,
    CallbackQuery,
    FSInputFile,
    InputMediaPhoto
)

from aiogram.fsm.context import FSMContext

import logging

from forms.user import Form

from keyboards.inline import (
    fitting_carousel_keyboard,
    DRAWER_BOTTOMS,
    drawer_bottom_carousel
)

from services.viyar_parser import (
    CITY_MAP
)

from services.callback_lock import (
    acquire_lock
)

from services.fittings_service import (

    normalize_fitting,

    build_fitting_media,

    calculate_selected_fitting
)

from services.build_project_input import (
    build_project_input
)

from services.project_generation_service import (
    generate_project
)
from services.debug_export import (
    export_debug_bom
)

from services.project_storage_service import (
    save_project
)

from services.material_db import (
    get_user_city
)



router = Router()


# ✅ ОНОВЛЕНО: Миттєва карусель фурнітури з БД
async def show_fittings(message, state):

    data = await state.get_data()

    depth = data.get("depth")

    if not depth:

        await message.answer(
            "❌ Не знайдено глибину"
        )

        return

    has_tip_on = (
        data.get("sub_type") == "tipon"
    )

    from services.fittings_logic import (
        build_fittings
    )

    fittings = build_fittings(
        depth,
        has_tip_on
    )

    if not fittings:

        await message.answer(
            "❌ Немає фурнітури"
        )

        return

    city_raw = await get_user_city(
        message.from_user.id
    )

    city = CITY_MAP.get(
        city_raw,
        "kyiv"
    )

    await state.update_data(

        fittings=fittings,

        fit_index=0,

        city=city
    )

    # =====================================
    # ПЕРШИЙ ЕЛЕМЕНТ
    # =====================================

    item = fittings[0]

    drawers = data.get(
        "drawers_config",
        []
    )

    drawer_count = sum(drawers)

    normalized = await normalize_fitting(
        item=item,
        city=city,
        drawer_count=drawer_count
    )

    if not normalized:

        await message.answer(
            "❌ Не знайдено фурнітуру"
        )

        return

    media = await build_fitting_media(
        item=item,
        city=city,
        index=0,
        drawer_count=drawer_count
    )

    if not media:

        await message.answer(
            "❌ Не вдалося створити preview"
        )

        return

    # =====================================
    # CREATE FIRST MESSAGE
    # =====================================

    sent = await message.answer_photo(

        photo=media.media,

        caption=media.caption,

        reply_markup=fitting_carousel_keyboard()
    )

    await state.update_data(

        fit_index=0,

        fit_msg_id=sent.message_id,

        fit_chat_id=sent.chat.id
    )



async def show_one_fitting(message: Message, state: FSMContext):

    try:

        data = await state.get_data()

        fittings = data.get("fittings", [])

        if not fittings:

            await message.answer(
                "❌ Немає фурнітури"
            )
            return

        index = data.get("fit_index", 0)

        if index >= len(fittings):
            index = 0

        item = fittings[index]

        city_raw = await get_user_city(
            message.chat.id
        )

        city = CITY_MAP.get(
            city_raw,
            "kyiv"
        )

        media = await build_fitting_media(
            item=item,
            city=city,
            index=index
        )

        if not media:

            await message.answer(
                "❌ Не вдалося сформувати preview"
            )

            return

        fit_msg_id = data.get("fit_msg_id")

        # ==========================================
        # FIRST SEND
        # ==========================================

        if not fit_msg_id:

            sent = await message.answer_photo(

                photo=media.media,

                caption=media.caption,

                reply_markup=fitting_carousel_keyboard()
            )

            await state.update_data(

                fit_msg_id=sent.message_id,

                fit_chat_id=sent.chat.id
            )

        # ==========================================
        # EDIT EXISTING
        # ==========================================

        else:

            await message.bot.edit_message_media(

                chat_id=message.chat.id,

                message_id=fit_msg_id,

                media=media,

                reply_markup=fitting_carousel_keyboard()
            )

    except Exception as e:

        import traceback

        logging.error(
            traceback.format_exc()
        )

        await message.answer(
            f"❌ show_one_fitting ERROR\n\n{str(e)}"
        )

# обробка кнопок
@router.callback_query(F.data == "fit_next")
async def fit_next(callback: CallbackQuery, state: FSMContext):

    data = await state.get_data()

    fittings = data.get("fittings", [])

    if not fittings:

        await callback.answer()
        return

    index = data.get("fit_index", 0)

    index += 1

    if index >= len(fittings):
        index = 0

    await state.update_data(
        fit_index=index
    )

    await show_one_fitting(
        callback.message,
        state
    )

    await callback.answer()


@router.callback_query(F.data == "fit_prev")
async def fit_prev(callback: CallbackQuery, state: FSMContext):

    data = await state.get_data()

    fittings = data.get("fittings", [])

    if not fittings:

        await callback.answer()
        return

    index = data.get("fit_index", 0)

    index -= 1

    if index < 0:
        index = len(fittings) - 1

    await state.update_data(
        fit_index=index
    )

    await show_one_fitting(
        callback.message,
        state
    )

    await callback.answer()


# Обробник після вибору напрямних
@router.callback_query(F.data == "fit_select")
async def fit_select(callback: CallbackQuery, state: FSMContext):

    lock = await acquire_lock(

        callback.from_user.id,

        "fit_select"
    )

    if not lock:

        await callback.answer(
            "⏳ Прорахунок вже генерується..."
        )

        return

    try:

        data = await state.get_data()

        fittings = data.get("fittings", [])

        index = data.get("fit_index", 0)

        if not fittings:

            await callback.answer(
                "❌ Немає фурнітури",
                show_alert=True
            )

            return

        selected = fittings[index]

        city_raw = await get_user_city(
            callback.from_user.id
        )

        city = CITY_MAP.get(
            city_raw,
            "kyiv"
        )

        drawers = data.get(
            "drawers_config",
            []
        )

        drawer_count = sum(drawers)

        result = await calculate_selected_fitting(
            selected=selected,
            city=city,
            drawer_count=drawer_count
        )

        if not result:

            await callback.message.answer(
                "❌ Не вдалося прорахувати фурнітуру"
            )

            return

        fitting_name = result["name"]

        fitting_price = result["price"]

        total_price = result["total_price"]

        await state.update_data(

            selected_fitting={

                "name": fitting_name,

                "price": fitting_price,

                "total_price": total_price,

                "drawer_count": drawer_count,

                "code": result.get(
                    "code",
                    selected.get("code", "unknown")
                )
            }
        )

        text = (

            f"✅ Обрано напрямні:\n"

            f"{fitting_name}\n"

            f"💰 {fitting_price} грн x "
            f"{drawer_count}\n\n"

            f"🧮 Всього: "
            f"{round(total_price, 2)} грн\n\n"

            f"Варіант #{index + 1}"
        )

        try:

            await callback.message.delete()

        except Exception as e:

            logging.info(
                f"DELETE FITTING MESSAGE ERROR: {e}"
            )

        await callback.message.answer(text)

        project_input = await build_project_input(
            state
        )

        generation_result = await generate_project(
            project_input
        )

        if not generation_result.success:

            await callback.message.answer(

                "❌ Помилки проекту:\n\n"
                + "\n".join(
                    generation_result.errors
                )
            )

            return

        status_msg = await callback.message.answer(

            "⏳ Генеруємо проект..."
        )

        try:

            # =====================================
            # TEMP STUB RESULT
            # =====================================

            result = generation_result.result

            project = result.get(
                "project",
                {}
            )

            cutting = result.get(
                "cutting",
                {}
            )

            if not project:

                project = {
                    "details": []
                }

            if not cutting:

                cutting = {

                    "area": 0,

                    "cut": 0,

                    "edge_04": 0,

                    "edge_08": 0
                }

        except Exception as e:

            try:

                await status_msg.delete()

            except Exception as e:

                logging.error(
                    f"ERROR: {e}"
                )

            import traceback

            error = traceback.format_exc()

            logging.info(error)

            await callback.message.answer(

                "❌ Помилка генерації прорахунку\n\n"
                f"{str(e)}"
            )

            return

        project_id = await save_project(

            telegram_id=callback.from_user.id,

            params=project_input.model_dump(),

            project=project,

            cutting=cutting
        )

        debug_file = export_debug_bom(

            project_id,

            project
        )

        await state.update_data(

            project_id=project_id
        )

        details_count = len(
            project.get("details", [])
        )

        cutting_area = cutting.get(
            "area",
            0
        )

        cutting_cut = cutting.get(
            "cut",
            0
        )

        edge_04 = cutting.get(
            "edge_04",
            0
        )

        edge_08 = cutting.get(
            "edge_08",
            0
        )

        logging.info(f"CUTTING: {cutting}")

        await callback.message.answer(
            f"✅ Прорахунок створено\n\n"

            f"🆔 Project ID:\n"
            f"{project_id}\n\n"

            f"📦 Деталей: {details_count}\n"

            f"📐 Площа: "
            f"{cutting_area} м²\n"

            f"✂️ Різ: "
            f"{cutting_cut} п.м.\n"

            f"🟤 Крайка 0.4:\n"
            f"{edge_04} п.м.\n"

            f"⚫ Крайка 0.8:\n"
            f"{edge_08} п.м."
        )

        debug_document = FSInputFile(
            debug_file
        )

        await callback.message.answer_document(

            debug_document,

            caption=(
                "📦 DEBUG BOM EXPORT"
            )
        )

        logging.info(edge_04)
        logging.info(edge_08)

        await state.clear()

        await callback.answer()

    except Exception as e:

        import traceback

        logging.error(
            traceback.format_exc()
        )

        await callback.message.answer(
            f"❌ fit_select ERROR\n\n{str(e)}"
        )

    finally:

        from services.callback_lock import (
            release_lock
        )

        await release_lock(

            callback.from_user.id,

            "fit_select"
        )

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

        bottom_type=bottom["code"]
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