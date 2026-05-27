import aiohttp
import os

from io import BytesIO

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont


# =========================================
# РОЗМІРИ КАРТКИ
# =========================================

WIDTH = 420
HEIGHT = 300


# =========================================
# КОЛЬОРИ
# =========================================

BG = (255, 255, 255)

TEXT = (35, 35, 35)

GREEN = (17, 85, 65)

LINE = (230, 230, 230)


# =========================================
# ROOT ДИРЕКТОРІЯ ПРОЕКТУ
# =========================================

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)


# =========================================
# ЗАВАНТАЖЕННЯ АВАТАРКИ TELEGRAM
# =========================================

async def download_avatar(bot, user_id):

    try:

        photos = await bot.get_user_profile_photos(
            user_id=user_id,
            limit=1
        )

        if photos.total_count == 0:
            return None

        file_id = photos.photos[0][-1].file_id

        file = await bot.get_file(file_id)

        url = (
            f"https://api.telegram.org/file/"
            f"bot{bot.token}/{file.file_path}"
        )

        async with aiohttp.ClientSession() as session:

            async with session.get(url) as response:

                data = await response.read()

        avatar = Image.open(
            BytesIO(data)
        ).convert("RGBA")

        return avatar

    except Exception as e:

        print("AVATAR ERROR:", e)

        return None


# =========================================
# БЕЗПЕЧНЕ ЗАВАНТАЖЕННЯ PNG
# =========================================

def load_png(path, size=None):

    try:

        image = Image.open(path).convert("RGBA")

        if size:
            image = image.resize(size)

        return image

    except Exception as e:

        print("PNG LOAD ERROR:", path, e)

        return None


# =========================================
# ГЕНЕРАЦІЯ КАРТКИ
# =========================================

async def build_profile_card(
    bot,
    user_id,
    name,
    phone,
    city,
    email
):

    # =====================================
    # БАЗОВА КАРТКА
    # =====================================

    card = Image.new(
        "RGB",
        (WIDTH, HEIGHT),
        BG
    )

    draw = ImageDraw.Draw(card)

    # =====================================
    # ШРИФТИ
    # =====================================

    try:
        # Заголовок
        # 24 = розмір шрифту

        title_font = ImageFont.truetype(
            "arialbd.ttf",
            24
        )
        # Назви полів:
        # Ім'я, Телефон...
        label_font = ImageFont.truetype(
            "arialbd.ttf",
            18
        )
        # Значення:
        # Сергій, Київ...
        value_font = ImageFont.truetype(
            "arial.ttf",
            15
        )

    except:

        title_font = ImageFont.load_default()
        label_font = ImageFont.load_default()
        value_font = ImageFont.load_default()

    # =====================================
    # АВАТАРКА TELEGRAM
    # =====================================

    avatar = await download_avatar(
        bot,
        user_id
    )
    # РОЗМІР АВАТАРКИ
    # Більше число = більша картинка
    avatar_size = 100

    if avatar:

        avatar = avatar.resize(
            (avatar_size, avatar_size)
        )
        # Робимо круглу маску
        mask = Image.new(
            "L",
            (avatar_size, avatar_size),
            0
        )

        mask_draw = ImageDraw.Draw(mask)

        mask_draw.ellipse(
            (0, 0, avatar_size, avatar_size),
            fill=255
        )

        avatar.putalpha(mask)

        # =================================
        # ПОЗИЦІЯ АВАТАРКИ
        # =================================

        # (X, Y)

        # X = ліво / право
        # Y = верх / низ

        # Наприклад:
        # (120, 40)
        # → лівіше і нижче
        card.paste(
            avatar,
            (30, 130),
            avatar
        )

    # =====================================
    # ЗАГОЛОВОК
    # =====================================
    # (X, Y)

    # X = ліво / право
    # Y = верх / низ
    draw.text(
        (145, 30),
        "Профіль\nкористувача",
        fill=TEXT,
        font=title_font
    )

    # =====================================
    # ЛІНІЯ
    # =====================================

    # (x1, y1, x2, y2)

    # x1 = початок
    # x2 = кінець
    # y = висота

    draw.line(
        (35, 100, 355, 100),
        fill=LINE,
        width=2
    )

    # =====================================
    # ЛОГО
    # =====================================

    logo_path = os.path.join(
        BASE_DIR,
        "images",
        "logo.png"
    )
    # Розмір logo
    logo = load_png(
        logo_path,
        (60, 60)
    )

    if logo:
        # Координати logo
        card.paste(
            logo,
            (55, 25),
            logo
        )

    # =====================================
    # ДАНІ
    # =====================================

    rows = [

        (
            "Ім'я",
            name,
            "user.png"
        ),

        (
            "Телефон",
            phone,
            "phone.png"
        ),

        (
            "Місто",
            city,
            "city.png"
        ),
        # [:16] = обрізати email до 16 символів
        # Якщо треба більше:
        # email[:22]
        (
            "Email",
            email[:28],
            "email.png"
        )
    ]

    # =====================================
    # ПОЗИЦІЇ
    # =====================================

    # ІКОНКА
    # ліво / право
    x_icon = 180

    # НАЗВА ПОЛЯ
    # Ім'я:
    # Телефон:
    x_label = 145

    # ЗНАЧЕННЯ
    # Сергій
    # +380...
    x_value = 210

    # Початок блоку по вертикалі
    # Чим більше число:
    # тим нижче починається список
    y = 120

    # =====================================
    # РЯДКИ
    # =====================================

    for label, value, icon_file in rows:

        icon_path = os.path.join(
            BASE_DIR,
            "images",
            "icons",
            icon_file
        )

        icon = load_png(
            icon_path,
            (18, 18)
        )

        if icon:

            card.paste(
                icon,
                (x_icon, y + 2),
                icon
            )

        # Назва поля

        # draw.text(
        #     (x_label, y),
        #     f"{label}:",
        #     fill=TEXT,
        #     font=label_font
        # )

        # Значення

        draw.text(
            (x_value, y),
            str(value),
            fill=GREEN,
            font=value_font
        )
        # =================================
        # ВІДСТУП МІЖ РЯДКАМИ
        # =================================

        # Більше:
        # y += 70

        # Менше:
        # y += 40
        y += 40

    # =====================================
    # ЗБЕРЕЖЕННЯ
    # =====================================

    output_path = os.path.join(
        BASE_DIR,
        "profile_card.png"
    )

    card.save(output_path)

    return output_path