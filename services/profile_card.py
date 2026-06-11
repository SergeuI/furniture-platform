import os
from io import BytesIO

import aiohttp
from PIL import Image, ImageDraw, ImageFont


WIDTH = 880
HEIGHT = 500

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_PATH = os.path.join(BASE_DIR, "profile_card.png")

GRAPHITE_950 = (13, 20, 26)
GRAPHITE_900 = (17, 24, 32)
GRAPHITE_800 = (32, 41, 50)
STEEL_500 = (102, 113, 123)
STEEL_300 = (168, 177, 186)
SURFACE = (247, 250, 252)
SURFACE_CARD = (255, 255, 255)
LINE = (223, 231, 238)
TEXT_DARK = (31, 41, 55)
TEXT_MUTED = (93, 109, 126)
ACCENT = (57, 211, 83)
ACCENT_DARK = (31, 170, 40)

CARD_RADIUS = 26
PANEL_RADIUS = 20
HEADER_HEIGHT = 88
AVATAR_SIZE = 118

try:
    RESAMPLE = Image.Resampling.LANCZOS
except AttributeError:
    RESAMPLE = Image.LANCZOS


def rounded_mask(size, radius):
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, size[0], size[1]),
        radius=radius,
        fill=255,
    )
    return mask


def fit_text(value, limit):
    if not value:
        return "-"
    text = str(value).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def normalize_role(role):
    value = (role or "").strip().lower()
    mapping = {
        "guest": ("Гість", (244, 247, 250), (196, 205, 214), TEXT_MUTED),
        "user": ("Користувач", (232, 249, 236), (186, 233, 195), ACCENT_DARK),
        "pro": ("PRO", (232, 244, 255), (180, 211, 244), (22, 94, 166)),
        "admin": ("ADMIN", (245, 239, 255), (219, 198, 255), (99, 44, 177)),
    }
    return mapping.get(value, ("Користувач", (232, 249, 236), (186, 233, 195), ACCENT_DARK))


def load_font(size, bold=False):
    candidates = []
    if bold:
        candidates.extend(
            [
                "C:\\Windows\\Fonts\\seguisb.ttf",
                "C:\\Windows\\Fonts\\segoeuib.ttf",
                "C:\\Windows\\Fonts\\arialbd.ttf",
            ]
        )
    else:
        candidates.extend(
            [
                "C:\\Windows\\Fonts\\segoeui.ttf",
                "C:\\Windows\\Fonts\\arial.ttf",
            ]
        )

    for candidate in candidates:
        if os.path.exists(candidate):
            try:
                return ImageFont.truetype(candidate, size)
            except OSError:
                pass

    return ImageFont.load_default()


def load_png(path, size=None):
    try:
        image = Image.open(path).convert("RGBA")
        if size:
            image = image.resize(size, RESAMPLE)
        return image
    except Exception as exc:
        print("PNG LOAD ERROR:", path, exc)
        return None


async def download_avatar(bot, user_id):
    try:
        photos = await bot.get_user_profile_photos(user_id=user_id, limit=1)
        if photos.total_count == 0:
            return None

        file_id = photos.photos[0][-1].file_id
        file = await bot.get_file(file_id)
        url = f"https://api.telegram.org/file/bot{bot.token}/{file.file_path}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                data = await response.read()

        return Image.open(BytesIO(data)).convert("RGBA")
    except Exception as exc:
        print("AVATAR ERROR:", exc)
        return None


def draw_label_value(draw, x, y, label, value, label_font, value_font):
    draw.text((x, y), label, fill=TEXT_MUTED, font=label_font)
    draw.text((x, y + 24), value, fill=TEXT_DARK, font=value_font)


async def build_profile_card(bot, user_id, name, phone, city, email, role=None):
    card = Image.new("RGBA", (WIDTH, HEIGHT), SURFACE)
    card_mask = rounded_mask((WIDTH, HEIGHT), CARD_RADIUS)

    shell = Image.new("RGBA", (WIDTH, HEIGHT), SURFACE_CARD)
    shell_draw = ImageDraw.Draw(shell)
    shell_draw.rounded_rectangle(
        (0, 0, WIDTH - 1, HEIGHT - 1),
        radius=CARD_RADIUS,
        fill=SURFACE_CARD,
        outline=LINE,
        width=1,
    )

    header = Image.new("RGBA", (WIDTH, HEADER_HEIGHT), SURFACE_CARD)
    header_draw = ImageDraw.Draw(header)
    header_draw.rounded_rectangle(
        (0, 0, WIDTH - 1, HEADER_HEIGHT + CARD_RADIUS),
        radius=CARD_RADIUS,
        fill=SURFACE_CARD,
    )
    header_draw.rectangle((0, 0, WIDTH, 8), fill=ACCENT)
    shell.alpha_composite(header, (0, 0))

    title_font = load_font(30, bold=True)
    subtitle_font = load_font(17)
    section_font = load_font(16, bold=True)
    label_font = load_font(15)
    value_font = load_font(22, bold=True)
    detail_font = load_font(17)
    badge_font = load_font(15, bold=True)

    logo = load_png(
        os.path.join(BASE_DIR, "branding", "logo", "mproject-logo-reference.jpg"),
        size=(210, 48),
    )
    if logo:
        shell.alpha_composite(logo, (34, 24))

    shell_draw.text(
        (268, 22),
        "Профіль користувача",
        fill=TEXT_DARK,
        font=title_font,
    )
    shell_draw.text(
        (268, 56),
        "Персональні дані в MProject.furniture",
        fill=TEXT_MUTED,
        font=subtitle_font,
    )

    role_title, role_fill, role_outline, role_text = normalize_role(role)
    role_badge = (WIDTH - 182, 24, WIDTH - 34, 58)
    shell_draw.rounded_rectangle(role_badge, radius=17, fill=role_fill, outline=role_outline)
    badge_text_box = shell_draw.textbbox((0, 0), role_title, font=badge_font)
    badge_text_width = badge_text_box[2] - badge_text_box[0]
    shell_draw.text(
        (role_badge[0] + ((role_badge[2] - role_badge[0] - badge_text_width) / 2), role_badge[1] + 8),
        role_title,
        fill=role_text,
        font=badge_font,
    )

    content_top = HEADER_HEIGHT + 22

    left_panel = (28, content_top, 290, HEIGHT - 28)
    right_panel = (334, content_top, WIDTH - 28, HEIGHT - 28)

    shell_draw.rounded_rectangle(left_panel, radius=PANEL_RADIUS, fill=(248, 251, 253), outline=LINE)
    shell_draw.rounded_rectangle(right_panel, radius=PANEL_RADIUS, fill=(250, 252, 254), outline=LINE)

    avatar = await download_avatar(bot, user_id)
    avatar_x = left_panel[0] + 69
    avatar_y = left_panel[1] + 34
    avatar_bg_box = (avatar_x - 12, avatar_y - 12, avatar_x + AVATAR_SIZE + 12, avatar_y + AVATAR_SIZE + 12)
    shell_draw.ellipse(avatar_bg_box, fill=(235, 243, 248), outline=(220, 229, 236))

    if avatar:
        avatar = avatar.resize((AVATAR_SIZE, AVATAR_SIZE), RESAMPLE)
        avatar.putalpha(rounded_mask((AVATAR_SIZE, AVATAR_SIZE), AVATAR_SIZE // 2))
        shell.alpha_composite(avatar, (avatar_x, avatar_y))
    else:
        symbol = load_png(
            os.path.join(BASE_DIR, "branding", "logo", "mp-symbol-reference.jpg"),
            size=(92, 92),
        )
        if symbol:
            shell.alpha_composite(symbol, (avatar_x + 13, avatar_y + 13))

    shell_draw.text(
        (left_panel[0] + 36, avatar_y + AVATAR_SIZE + 24),
        fit_text(name, 24),
        fill=TEXT_DARK,
        font=value_font,
    )
    shell_draw.text(
        (left_panel[0] + 36, avatar_y + AVATAR_SIZE + 60),
        "Активний профіль платформи",
        fill=TEXT_MUTED,
        font=detail_font,
    )

    badge_box = (left_panel[0] + 36, avatar_y + AVATAR_SIZE + 108, left_panel[0] + 212, avatar_y + AVATAR_SIZE + 146)
    shell_draw.rounded_rectangle(badge_box, radius=18, fill=(232, 249, 236), outline=(186, 233, 195))
    shell_draw.text((badge_box[0] + 18, badge_box[1] + 9), "Профіль синхронізовано", fill=ACCENT_DARK, font=badge_font)

    shell_draw.text((right_panel[0] + 26, right_panel[1] + 22), "Контактні дані", fill=TEXT_DARK, font=section_font)

    row_top = right_panel[1] + 58
    row_gap = 56
    icon_size = 24
    icons = {
        "Ім'я": "user.png",
        "Телефон": "phone.png",
        "Місто": "city.png",
        "Email": "email.png",
    }
    rows = [
        ("Ім'я", fit_text(name, 32)),
        ("Телефон", fit_text(phone, 24)),
        ("Місто", fit_text(city, 24)),
        ("Email", fit_text(email, 34)),
    ]

    list_left = right_panel[0] + 22
    list_right = right_panel[2] - 22
    list_top = row_top - 10
    list_bottom = row_top + ((len(rows) - 1) * row_gap) + 44
    shell_draw.rounded_rectangle(
        (list_left, list_top, list_right, list_bottom),
        radius=18,
        fill=(255, 255, 255),
        outline=(228, 235, 240),
    )

    for index, (label, value) in enumerate(rows):
        y = row_top + index * row_gap
        icon = load_png(os.path.join(BASE_DIR, "images", "icons", icons[label]), size=(icon_size, icon_size))
        if icon:
            shell.alpha_composite(icon, (right_panel[0] + 28, y + 1))

        draw_label_value(
            shell_draw,
            right_panel[0] + 64,
            y - 8,
            label,
            value,
            label_font,
            detail_font,
        )
        if index < len(rows) - 1:
            divider_y = y + 42
            shell_draw.line(
                (right_panel[0] + 24, divider_y, right_panel[2] - 24, divider_y),
                fill=(235, 239, 243),
                width=1,
            )

    card.alpha_composite(shell)
    card.putalpha(card_mask)
    card.convert("RGB").save(OUTPUT_PATH)
    return OUTPUT_PATH
