# Update package update_0017

- Created: 2026-07-04T23:44:18+03:00
- Branch: main
- Head commit: 330ecaf
- File count: 6

## Files
- code:
  - api/routes/catalog.py
- database:
  - database/repositories/inventory_repository.py
- ui:
  - frontend/admin/src/App.jsx
  - frontend/admin/src/styles.css
  - product_center_settings.json
- other:
  - product_center_history.jsonl

## Server plan
- 1. На сервері виконати `git pull`.
- 2. Запустити `scripts/safe_update_db.py` з резервною копією.
- 3. Зібрати фронтенд після оновлення коду.
- 4. Перезапустити API, bot і фронтенди після оновлення.
