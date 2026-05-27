from aiogram.types import (
    BufferedInputFile,
    InputMediaPhoto
)

from services.mt_kits_parser import (
    get_kit_price
)

from services.database import (
    get_materials_by_category_and_length
)

import os
import aiohttp


# =========================================================
# BUILD MEDIA PHOTO
# =========================================================

async def build_media_photo(photo_path_or_url):

    # =====================================
    # URL
    # =====================================

    if (
        isinstance(photo_path_or_url, str)
        and photo_path_or_url.startswith("http")
    ):

        async with aiohttp.ClientSession() as session:

            async with session.get(photo_path_or_url) as resp:

                if resp.status != 200:
                    return None

                data = await resp.read()

        filename = os.path.basename(
            photo_path_or_url
        )

        if "." not in filename:
            filename += ".jpg"

        return BufferedInputFile(
            data,
            filename=filename
        )

    # =====================================
    # LOCAL FILE
    # =====================================

    with open(photo_path_or_url, "rb") as f:

        data = f.read()

    filename = os.path.basename(
        photo_path_or_url
    )

    return BufferedInputFile(
        data,
        filename=filename
    )


# =========================================================
# NORMALIZE FITTING
# =========================================================

async def normalize_fitting(
    item,
    city,
    drawer_count=1
):

    # =====================================
    # VIYAR
    # =====================================

    if item["type"] == "viyar":

        materials = await get_materials_by_category_and_length(
            item["category"],
            item["length"],
            city
        )

        if not materials:
            return None

        mat = materials[0]

        text = (
            f"{mat['name']}\n"
            f"💰 {mat['price']} грн\n\n"
            f"Варіант #1"
        )

        photo = (
            mat.get("tg_file_id")
            or mat.get("image")
        )

        return {
            "name": mat["name"],
            "price": mat["price"],
            "photo": photo,
            "text": text,
            "total_price": mat["price"]
        }

    # =====================================
    # MT KIT
    # =====================================

    else:

        kit = await get_kit_price(
            item["code"],
            city
        )

        if not kit:
            return None

        total_price = (
            kit["price"] * drawer_count
        )

        text = (
            f"{kit['name']}\n"
            f"💰 {kit['price']} грн x "
            f"{drawer_count}\n\n"
            f"🧮 Всього: "
            f"{round(total_price, 2)} грн\n\n"
            f"Варіант #1"
        )

        photo = (
            kit.get("tg_file_id")
            or kit.get("image")
        )

        return {
            "name": kit["name"],
            "price": kit["price"],
            "photo": photo,
            "text": text,
            "total_price": total_price
        }


# =========================================================
# RESOLVE FITTING PHOTO
# =========================================================

async def resolve_fitting_photo(
    photo
):

    if isinstance(photo, str):

        # =====================================
        # TELEGRAM FILE_ID
        # =====================================

        if photo.startswith("AgAC"):

            media_photo = photo

        # =====================================
        # URL / LOCAL FILE
        # =====================================

        else:

            media_photo = await build_media_photo(
                photo
            )

    else:

        media_photo = photo

    return media_photo


# =========================================================
# BUILD FITTING MEDIA
# =========================================================

async def build_fitting_media(
    item,
    city,
    index,
    drawer_count=1
):

    normalized = await normalize_fitting(
        item=item,
        city=city,
        drawer_count=drawer_count
    )

    if not normalized:
        return None

    photo = normalized["photo"]

    text = normalized["text"].replace(
        "Варіант #1",
        f"Варіант #{index + 1}"
    )

    if not photo:
        return None

    media_photo = await resolve_fitting_photo(
        photo
    )

    if not media_photo:
        return None

    return InputMediaPhoto(
        media=media_photo,
        caption=text
    )


# =========================================================
# CALCULATE SELECTED FITTING
# =========================================================

async def calculate_selected_fitting(
    selected,
    city,
    drawer_count
):

    # =====================================
    # VIYAR
    # =====================================

    if selected["type"] == "viyar":

        materials = await get_materials_by_category_and_length(
            selected["category"],
            selected["length"],
            city
        )

        if not materials:
            return None

        mat = materials[0]

        total_price = (
            mat["price"] * drawer_count
        )

        fitting_name = mat["name"]

        fitting_price = mat["price"]

    # =====================================
    # MT KIT
    # =====================================

    else:

        kit = await get_kit_price(
            selected["code"],
            city
        )

        if not kit:
            return None

        total_price = (
            kit["price"] * drawer_count
        )

        fitting_name = kit["name"]

        fitting_price = kit["price"]

    return {
        "name": fitting_name,
        "price": fitting_price,
        "total_price": total_price,
        "code": selected["code"]
    }