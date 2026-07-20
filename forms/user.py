from aiogram.fsm.state import State, StatesGroup

class Form(StatesGroup):
    # 🔹 реєстрація
    name = State()
    phone = State()
    citi = State()
    email = State()

    # 🔹 редагування
    edit_phone = State()
    edit_citi = State()
    edit_email = State()

    # 🔹 габарити
    # 🔹 габарити

    dimensions = State()

    telegram_registration = State()

    width = State()

    height = State()

    depth = State()

    # 🔹 матеріали
    material_type = State()
    material = State()

    # ◆ виробництво
    scan_barcode = State()
    # ◆ адміністрування
    create_operator_id = State()

    create_operator_username = State()

    create_operator_role = State()
    # =========================
    # СЕКЦІЇ
    # =========================

    choose_sections = State()

    # =========================
    # ШУХЛЯДИ
    # =========================

    choose_drawers = State()
    choose_drawer_bottom = State()

    choose_material_type = State()


state_map = {
    "Form.name": "введення імені",
    "Form.phone": "введення телефону",
    "Form.citi": "вибір міста",
    "Form.email": "введення email",
    "Form.dimensions": "введення габаритів",
    "Form.width": "введення ширини",
    "Form.height": "введення висоти",
    "Form.depth": "введення глибини",
    None: "головне меню"
}
