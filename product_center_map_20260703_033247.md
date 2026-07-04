# Карта продукту

- Згенеровано: 2026-07-03T03:32:47+03:00
- Компонентів: 8

## Інтерфейси

### Frontend app (`app`)

- Стан: процес: зупинено | web: online | файлів: 7
- Що робить: Публічний калькулятор і 3D-інтерфейс.
- Відповідає за: Показує користувацький інтерфейс, працює через API і відображає проектні дані.
- Залежить від: API, База даних
- Керування: Запуск / стоп
- Файли:
  - frontend/app/src/App.jsx
  - frontend/app/src/main.jsx
  - frontend/app/src/components/PartThreeViewer.jsx
  - frontend/app/src/components/ProjectThreeViewer.jsx
  - frontend/app/src/styles.css
  - frontend/app/vite.config.js
  - frontend/app/package.json

### Frontend admin (`admin`)

- Стан: процес: зупинено | web: online | файлів: 7
- Що робить: Адмін-панель для керування продуктом.
- Відповідає за: Дає доступ до керування проектами, каталогом, аудитом і сервісними діями.
- Залежить від: API, База даних
- Керування: Запуск / стоп
- Файли:
  - frontend/admin/src/App.jsx
  - frontend/admin/src/main.jsx
  - frontend/admin/src/components/PartThreeViewer.jsx
  - frontend/admin/src/components/ProjectThreeViewer.jsx
  - frontend/admin/src/styles.css
  - frontend/admin/vite.config.js
  - frontend/admin/package.json

## Дані

### База даних (`database`)

- Стан: файлів: 3
- Що робить: Основна SQLite-база з даними продукту.
- Відповідає за: Зберігає дані проектів, каталогів, користувачів і службову інформацію.
- Залежить від: API, Бот, Скрипти БД
- Керування: Відкрити
- Файли:
  - furniture_platform.db
  - mebli_calculator.db
  - database/init_db.py

## Керування

### Product Center (`product-center`)

- Стан: файлів: 5
- Що робить: Центральна програма керування продуктом.
- Відповідає за: Запускає сервіси, відкриває сторінки, веде історію та звіти.
- Залежить від: Усі компоненти
- Керування: Відкрити
- Файли:
  - scripts/db_update_wizard.py
  - product_center.pyw
  - product_center_launcher.py
  - product_center_settings.json
  - product_center_history.jsonl

## Сервер

### API (`api`)

- Стан: процес: зупинено | web: offline | файлів: 21
- Що робить: FastAPI backend для auth, projects, catalog, audit і fitting holes.
- Відповідає за: Приймає запити від інтерфейсів, працює з БД і віддає дані для аналізу та редагування.
- Залежить від: База даних, Frontend admin, Frontend app
- Керування: Запуск / стоп
- Файли:
  - main_api.py
  - api/routes/audit.py
  - api/routes/auth.py
  - api/routes/catalog.py
  - api/routes/fitting_holes.py
  - api/routes/project.py
  - api/dependencies/auth.py
  - database/init_db.py
  - database/repositories/audit_log_repository.py
  - database/repositories/catalog_repository.py
  - database/repositories/fitting_holes_repository.py
  - database/repositories/inventory_repository.py
  - database/repositories/material_import_job_repository.py
  - database/repositories/project_repository.py
  - database/repositories/project_scan_repository.py
  - database/repositories/project_version_repository.py
  - database/repositories/service_catalog_repository.py
  - database/repositories/user_change_request_repository.py
  - database/repositories/user_repository.py
  - services/material_import_queue_service.py
  - services/catalog_auto_refresh_service.py

### Бот (`bot`)

- Стан: процес: зупинено | файлів: 25
- Що робить: Telegram-бот і фонові задачі синхронізації.
- Відповідає за: Обробляє Telegram-взаємодію, ініціалізує БД, запускає планувальник і MT-логіку.
- Залежить від: База даних, MT-дані, Планувальник
- Керування: Запуск / стоп
- Файли:
  - main.py
  - handlers/auth.py
  - handlers/categories.py
  - handlers/dimensions.py
  - handlers/drawers.py
  - handlers/drawer_bottoms.py
  - handlers/fittings.py
  - handlers/gpt.py
  - handlers/materials.py
  - handlers/production.py
  - handlers/profile.py
  - handlers/router.py
  - handlers/sections.py
  - services/scheduler.py
  - services/mt_parser.py
  - services/mt_kits_parser.py
  - services/production_admin_engine.py
  - services/production_auth_engine.py
  - services/production_dashboard_engine.py
  - services/production_database_engine.py
  - services/production_role_engine.py
  - services/production_scan_engine.py
  - services/production_state_engine.py
  - services/production_tracking_engine.py
  - services/database.py

### Фонові служби (`background`)

- Стан: процес: зупинено | файлів: 3
- Що робить: Матеріали, каталоги та синхронізація, що стартують разом з API.
- Відповідає за: Підтримує черги імпорту і автоновлення каталогу у фоні.
- Залежить від: API
- Керування: Працює через API
- Файли:
  - services/material_import_queue_service.py
  - services/catalog_auto_refresh_service.py
  - services/scheduler.py

## Утиліти

### Скрипти БД (`scripts-db`)

- Стан: файлів: 5
- Що робить: Безпечні оновлення, repair і seed-скрипти.
- Відповідає за: Оновлює структуру бази без втрати користувацьких даних.
- Залежить від: База даних
- Керування: Відкрити
- Файли:
  - scripts/safe_update_db.py
  - scripts/repair_catalog_data.py
  - scripts/seed_confirmat_190106_holes.py
  - scripts/upgrade_fittings_schema.py
  - scripts/catalog_snapshot.py

