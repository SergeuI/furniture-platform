# MP Furniture Platform / MPFC

Дата підготовки: 2026-08-20  
Основа: повний аудит фактичного репозиторію, SQLite-схеми, FastAPI, frontend, Telegram-бота, Product Center, імпортерів і виробничих сервісів.

Цей документ навмисно написаний у двох режимах одночасно:
- для власника продукту він пояснює, як система працює простими словами;
- для розробника він показує технічні сутності, зв'язки, джерела істини, ризики та порядок розвитку.

---

## 1. Як працює весь продукт

MPFC вже є єдиною платформою, а не набором окремих скриптів.

Простими словами:
- користувач реєструється;
- обирає матеріали, фурнітуру і параметри меблів;
- отримує проєкт, BOM, кошторис і виробничі дані;
- адміністратор керує каталогом, технічними вузлами, присадкою, тарифами і правами;
- Telegram-бот дає швидкий доступ до того самого ядра системи;
- 3D у поточному вигляді є візуальним preview, а не повноцінним кінематичним рушієм.

Технічно:
- backend: `main_api.py`, `api/routes/*`, `services/*`, `database/*`;
- bot: `main.py`, `handlers/*`;
- user web: `frontend/app`;
- admin web: `frontend/admin`;
- storage: SQLite `furniture_platform.db`;
- legacy helper data: Telegram/production tables і старі parser-структури.

Головна архітектурна ідея зараз:
- один backend;
- одна основна БД;
- окремі канали доступу;
- частково спільні дані;
- частково legacy-залишки;
- ще немає повноцінного versioned technical rule layer.

---

## 2. Master Architecture Map

### 2.1 Верхній рівень

#### Користувачі та доступ
Простими словами: хто входить у систему, що може робити, які має обмеження.

Технічно:
- `users`;
- `entitlement_features`;
- `plan_entitlements`;
- `registration_identities`;
- `registration_challenges`;
- `user_change_requests`;
- `audit_logs`.

#### Каталоги
Простими словами: довідник матеріалів, фурнітури, виробників, постачальників, серій, категорій, цін і фото.

Технічно:
- `materials`;
- `material_prices`;
- `material_user_links`;
- `material_edges`;
- `material_edge_options`;
- `material_edge_prices`;
- `fittings`;
- `fitting_products`;
- `fitting_supplier_offers`;
- `fitting_images`;
- `fitting_manufacturers`;
- `fitting_series`;
- `fitting_categories`;
- `suppliers`;
- `service_catalog_items`;
- `service_drilling_rules`.

#### Технічна частина фурнітури
Простими словами: не товар як такий, а те, що він означає в механіці меблів.

Технічно:
- `fitting_products`;
- `mounting_nodes`;
- `mounting_node_items`;
- `mounting_node_templates`;
- `mounting_node_versions`;
- `fitting_hole_templates`;
- `fitting_hole_points`.

#### Проєкт меблів
Простими словами: конкретний меблевий виріб із розмірами, матеріалами, фурнітурою, розрахунками і виробничими даними.

Технічно:
- `projects`;
- `project_versions`;
- `project_scan_sessions`.

#### Розрахунки
Простими словами: скільки потрібно матеріалів, фурнітури, робіт і яка буде ціна.

Технічно:
- `project_bom_service`;
- `project_costing_service`;
- `project_cutting_service`;
- `project_part_detail_service`;
- `service_catalog_items`;
- `material_prices`;
- `fitting_supplier_offers`;
- `fittings.price`;
- `materials` / `materials.price`.

#### 3D
Простими словами: попередній перегляд форми меблів і деталей.

Технічно:
- `frontend/app/src/components/ProjectThreeViewer.jsx`;
- `frontend/app/src/components/PartThreeViewer.jsx`;
- React Three Fiber + Three.js.

#### Виробництво
Простими словами: підготовка деталей, кромки, присадки і даних для CNC/експорту.

Технічно:
- `services/cutting_*`;
- `services/generate_*`;
- `services/production_*`;
- `services/cnc_*`;
- `parts`, `orders`, `nesting_results`, `machining_operations`, `production_states`, `production_users`.

#### Аналіз документів
Простими словами: фото, PDF, креслення чи відео перетворюються на чернетку або технічне правило.

Технічно:
- `services/ocr_service.py`;
- `services/project_parser.py`;
- `services/furniture_detector.py`;
- `services/material_catalog_service.py`;
- `services/viyar_parser.py`;
- `services/mt_parser.py`.

#### Канали роботи
Простими словами: один продукт працює через веб, Telegram і API.

Технічно:
- Admin Web: `frontend/admin`;
- User Web: `frontend/app`;
- Telegram: `main.py`, `handlers/*`;
- API: `main_api.py`, `api/routes/*`.

---

## 3. Рух даних

### 3.1 Типовий шлях користувача

1. Користувач входить у систему.
2. Система визначає роль, тариф і trial-стан.
3. Користувач створює або відкриває проєкт.
4. Проєкт використовує live catalog data для матеріалів, фурнітури і сервісів.
5. Backend рахує BOM, cutting, part detail, estimate.
6. User web показує 3D preview і таблиці.
7. Дані можуть бути підтягнуті в Telegram або експортуватися у виробництво.

### 3.2 Типовий шлях адміна

1. Адмін відкриває catalog або mounting nodes.
2. Додає чи редагує матеріали, фурнітуру, offers, taxonomy, rules.
3. Система перевіряє права через backend.
4. Дані пишуться в ті самі таблиці, які використовуються в user web і bot.

### 3.3 Типовий шлях Telegram

1. Telegram-бот отримує команду або callback.
2. Handler звертається до спільного сервісу.
3. Сервіс читає ті самі каталоги і проєкти.
4. Користувач отримує коротку відповідь, швидкий кошторис або вибір товару.

### 3.4 Що є live, а що snapshot

Live:
- каталоги;
- ціни;
- stock;
- права;
- taxonomy.

Snapshot:
- `project_versions`;
- `mounting_node_versions`;
- окремі scan sessions.

Поточний ризик:
- BOM та кошторис залежать від live catalog, тому історичний проєкт може змінюватися після оновлення довідників, якщо не зафіксувати snapshot повністю.

---

## 4. Architecture Ledger

Пояснення колонок:
- `Source of Truth` - де дані реально живуть;
- `System/User/Project` - чия це сутність;
- `Delete policy` - як видаляється або архівується;
- `Version policy` - чи є версії;
- `Snapshot policy` - чи потрапляє в проєктний зліпок;
- `Рішення` - REUSE / EXTEND / NEW / LEGACY / REMOVE LATER.

| Людська назва | Що це означає | Технічна сутність | Source of Truth | System/User/Project | Хто створює | Хто змінює | Де використовується | Від чого залежить | Що залежить від неї | Delete policy | Version policy | Snapshot policy | Стан | Рішення |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Користувач | Акаунт людини або компанії | `users` | `users` | System + User | admin, registration | user, admin | auth, projects, bot, permissions | registration, auth, trial | майже все | soft/active flags | немає повноцінної | частково в проєктах | ✅ | REUSE |
| Тариф і права | Що доступно на плані | `entitlement_features`, `plan_entitlements` | `plan_entitlements` + `entitlement_features` | System | admin | admin | API enforcement, UI visibility | plan code, feature registry | many features | soft/inactive | registry versioning логічне, не окреме | ні | ✅ | REUSE |
| Матеріал | Декоративна/конструкційна позиція | `materials` | `materials` | System + User | admin, imports, user | admin, owner | web, bot, BOM | supplier data, images, prices | project BOM, cutting | delete with dependency checks | немає | project uses live refs | ✅ | EXTEND |
| Ціна матеріалу | Ціна по місту/джерелу | `material_prices` | `material_prices` | System | imports, workers | imports | catalog, bot, BOM | material, city, source | estimate | delete with refresh rules | немає | live only | ✅ | REUSE |
| Кромка | Крайка для матеріалів | `material_edge_options`, `material_edge_prices` | edge tables | System | imports | imports/admin | catalog, BOM | material article | material calculation | delete with checks | немає | live only | 🟡 | EXTEND |
| Фурнітура як товар | Конкретний купівельний товар | `fittings` | `fittings` | System + User | admin, imports, user | admin, owner | catalog, bot, project, BOM | supplier offer, technical product | offers, project selection | delete with dependency checks | частково через technical link | live + partial snapshot | ✅ | EXTEND |
| Технічний продукт фурнітури | Що це за механізм по суті | `fitting_products` | `fitting_products` | System | admin, imports | admin | technical catalog, taxonomy | manufacturer, series, category | fittings, future rules | soft/inactive | немає повної | бажано snapshot | 🟡 | EXTEND |
| Постачальник | Хто продає | `suppliers` | `suppliers` | System + User | admin, owner | admin, owner | offers, catalog | ownership, logos | supplier offers | delete with dependency checks | немає | live only | ✅ | EXTEND |
| Supplier offer | Пропозиція від постачальника | `fitting_supplier_offers` | `fitting_supplier_offers` | System | imports, admin | imports/admin | pricing, catalog, bot | fitting, supplier | price, stock, article | delete with dependency checks | немає | live only | ✅ | REUSE |
| Фото фурнітури | Зображення товару | `fitting_images` | `fitting_images` | System | imports, admin | admin/imports | catalog, preview | fitting | product page | cascade from fitting | немає окремої | live only | ✅ | REUSE |
| Класифікація фурнітури | Категорії, серії, виробники | `fitting_categories`, `fitting_series`, `fitting_manufacturers` | taxonomy tables | System | admin | admin | catalog, filters | taxonomy logic | fitting products | delete with dependency checks | soft/inactive | live only | ✅ | REUSE |
| Монтажний вузол | Склад механізму після встановлення | `mounting_nodes` | `mounting_nodes` + `mounting_node_versions` | System + User | admin, future user | admin, owner | processing, future rules | fitting items, templates | drilling, motion, 3D | archive/delete guarded | versioned | snapshot desired | 🟡 | EXTEND |
| Склад вузла | Які фурнітурні елементи входять | `mounting_node_items` | `mounting_node_items` | System + User | admin | admin, owner | mounting nodes, processing | mounting node, fitting | drilling, BOM, 3D | cascade with node | inherits node version | yes via node snapshot | 🟡 | EXTEND |
| Шаблон присадки | Набір отворів для конкретного типу | `fitting_hole_templates` | `fitting_hole_templates` | System | admin | admin | fitting holes, mounting nodes | fitting | hole points, templates | delete guarded by references | немає | should snapshot | 🟡 | EXTEND |
| Точки присадки | Конкретні отвори і координати | `fitting_hole_points` | `fitting_hole_points` | System | admin | admin | previews, future production | template | drilling, 3D, export | delete guarded | немає | should snapshot | 🟡 | EXTEND |
| Правило присадки сервісу | Сервісне свердління | `service_drilling_rules` | `service_drilling_rules` | System | admin | admin | processing, service catalog | service item, diameters, depths | hole preview, validation | delete guarded | немає | live only | 🟡 | EXTEND |
| Сервісний каталог | Роботи/послуги | `service_catalog_items` | `service_catalog_items` | System + User | admin, imports, user | admin, owner | BOM, pricing, drilling | source, tree, rules | project cost | delete guarded | rules fields partially versioned | live + partial owner refs | ✅ | EXTEND |
| Проєкт | Конкретний меблевий виріб | `projects` | `projects` | Project | user, admin | user, admin | user web, admin, bot | live catalog, forms | BOM, cutting, 3D, export | delete guarded | partial | snapshot partial | ✅ | EXTEND |
| Версія проєкту | Збережений стан проєкту | `project_versions` | `project_versions` | Project | backend | backend | rollback, history | project | safe history | no direct delete policy found | versioned | yes | ✅ | REUSE |
| Project scan | Чернетка з OCR/фото | `project_scan_sessions` | `project_scan_sessions` | Project | user | backend/admin | user web, future bot | uploads, OCR, detection | create project draft | lifecycle status | versioned by session | yes | 🟡 | EXTEND |
| Аудит | Хто і що змінив | `audit_logs` | `audit_logs` | System | backend | backend | admin review, traceability | actor, entity | compliance, debug | delete rarely | append-only | yes for history | ✅ | REUSE |
| Telegram helper data | Старі/допоміжні записи | `telegram_users`, `telegram_projects`, `calculations` | legacy tables | Legacy | bot | bot | Telegram only | chat flows | quick actions | legacy cleanup later | no | no | ⚠️ | LEGACY |

---

## 5. Фурнітура і технічна модель

### 5.1 Ланцюжок фурнітури

Коротко:
- конкретний товар;
- його технічний тип;
- сумісність;
- монтажний вузол;
- правило монтажу;
- присадка;
- правило руху;
- 3D.

### 5.2 Що вже є

- `fittings` - реальний товар для продажу, запасу, прайсу, фото.
- `fitting_products` - окремий технічний тип.
- `fitting_supplier_offers` - пропозиції різних постачальників.
- `fitting_hole_templates` / `fitting_hole_points` - початкова модель присадки.
- `mounting_nodes` - початкова модель зібраного механізму.

### 5.3 Де зараз змішано commercial і technical

- У `fittings` одночасно є:
  - назва товару;
  - артикул;
  - ціна;
  - stock;
  - джерело;
  - фото;
  - `technical_product_id`.
- Це означає, що таблиця одночасно є товарним каталогом і операційним bridge між технічною сутністю та постачальниками.

### 5.4 Просте пояснення для власника

- `fittings` - “що ми реально продаємо або купуємо”.
- `fitting_products` - “що це за механізм насправді”.
- `mounting_nodes` - “як цей механізм складається в установці”.
- `fitting_hole_templates` - “які отвори потрібно зробити”.
- `fitting_hole_points` - “де саме ці отвори стоять”.

### 5.5 Що ще не доведено до повної моделі

- немає повноцінного technical compatibility layer;
- немає motion rules;
- немає collision/clearance engine як окремого persisted шару;
- немає versioned publish flow для технічних правил;
- є лише підготовчі структури.

---

## 6. Монтажні вузли та присадка

### 6.1 Монтажний вузол

Простими словами:
- це зібраний набір елементів фурнітури, який ставиться як один механізм.

Технічно:
- `mounting_nodes`
- `mounting_node_items`
- `mounting_node_templates`
- `mounting_node_versions`

### 6.2 Що вже є

- вузол має `owner_user_id`, `is_system`, `is_active`, `is_archived`;
- є version history;
- є прив’язка до `fittings`;
- є прив’язка до шаблонів присадки;
- є базова перевірка доступу в service/router.

### 6.3 Що зараз видно з БД

- структура створена;
- фактичні записи в `mounting_nodes`, `mounting_node_items`, `mounting_node_templates` зараз відсутні;
- історія версій вже існує.

### 6.4 Присадка

Простими словами:
- це карта отворів: де, якої глибини, якого діаметра і на якій стороні треба свердлити.

Технічно:
- `fitting_hole_templates`
- `fitting_hole_points`
- `service_drilling_rules`
- `fitting_hole_service_rules`

### 6.5 Координати

У поточній моделі видно:
- `x_mm`, `y_mm`, `z_mm`;
- `diameter_mm`;
- `depth_mm`;
- `side`;
- `operation`;
- `mirrored`;
- `target_surface`, `target_side`, `target_panel`.

Це означає:
- модель вже підтримує просту геометрію отворів;
- але ще не є повною кінематичною координатною системою для motion rules.

### 6.6 Статус

- ✅ основа є;
- 🟡 живі дані і правила ще не доведені до повної архітектури;
- 🔴 окремий kinematic layer ще не існує.

### 6.7 UI/UX reference contract

Офіційний UI/UX-еталон сторінок монтажних вузлів зафіксовано в [`docs/mounting_node_reference_workspace_v1.md`](mounting_node_reference_workspace_v1.md) — **Mounting Node Reference Workspace v1 — Confirmat**.

---

## 7. 3D та анімація

### 7.1 Що є зараз

- статичний 3D preview на React Three Fiber;
- показ корпусу, фасадів, деталей, отворів, кромки, пазів, чвертей;
- режими assembled / exploded / transparent / solid;
- частково heuristic-based classification деталей.

### 7.2 Що це означає простими словами

- система вже “показує форму”;
- але ще не “симулює механіку”.

### 7.3 Чого поки що немає

- немає persisted GLB/GLTF/STEP/CAD asset pipeline як основи core 3D model;
- немає joint graph;
- немає animation timeline;
- немає collision engine як окремої бізнес-сутності;
- немає kinematic chain storage;
- немає strict world/local coordinate standard, закріпленого як єдиний продуктовый контракт.

### 7.4 Що буде потрібно для майбутнього

- `HINGE_ROTATION`;
- `LINEAR_SLIDE`;
- `PARALLEL_VERTICAL_LIFT`;
- `kinematic chains`;
- `collision envelopes`;
- `mirrored behavior`;
- `versioned 3D asset snapshots`.

### 7.5 Практичний висновок

Поточний 3D модуль придатний як UI preview.
Для production-grade technical model він ще не достатній.

---

## 8. Technical Rule Studio

### 8.1 Що це має означати

Простими словами:
- це внутрішній admin-only простір, де технічне правило не публікується, поки його не перевірено.

### 8.2 Майбутній pipeline

```text
PDF / image / drawing / video / CAD
→ extraction
→ structured technical data
→ admin review
→ test
→ publish
```

### 8.3 Що вже можна переиспользувати

- документо- і upload-логіку;
- OCR/scan-пайплайн;
- audit logs;
- entitlement system;
- project scan sessions;
- service catalog tree;
- service drilling rules.

### 8.4 Що треба буде додати

- окремий layer для source/evidence;
- versioning rule package;
- статуси DRAFT / EXTRACTED / REVIEWED / TESTED / APPROVED / PUBLISHED / DEPRECATED;
- захист від автоматичної публікації AI;
- test scenarios;
- rule regression suite.

### 8.5 Простими словами для власника

- AI може запропонувати правило;
- адміністратор його перевіряє;
- система тестує;
- тільки після цього правило стає системним.

---

## 9. Проєкти та snapshots

### 9.1 Що таке проєкт простими словами

Проєкт - це не просто форма.
Це зафіксований стан меблевого виробу, який включає:
- розміри;
- матеріали;
- фурнітуру;
- кромку;
- присадку;
- 3D preview;
- BOM;
- розрахунки;
- виробничі дані.

### 9.2 Що є зараз

- `projects` - live state;
- `project_versions` - історія/зліпки;
- `project_scan_sessions` - чернетки зі скану.

### 9.3 Що треба фіксувати у snapshot

- не тільки значення полів форми;
- а й розраховані посилання на каталоги, якщо вони впливають на старий кошторис;
- версію technical rule, якщо вона змінює геометрію;
- технічну і комерційну заміну окремо.

### 9.4 Що зараз є ризиком

- якщо live price або live offer зміниться, старий проєкт може візуально/фінансово змінитися;
- якщо tech rule оновиться, старий 3D або drilling може стати неактуальним;
- тому потрібно розділити live catalog і frozen project snapshot.

---

## 10. BOM / ціни / заміни

### 10.1 Просте пояснення

Потрібно відрізняти:
- технічно що треба;
- комерційно де це купити;
- скільки це коштує;
- що входить у BOM;
- що входить у estimate.

### 10.2 Де це вже є

- `project_bom_service.py`;
- `project_costing_service.py`;
- `project_cutting_service.py`;
- `services/project_generation_service.py`;
- `fitting_supplier_offers`;
- `material_prices`;
- `service_catalog_items.base_price`.

### 10.3 Комерційна заміна

Простими словами:
- той самий технічний механізм;
- але інший постачальник, артикул, stock або ціна.

Що не повинно змінюватися:
- mounting node;
- drilling;
- 3D;
- motion.

### 10.4 Технічна заміна

Простими словами:
- інший механізм по суті;
- може змінитися монтаж, отвори, 3D і рух.

### 10.5 Поточний стан

- комерційна заміна частково можлива;
- технічна заміна поки не оформлена як окрема правило-система.

---

## 11. Telegram

### 11.1 Що Telegram є зараз

- окремим UI-каналом до того самого ядра;
- не окремим продуктом;
- не окремою БД;
- не окремою формулою кошторису.

### 11.2 Що Telegram уже вміє

- реєстрація;
- профіль;
- вибір матеріалів;
- вибір фурнітури;
- прості розрахунки;
- production helper flows;
- роботу з legacy helper data.

### 11.3 Що Telegram не повинен робити

- повний 3D editor;
- editing присадки;
- editing mounting nodes;
- publishing system rules;
- окрему копію каталогу;
- окрему модель кошторису.

### 11.4 Правильна модель

```text
MPFC Core
  ├─ Web App
  └─ Telegram Bot
```

Одна БД.
Одні каталоги.
Одні правила.
Одні проєкти.
Один BOM.

---

## 12. Права

### 12.1 Що є зараз

- роль у `users.role`;
- plan/feature matrix;
- backend enforcement через `EntitlementService`;
- `require_roles` у dependency layer;
- UI visibility як додатковий шар.

### 12.2 Що це означає простими словами

- не всі кнопки, які видно в інтерфейсі, можна безпечно вважати дозволеними;
- істинний контроль має бути на backend.

### 12.3 Важливі відмінності

- system-only;
- user-owned;
- admin override;
- plan limitation;
- trial limitation.

### 12.4 Status

- ✅ основа реально працює;
- 🟡 ще треба вирівняти повну матрицю на всіх доменах;
- ⚠️ частина прав виражена тільки в UI-логіці.

---

## 13. Source of Truth Map

```text
ЦІНА
→ Supplier Offer / Material Price / Service Base Price

ТЕХНІЧНИЙ ТИП
→ fitting_products

КОНКРЕТНИЙ ТОВАР
→ fittings / materials

СКЛАД МЕХАНІЗМУ
→ mounting_nodes + mounting_node_items

ОТВОРИ
→ fitting_hole_templates + fitting_hole_points

РУХ
→ майбутній Motion Rule Layer

3D ФОРМА
→ frontend 3D preview + майбутні asset snapshots

СТАН У ПРОЄКТІ
→ projects + project_versions
```

### Конфліктні місця

- `fittings` одночасно є товаром і технічним bridge;
- `materials` мають і товарні, і користувацькі, і кешовані поля;
- `projects` не зберігають повний frozen state усіх залежних сутностей;
- `mounting_nodes` і `fitting_hole_*` поки що не мають повного operational dataset.

---

## 14. Versioning Map

### Має версіонуватися

- technical product;
- mounting node;
- drilling rule;
- motion rule;
- compatibility rule;
- 3D asset;
- source document;
- rule evidence.

### Що вже версіоновано

- `project_versions`;
- `mounting_node_versions`.

### Що ще не версіоновано як окремий технічний контракт

- `fitting_products`;
- `fitting_hole_templates`;
- `fitting_hole_points`;
- `service_drilling_rules`;
- motion/collision rules.

### Просте правило

Після publish зміну, що впливає на виробництво, не редагувати “на місці”.

Краще:
- v1;
- потім v2;
- старі проєкти лишаються на старій версії.

---

## 15. Risks

### Critical

- live catalog може змінити історичний кошторис;
- немає повного technical rule layer;
- mounting/drilling/3D ще не закріплені як єдина версіонована модель.

### High

- commercial і technical сутності фурнітури змішані;
- owner/system data може почати конкурувати з system catalog;
- Telegram legacy data може відтворювати стару логіку;
- imports можуть “повертати” data after delete.

### Medium

- 3D preview heuristic-based;
- частина business rules зав'язана на назви;
- тестове покриття є, але `pytest` не встановлений у цьому venv.

---

## 16. Dependency Roadmap

### Етап 1 - Закріпити фундамент даних

Що робимо:
- зафіксувати source of truth;
- розвести commercial і technical reading;
- описати snapshot policy для проєктів.

Чому:
- без цього масове наповнення каталогу створить хаос.

Що вже є:
- база;
- catalog;
- entitlements;
- project versions;
- mounting node versions.

Що не чіпаємо:
- існуючі таблиці;
- працюючі UI;
- legacy flows.

### Етап 2 - Розділити товар і технічну поведінку

Що робимо:
- оформити technical product як окремий контракт;
- відокремити монтаж і присадку від комерційного товару.

### Етап 3 - Додати versioned rule layer

Що робимо:
- правила підбору;
- сумісність;
- монтаж;
- присадка;
- рух;
- колізії.

### Етап 4 - Rule Studio

Що робимо:
- джерела;
- review;
- test;
- publish.

### Етап 5 - Розширення 3D і production

Що робимо:
- motion;
- collision;
- export;
- regression tests.

---

## 17. Що треба зробити до масового наповнення фурнітури

### Обов'язково зараз

- зафіксувати, що `fittings` - комерційний рівень, а `fitting_products` - технічний;
- визначити snapshot policy для project BOM;
- не публікувати нові технічні сутності без versioning policy;
- не починати Rule Studio як “другий каталог”.

### Можна трохи пізніше

- evidence layer;
- source document storage;
- rule test scenarios;
- motion/collision engine.

### Можна безпечно паралельно

- описати ledger;
- розширити документацію;
- підготувати матрицю прав;
- формалізувати naming conventions;
- планувати import mapping.

---

## 18. User/Admin/Telegram Map

| Функція | Admin Web | User Web | Telegram | API |
| --- | ---: | ---: | ---: | ---: |
| Реєстрація | ❌ | ✅ | ✅ | ✅ |
| Профіль | ✅ | ✅ | ✅ | ✅ |
| Каталог матеріалів | ✅ | ✅ | ✅ | ✅ |
| Каталог фурнітури | ✅ | ✅ | ✅ | ✅ |
| Створення проєкту | ✅ | ✅ | частково | ✅ |
| BOM | ✅ | ✅ | ✅ | ✅ |
| Кошторис | ✅ | ✅ | ✅ | ✅ |
| Mounting nodes | ✅ | ❌ | ❌ | ✅ |
| Присадка | ✅ | ❌ | ❌ | ✅ |
| Rule Studio | ✅ | ❌ | ❌ | майбутній |
| 3D preview | ✅ | ✅ | ❌ | частково |

---

## 19. Що вже працює, а що ще ні

### Вже працює

- backend API;
- auth;
- catalog;
- projects;
- BOM/cutting;
- entitlements;
- Telegram bot flows;
- 3D preview.

### Є основа, треба доробити

- mounting nodes;
- fitting holes;
- technical product layer;
- frozen snapshots;
- versioned rule layer.

### Ще немає

- Rule Studio;
- motion rules;
- collision envelopes;
- full kinematic chains;
- strict coordinate standard as product contract.

### Є ризик / legacy

- Telegram helper tables;
- mixed commercial/technical tables;
- live references where snapshots are needed.

---

## 20. Recommended next step

Наступний безпечний крок:

1. Перетворити цей документ у повну Master Architecture Ledger у вигляді окремої, ще більш детальної матриці по сутностях.
2. Після цього зробити окрему dependency diagram для:
   - fittings;
   - materials;
   - projects;
   - mounting nodes;
   - drilling rules;
   - 3D.
3. Лише потім переходити до першого архітектурного етапу реалізації.

---

## 21. Підсумок для власника

Система вже реальна і досить велика:
- у ній є каталог;
- є проєкти;
- є тарифи;
- є Telegram;
- є 3D preview;
- є виробничі сервіси;
- є початкові технічні правила.

Але архітектурний фундамент ще треба домалювати в одному місці:
- чітко відділити товар від техніки;
- зафіксувати versioning;
- закріпити snapshots;
- підготувати rule layer;
- не плодити паралельний продукт поверх існуючого.
