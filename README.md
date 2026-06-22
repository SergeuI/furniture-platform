# furniture-platform
Furniture calculation platform with Telegram bot, FastAPI backend, BOM engine and CNC generation

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
