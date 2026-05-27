from aiogram import Router, F

from aiogram.filters import (
    StateFilter,
    Command
)

from aiogram.types import (
    Message
)

from aiogram.fsm.context import FSMContext

from forms.user import (
    Form,
    state_map
)

from openai import AsyncOpenAI

from dotenv import load_dotenv

import os

router = Router()

load_dotenv()

api_key = os.getenv(
    "OPENAI_API_KEY"
)

client = AsyncOpenAI(
    api_key=api_key
) if api_key else None



# OPEN AI
async def ask_gpt(
    user_text: str,
    state_data: dict,
    current_state: str,
    step: int,
    category: str | None,
    subcategory: str | None
):
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": f"""
Ти консультант меблевого бота.

ПОТОЧНИЙ ЕТАП:
{current_state}

КАТЕГОРІЯ:
{category}

ПІДКАТЕГОРІЯ:
{subcategory}

ДАНІ КОРИСТУВАЧА:
{state_data}

КРОК: 
{step}

КРОКИ:
0 → ширина
1 → висота
2 → глибина

ПРАВИЛА:
1.Ти менеджер меблевого салону.

Ти НЕ вигадуєш технічні обмеження.
Ти НЕ змінюєш цифри користувача.

Ти:
— пояснюєш що означає параметр
— даєш рекомендації
— попереджаєш про незручність

РЕКОМЕНДАЦІЇ:
- ширина комода: 600–1600 мм
- висота: 600–1000 мм
- глибина: 400–600 мм

Якщо значення виходить за межі — скажи:
"Це можливо, але може бути незручно, зазвичай роблять..."

Якщо користувач питає "що далі":
— поясни поточний крок.
2. Не пояснюй попередні етапи
3. Не говори про реєстрацію якщо користувач вже зареєстрований
4. Не вигадуй функції

ЕТАПИ:
- Form.name → введення імені
- Form.phone → введення телефону
- Form.citi → вибір міста
- Form.email → введення email
- Form.dimensions → введення габаритів
- main_menu → користувач вже зареєстрований

Якщо користувач питає "що далі", "що робити", "що вводити":
— поясни поточний крок
ВАЖЛИВО:
Якщо користувач ще не перейшов до введення габаритів —
НЕ говори про ширину, висоту чи глибину.

Якщо користувач знаходиться на виборі категорії або типу комода:
— пояснюй що потрібно обрати тип або конфігурацію меблів.

Приклад:
- якщо етап габаритів → скажи "Зараз потрібно ввести ширину, потім висоту і глибину"

Якщо питання частково підходить — відповідай в межах поточного етапу
"""
            },
            {"role": "user", "content": user_text}
        ]
    )
    return response.choices[0].message.content


@router.message(F.text == "🤖 Допомога")
async def gpt_help(message: Message):
    await message.answer("Напишіть ваше питання 👇")



@router.message(
    ~Command("start"),
    ~StateFilter(
        Form.dimensions,
        Form.choose_sections,
        Form.choose_drawers,
        Form.choose_drawer_bottom
    )
)
async def fallback(
    message: Message,
    state: FSMContext
):

    current_state = await state.get_state()

    # =====================================
    # НЕ ЧІПАЄМО FSM FLOW
    # =====================================

    if current_state in [

        Form.dimensions.state,
        Form.choose_sections.state,
        Form.choose_drawers.state,
        Form.choose_drawer_bottom.state

    ]:
        return

    # =====================================
    # ТІЛЬКИ GPT HELP
    # =====================================


    if not client:
        return

    state_data = await state.get_data()

    category = state_data.get(
        "current_category"
    )

    subcategory = state_data.get(
        "subcategory"
    )

    step = state_data.get(
        "current_step",
        0
    )

    current_state_human = state_map.get(
        current_state,
        "main_menu"
    )

    answer = await ask_gpt(

        message.text,

        state_data,

        current_state_human,

        step,

        category,

        subcategory
    )

    await message.answer(answer)
