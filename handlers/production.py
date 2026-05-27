from aiogram import Router, F

from aiogram.filters import (
    Command
)

from aiogram.types import (
    Message
)

from aiogram.fsm.context import FSMContext

from forms.user import Form

from services.production_scan_engine import (
    process_scan
)

from services.production_admin_engine import (
    create_operator,
    is_admin
)

from services.production_dashboard_engine import (
    get_production_stats
)

router = Router()



@router.message(
    Form.scan_barcode
)
async def scan_barcode_handler(

    message: Message,

    state: FSMContext
):

    barcode = (
        message.text.strip()
    )

    result = process_scan(

        barcode,

        "cutting",

        message.from_user.id
    )

    if not result[
        "success"
    ]:

        await message.answer(

            f"❌ Помилка: "
            f"{result.get('error')}"
        )

        return

    await message.answer(

        "✅ Етап оновлено\n\n"

        f"Деталь: "
        f"{result['part_id']}\n"

        f"{result['old_stage']} "
        f"→ "
        f"{result['new_stage']}"
    )

    await state.clear()


# =====================================================
# CREATE OPERATOR
# Створення оператора
# =====================================================

@router.message(
    Command("create_operator")
)
async def create_operator_command(

    message: Message,

    state: FSMContext
):

    await state.set_state(
        Form.create_operator_id
    )

    await message.answer(

        "Введіть Telegram ID оператора"
    )  


# =====================================================
# OPERATOR ID
# =====================================================

@router.message(
    Form.create_operator_id
)
async def operator_id_handler(

    message: Message,

    state: FSMContext
):

    try:

        operator_id = int(
            message.text
        )

    except ValueError:

        await message.answer(

            "❌ Telegram ID має бути числом"
        )

        return

    await state.update_data(

        operator_id=operator_id
    )

    await state.set_state(
        Form.create_operator_username
    )

    await message.answer(

        "Введіть username"
    )


# =====================================================
# OPERATOR USERNAME
# =====================================================

@router.message(
    Form.create_operator_username
)
async def operator_username_handler(

    message: Message,

    state: FSMContext
):

    await state.update_data(

        username=message.text
    )

    await state.set_state(
        Form.create_operator_role
    )

    await message.answer(

        "Введіть роль\n\n"

        "admin\n"
        "cut_operator\n"
        "edgebanding_operator\n"
        "drilling_operator\n"
        "assembly_operator\n"
        "packaging_operator"
    )


# =====================================================
# OPERATOR ROLE
# =====================================================

@router.message(
    Form.create_operator_role
)
async def operator_role_handler(

    message: Message,

    state: FSMContext
):

    data = await state.get_data()

    result = create_operator(

        admin_id=message.from_user.id,

        telegram_id=data[
            "operator_id"
        ],

        username=data[
            "username"
        ],

        role=message.text
    )

    if not result[
        "success"
    ]:

        await message.answer(

            f"❌ Помилка: "
            f"{result['error']}"
        )

        await state.clear()

        return

    await message.answer(

        "✅ Оператор створений\n\n"

        f"ID: "
        f"{result['telegram_id']}\n"

        f"Username: "
        f"{result['username']}\n"

        f"Role: "
        f"{result['role']}"
    )

    await state.clear()      



# =====================================================
# PRODUCTION DASHBOARD
# Dashboard виробництва
# =====================================================

@router.message(
    Command("dashboard")
)
async def dashboard_handler(

    message: Message
):
    from services.production_admin_engine import (
        is_admin
    )

    if not is_admin(

        message.from_user.id
    ):

        await message.answer(

            "❌ Доступ заборонений"
        )

        return
    stats = get_production_stats()

    stages = stats[
        "stages"
    ]

    stage_text = ""

    for stage, count in stages.items():

        stage_text += (

            f"{stage}: "
            f"{count}\n"
        )

    await message.answer(

        "📊 Dashboard виробництва\n\n"

        f"Всього деталей: "
        f"{stats['total_parts']}\n"

        f"Завершено: "
        f"{stats['completed_parts']}\n"

        f"Прогрес: "
        f"{stats['progress_percent']}%\n\n"

        f"Етапи:\n"
        f"{stage_text}"
    )    

