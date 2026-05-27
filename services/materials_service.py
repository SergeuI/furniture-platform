from aiogram.types import (
    FSInputFile,
    InputMediaPhoto
)

import aiohttp
import tempfile


# =====================================================
# RESOLVE MATERIAL PHOTO
# =====================================================

async def resolve_material_photo(
    photo
):

    if not photo:
        return None

    # =====================================
    # TELEGRAM FILE_ID
    # =====================================

    if (
        isinstance(photo, str)
        and photo.startswith("AgAC")
    ):

        return photo

    # =====================================
    # HTTP IMAGE
    # =====================================

    elif (
        isinstance(photo, str)
        and photo.startswith("http")
    ):

        async with aiohttp.ClientSession() as session:

            async with session.get(photo) as resp:

                if resp.status != 200:
                    return None

                data = await resp.read()

        tmp = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".jpg"
        )

        tmp.write(data)
        tmp.close()

        return FSInputFile(tmp.name)

    # =====================================
    # LOCAL FILE
    # =====================================

    elif isinstance(photo, str):

        return FSInputFile(photo)

    return photo


# =====================================================
# BUILD MATERIAL MEDIA
# =====================================================

async def build_material_media(

    material_data,

    title
):

    photo = (
        material_data.get("tg_file_id")
        or material_data.get("image")
    )

    media_photo = await resolve_material_photo(
        photo
    )

    if not media_photo:
        return None

    return InputMediaPhoto(

        media=media_photo,

        caption=(
            f"{title}"
            f"{material_data['name']}\n"
            f"💰 {material_data['price']} грн"
        )
    )