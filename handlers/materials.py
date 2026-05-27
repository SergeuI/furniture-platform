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

from keyboards.inline import (

    MATERIAL_TYPES,
    MATERIALS,

    material_keyboard,
    material_type_keyboard
)

from keyboards.ReplyKeyboard import (
    handles_keyboard
)

from services.viyar_parser import (
    CITY_MAP
)

from services.materials_service import (

    build_material_media,
    resolve_material_photo
)

from services.fittings_service import (
    build_fitting_media
)

from services.material_db import (

    get_user_city,
    get_material_with_price
)


router = Router()

HANDLES_ARTICLES = [

    "117213",
    "213752",
    "11728",
    "69690"
]



# ОКРЕМА ФУНКЦІЯ
async def show_material_types(message: Message, state: FSMContext):
    index = 0
    mat = MATERIAL_TYPES[index]
    photo = FSInputFile(mat["img"])

    await message.answer_photo(
        photo=photo,
        caption=f"🎨 Оберіть варіант:\n\n{mat['name']}",
        reply_markup=material_type_keyboard(index)
    )

    await state.update_data(mtype_index=index)
    await state.set_state(Form.material_type)   


async def show_materials(message: Message, state: FSMContext):

    index = 0

    data = await state.get_data()

    material_step = data.get("material_step", "single")

    city_raw = await get_user_city(message.from_user.id)

    if not city_raw:
        logging.info("❌ CITY NOT FOUND → FORCE DEFAULT kyiv")
        city_raw = "Київ"

    city = CITY_MAP.get(city_raw, "kyiv")

    logging.info(f"RAW CITY: {city_raw}")
    logging.info(f"FINAL CITY: {city}")

    mat = MATERIALS[index]

    material_data = await get_material_with_price(
        mat["article"],
        city
    )

    if not material_data:
        await message.answer("❌ Матеріал не знайдено")
        return

    photo = (
        material_data.get("tg_file_id")
        or material_data.get("image")
    )

    if not photo:
        await message.answer("❌ Немає зображення")
        return

    media = await build_material_media(

        material_data=material_data,

        title=""
    )

    if not media:

        await message.answer(
            "❌ Не вдалося створити preview"
        )

        return
    # =====================================
    # ТЕКСТ ЗАЛЕЖНО ВІД ЕТАПУ
    # =====================================

    if material_step == "facade":

        title = (
            "🎨 Оберіть матеріал фасаду\n\n"
        )

    elif material_step == "inside":

        title = (
            "📦 Оберіть матеріал корпусу\n\n"
        )

    else:

        title = (
            "🎨 Оберіть матеріал\n\n"
        )

    media.caption = (

        f"{title}"
        f"{material_data['name']}\n"
        f"💰 {material_data['price']} грн"
    )

    await message.answer_photo(

        photo=media.media,

        caption=media.caption,

        reply_markup=material_keyboard(index)
    )
    await state.update_data(
        mat_index=index
    )

    await state.set_state(Form.material)


@router.callback_query(
    Form.material,
    F.data.startswith("mat_")
)

async def material_navigation(
    callback: CallbackQuery,
    state: FSMContext
):

    data = callback.data.split("_")

    action = data[1]

    index = int(data[2])

    # =====================================
    # НАВІГАЦІЯ
    # =====================================

    if action == "next":

        index = (
            index + 1
        ) % len(MATERIALS)

    elif action == "prev":

        index = (
            index - 1
        ) % len(MATERIALS)

    # =====================================
    # SELECT
    # =====================================

    elif action == "select":

        state_data = await state.get_data()

        material_step = state_data.get(
            "material_step",
            "single"
        )

        mat = MATERIALS[index]

        city_raw = await get_user_city(
            callback.from_user.id
        )

        if not city_raw:
            city_raw = "Київ"

        city = CITY_MAP.get(
            city_raw,
            "kyiv"
        )

        material_data = await get_material_with_price(
            mat["article"],
            city
        )

        if not material_data:

            await callback.message.answer(
                "❌ Матеріал не знайдено"
            )

            return

        # =================================
        # SINGLE
        # =================================

        if material_step == "single":

            await state.update_data(
                selected_material=mat["article"]
            )

            await callback.message.delete()

            await callback.message.answer(
                f"✅ Обрано матеріал:\n"
                f"{material_data['name']}\n"
                f"💰 {material_data['price']} грн"
            )

            data = await state.get_data()

            if data.get("has_handles"):

                await show_handles_carousel(
                    callback.message,
                    state
                )

                return

            from handlers.fittings import (
                show_fittings
            )

            await show_fittings(
                callback.message,
                state
            )

            return

        # =================================
        # ФАСАД
        # =================================

        elif material_step == "facade":

            await state.update_data(
                facade_material=mat["article"]
            )

            await callback.message.delete()

            await callback.message.answer(
                f"✅ Обрано фасад:\n"
                f"{material_data['name']}\n"
                f"💰 {material_data['price']} грн"
            )

            # ПЕРЕХІД ДО КОРПУСУ

            await state.update_data(
                material_step="inside"
            )

            await show_materials(
                callback.message,
                state
            )

            return

        # =================================
        # КОРПУС
        # =================================

        elif material_step == "inside":

            await state.update_data(
                inside_material=mat["article"]
            )

            await callback.message.delete()

            await callback.message.answer(
                f"✅ Обрано корпус:\n"
                f"{material_data['name']}\n"
                f"💰 {material_data['price']} грн"
            )

            data = await state.get_data()

            if data.get("has_handles"):

                await show_handles_carousel(
                    callback.message,
                    state
                )

                return

            from handlers.fittings import (
                show_fittings
            )

            await show_fittings(
                callback.message,
                state
            )

            return

    # =====================================
    # ПОКАЗ КАРУСЕЛІ
    # =====================================

    city_raw = await get_user_city(
        callback.from_user.id
    )

    if not city_raw:
        city_raw = "Київ"

    city = CITY_MAP.get(
        city_raw,
        "kyiv"
    )

    mat = MATERIALS[index]

    material_data = await get_material_with_price(
        mat["article"],
        city
    )

    if not material_data:

        await callback.message.answer(
            "❌ Матеріал не знайдено"
        )

        return

    photo = (
        material_data.get("tg_file_id")
        or material_data.get("image")
    )

    media = await build_material_media(

        material_data=material_data,

        title=""
    )

    if not media:

        await callback.answer(
            "❌ Не вдалося створити preview",
            show_alert=True
        )

        return

    state_data = await state.get_data()

    material_step = state_data.get(
        "material_step",
        "single"
    )

    # =====================================
    # ТЕКСТ
    # =====================================

    if material_step == "facade":

        title = "🎨 Матеріал фасаду\n\n"

    elif material_step == "inside":

        title = "📦 Матеріал корпусу\n\n"

    else:

        title = "🎨 Матеріал\n\n"

    

    media.caption = (

        f"{title}"
        f"{material_data['name']}\n"
        f"💰 {material_data['price']} грн"
    )

    await callback.message.edit_media(

        media=media,

        reply_markup=material_keyboard(index)
    )

    await state.update_data(
        mat_index=index
    )

    try:
        await callback.answer()
    except:
        pass

@router.callback_query(
    Form.material_type,
    F.data.startswith("mtype_")
)

async def material_type_navigation(
    callback: CallbackQuery,
    state: FSMContext
):

    data = callback.data.split("_")

    action = data[1]

    index = int(data[2])

    # =====================================
    # НАВІГАЦІЯ
    # =====================================

    if action == "next":

        index = (
            index + 1
        ) % len(MATERIAL_TYPES)

    elif action == "prev":

        index = (
            index - 1
        ) % len(MATERIAL_TYPES)

    # =====================================
    # ВИБІР
    # =====================================

    elif action == "select":

        mat = MATERIAL_TYPES[index]

        await state.update_data(
            material_type=mat["code"]
        )

        await callback.message.delete()

        await callback.message.answer(
            f"✅ Обрано: {mat['name']}"
        )

        # =================================
        # ОДИН МАТЕРІАЛ
        # =================================

        if mat["code"] == "single":

            await state.update_data(
                material_step="single"
            )

            await show_materials(
                callback.message,
                state
            )

        # =================================
        # ДВА МАТЕРІАЛИ
        # =================================

        else:

            await state.update_data(
                material_step="facade"
            )

            await show_materials(
                callback.message,
                state
            )

        try:
            await callback.answer()
        except:
            pass

        return

    # =====================================
    # ПОКАЗ КАРУСЕЛІ
    # =====================================

    mat = MATERIAL_TYPES[index]

    photo = FSInputFile(mat["img"])

    await callback.message.edit_media(

        InputMediaPhoto(
            media=photo,
            caption=(
                f"🎨 Оберіть варіант:\n\n"
                f"{mat['name']}"
                f"Варіант #{index + 1}"
            )
        ),

        reply_markup=material_type_keyboard(index)
    )

    await state.update_data(
        mtype_index=index
    )

    try:
        await callback.answer()
    except:
        pass



async def show_handles_carousel(message, state):
    index = 0
    city_raw = await get_user_city(message.from_user.id)
    city = CITY_MAP.get(city_raw, "kyiv")

    article = HANDLES_ARTICLES[index]
    material = await get_material_with_price(article, city)

    if not material:
        await message.answer("❌ Ручка не знайдена")
        return

    photo = (
        material.get("tg_file_id")
        or material.get("image")
    )
    media_photo = await resolve_material_photo(
        photo
    )

    if not media_photo:

        await message.answer(
            "❌ Не вдалося створити preview"
        )

        return

    await message.answer_photo(
        photo=media_photo,
        caption=f"{material['name']}\n💰 {material['price']} грн",
        reply_markup=handles_keyboard(index)
    )

    await state.update_data(handle_index=index)

# Обробник каруселі ручек для комода
@router.callback_query(F.data.startswith("handle_"))
async def handles_navigation(callback: CallbackQuery, state: FSMContext):
    data = callback.data.split("_")
    action = data[1]
    index = int(data[2])

    if action == "next":
        index = (index + 1) % len(HANDLES_ARTICLES)
    elif action == "prev":
        index = (index - 1) % len(HANDLES_ARTICLES)
    elif action == "select":
        article = HANDLES_ARTICLES[index]
        city_raw = await get_user_city(callback.from_user.id)
        city = CITY_MAP.get(city_raw, "kyiv")

        material = await get_material_with_price(article, city)
        if not material:
            try:
                await callback.answer("❌ Ручка не знайдена", show_alert=True)
            except:
                pass
            return

        await callback.message.delete()
        await callback.message.answer(
            f"✅ Обрано ручку:\n{material['name']}\n💰 {material['price']} грн"
        )
        from handlers.fittings import (
            show_fittings
        )

        await show_fittings(
            callback.message,
            state
        )
        try:
            await callback.answer()
        except:
            pass
        return

    article = HANDLES_ARTICLES[index]
    city_raw = await get_user_city(callback.from_user.id)
    city = CITY_MAP.get(city_raw, "kyiv")

    material = await get_material_with_price(article, city)
    if not material:
        await callback.message.answer("❌ Ручка не знайдена")
        try:
            await callback.answer()
        except:
            pass
        return

    photo = (
        material.get("tg_file_id")
        or material.get("image")
    )

    media_photo = await resolve_material_photo(
        photo
    )

    if not media_photo:

        await callback.answer(
            "❌ Не вдалося створити preview",
            show_alert=True
        )

        return
       

    await callback.message.edit_media(
        InputMediaPhoto(
            media=media_photo,
            caption=f"{material['name']}\n💰 {material['price']} грн"
        ),
        reply_markup=handles_keyboard(index)
    )

    await state.update_data(handle_index=index)
    try:
        await callback.answer()
    except:
        pass

