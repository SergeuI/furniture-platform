# furniture-platform
Furniture calculation platform with Telegram bot, FastAPI backend, BOM engine and CNC generation

## Database safety

The app now reads the SQLite file path from environment variables instead of a hardcoded filename.

- `FURNITURE_PLATFORM_DB_PATH` controls the main app database
- `FURNITURE_LEGACY_DB_PATH` controls the legacy Telegram/production helper database

If the variables are not set, the app falls back to the project-root files:

- `furniture_platform.db`
- `mebli_calculator.db`

All startup and migration helpers are additive:

- tables are created with `CREATE TABLE IF NOT EXISTS`
- seeds use `INSERT OR IGNORE` or matching upserts
- no startup command drops tables or calls `delete` on user-owned project data

This means you can keep a separate local copy for testing and a separate server copy for production data.

### Local test setup

Windows PowerShell:

```powershell
Copy-Item .\furniture_platform.db .\furniture_platform.local.db
$env:FURNITURE_PLATFORM_DB_PATH = (Resolve-Path .\furniture_platform.local.db).Path
$env:FURNITURE_LEGACY_DB_PATH = (Resolve-Path .\mebli_calculator.db).Path
.\.venv\Scripts\python.exe main_api.py
```

If you also want the bot to use the same local database:

```powershell
$env:FURNITURE_PLATFORM_DB_PATH = (Resolve-Path .\furniture_platform.local.db).Path
$env:FURNITURE_LEGACY_DB_PATH = (Resolve-Path .\mebli_calculator.db).Path
.\.venv\Scripts\python.exe main.py
```

### Server update flow

Use the server's own database file and never copy your local test DB over it.

```bash
cd /path/to/furniture-platform
git pull
./venv/bin/pip install -r requirements.txt
cd frontend/admin
npm run build
export FURNITURE_PLATFORM_DB_PATH=/path/to/furniture-platform/furniture_platform.db
export FURNITURE_LEGACY_DB_PATH=/path/to/furniture-platform/mebli_calculator.db
./venv/bin/python scripts/safe_update_db.py
sudo systemctl restart furniture-api furniture-bot
```

`scripts/safe_update_db.py` makes a backup first and then runs the same additive initialization/migration logic, so existing user data stays intact.

## Restore user access

Reset an existing user's password from the project root. The password is entered
interactively and is not stored in the shell history.

Windows:

```powershell
.\.venv\Scripts\python.exe scripts\reset_user_password.py --user admin@example.com
```

Linux server:

```bash
./venv/bin/python scripts/reset_user_password.py --user admin@example.com
```

Demo users are no longer created automatically in normal environments. For an
explicit local demo database, set `SEED_DEMO_USERS=true` before initializing it.

## Playwright on an Ubuntu server

The Kronas and other browser-backed parsers require Chromium together with its
Linux runtime libraries. Install and verify them from the project root:

```bash
sudo ./venv/bin/playwright install-deps chromium
./venv/bin/playwright install chromium
./venv/bin/python scripts/check_playwright_runtime.py
```

The final command must print `Playwright Chromium: OK`. Restart the API and bot
after installing dependencies:

```bash
sudo systemctl restart furniture-api furniture-bot
```
