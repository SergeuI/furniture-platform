"""Майстер безпечного оновлення бази даних і локальних Git-комітів.

Ця програма допомагає:
- вибрати локальний або серверний сценарій;
- згенерувати команди оновлення баз;
- запустити безпечне локальне оновлення;
- подивитися Git-статус;
- зробити локальний коміт прямо з GUI.
"""

from __future__ import annotations

import json
import csv
import hashlib
import os
import shutil
import shlex
import re
import time
import traceback
from datetime import datetime
from collections import Counter
import subprocess
import sys
import threading
import tkinter as tk
import webbrowser
from urllib.error import URLError
from urllib.request import urlopen
from pathlib import Path
from tkinter import messagebox, ttk

from scripts.maintenance_preview import create_preview_file as create_maintenance_preview_file
from scripts.maintenance_owner_bypass import OWNER_LOGIN_URL, OWNER_LOGOUT_URL
from scripts.maintenance_server_control import (
    run_disable as run_maintenance_server_disable,
    run_enable as run_maintenance_server_enable,
    run_status as run_maintenance_server_status,
)
from scripts.maintenance_server_audit import (
    audit_server as audit_maintenance_server,
    audit_server_privileged as audit_privileged_maintenance_server,
)

try:
    import paramiko
except Exception:  # pragma: no cover - optional dependency
    paramiko = None


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SETTINGS_PATH = PROJECT_ROOT / "product_center_settings.json"
HISTORY_PATH = PROJECT_ROOT / "product_center_history.jsonl"
APP_LOG_PATH = PROJECT_ROOT / "product_center_app.log"
UPDATE_PACKAGES_DIR = PROJECT_ROOT / "docs" / "update_packages"
UPDATE_PACKAGES_STATE_FILE = UPDATE_PACKAGES_DIR / ".update_package_state.json"


def resolve_repo_python(root: Path) -> Path:
    candidate = root / ".venv" / "Scripts" / "python.exe"
    if candidate.exists():
        return candidate
    raise FileNotFoundError(f"Missing canonical repo Python: {candidate}")


PYTHON = resolve_repo_python(PROJECT_ROOT)
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
LOCAL_API_HEALTH_URL = "http://127.0.0.1:8000/health"
LOCAL_API_DOCS_URL = "http://127.0.0.1:8000/docs"
LOCAL_APP_URL = "http://127.0.0.1:5175"
LOCAL_ADMIN_URL = "http://127.0.0.1:5173"
REMOTE_ADMIN_WEBROOT = "/var/www/furniture-admin"


def prepare_tk_runtime() -> None:
    runtime_tcl = PROJECT_ROOT / "runtime" / "tcl"
    tcl_dir = runtime_tcl / "tcl8.6"
    tk_dir = runtime_tcl / "tk8.6"
    if tcl_dir.exists():
        os.environ.setdefault("TCL_LIBRARY", str(tcl_dir))
    if tk_dir.exists():
        os.environ.setdefault("TK_LIBRARY", str(tk_dir))


def default_main_db() -> str:
    return str((PROJECT_ROOT / "furniture_platform.db").resolve())


def default_legacy_db() -> str:
    return str((PROJECT_ROOT / "mebli_calculator.db").resolve())


def build_local_command(main_db: str, backup: bool) -> list[str]:
    command = [
        str(PYTHON),
        str(PROJECT_ROOT / "scripts" / "safe_update_db.py"),
        "--database",
        main_db,
    ]
    if not backup:
        command.append("--no-backup")
    return command


def format_windows_env(main_db: str, legacy_db: str) -> str:
    return (
        f'$env:FURNITURE_PLATFORM_DB_PATH = "{main_db}"\n'
        f'$env:FURNITURE_LEGACY_DB_PATH = "{legacy_db}"'
    )


def format_linux_env(main_db: str, legacy_db: str) -> str:
    return (
        f'export FURNITURE_PLATFORM_DB_PATH="{main_db}"\n'
        f'export FURNITURE_LEGACY_DB_PATH="{legacy_db}"'
    )


def format_local_env(main_db: str) -> str:
    return f'$env:FURNITURE_PLATFORM_DB_PATH = "{main_db}"'


def remote_python_prefix() -> str:
    return (
        'REMOTE_PYTHON="$(if [ -x ./.venv/bin/python ]; then printf "%s" ./.venv/bin/python; '
        'elif [ -x ./venv/bin/python ]; then printf "%s" ./venv/bin/python; '
        'elif command -v python3 >/dev/null 2>&1; then command -v python3; '
        'else command -v python; fi)" && '
        'if [ -z "$REMOTE_PYTHON" ]; then echo "No Python interpreter found" >&2; exit 1; fi'
    )


def remote_python_step(script_args: str) -> str:
    return f'{remote_python_prefix()} && "$REMOTE_PYTHON" {script_args}'


def format_ssh_command(
    server_host: str,
    server_port: str,
    server_user: str,
    ssh_key_path: str,
) -> str:
    host = server_host.strip() or "<host>"
    port = server_port.strip() or "22"
    user = server_user.strip() or "<user>"
    key_path = ssh_key_path.strip()
    base = ["ssh"]
    if key_path:
        base.extend(["-i", f'"{key_path}"'])
    base.extend(["-p", port, f"{user}@{host}"])
    return " ".join(base)


def build_ssh_probe_command(
    server_host: str,
    server_port: str,
    server_user: str,
    ssh_key_path: str,
) -> list[str]:
    host = server_host.strip()
    user = server_user.strip()
    if not host or not user:
        return []

    command = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10"]
    if ssh_key_path.strip():
        command.extend(["-i", ssh_key_path.strip()])
    command.extend(["-p", server_port.strip() or "22", f"{user}@{host}", "echo SERVER_OK"])
    return command


def _probe_server_with_paramiko(
    server_host: str,
    server_port: str,
    server_user: str,
    ssh_key_path: str,
    server_password: str,
) -> tuple[bool, str]:
    client, error = _open_paramiko_client(
        server_host,
        server_port,
        server_user,
        ssh_key_path,
        server_password,
    )
    if client is None:
        return False, error or "Не вдалося встановити SSH-з'єднання."

    try:
        stdin, stdout, stderr = client.exec_command("echo SERVER_OK", timeout=10)
        stdout_text = stdout.read().decode("utf-8", errors="replace").strip()
        stderr_text = stderr.read().decode("utf-8", errors="replace").strip()
        exit_status = stdout.channel.recv_exit_status()

        output_text = stdout_text or stderr_text
        if exit_status == 0 and "SERVER_OK" in output_text:
            return True, "SERVER_OK"
        return False, output_text or f"SSH command finished with code {exit_status}"
    except Exception as exc:  # pragma: no cover - depends on remote host
        return False, str(exc)
    finally:
        client.close()


def _open_paramiko_client(
    server_host: str,
    server_port: str,
    server_user: str,
    ssh_key_path: str,
    server_password: str,
):
    if paramiko is None:
        return (
            None,
            "Для SSH-автоматизації потрібна бібліотека paramiko. "
            "Додай її в requirements.txt і встанови залежності.",
        )

    key_path = ssh_key_path.strip()
    password = server_password.strip()
    if not key_path and not password:
        return None, "Потрібен або SSH key, або пароль для входу на сервер."

    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        connect_kwargs: dict[str, object] = {
            "hostname": server_host,
            "port": int(server_port or "22"),
            "username": server_user,
            "timeout": 10,
            "banner_timeout": 10,
            "auth_timeout": 10,
            "allow_agent": True,
            "look_for_keys": True,
        }

        if key_path:
            connect_kwargs["key_filename"] = key_path
        if password:
            connect_kwargs["password"] = password

        client.connect(**connect_kwargs)
        return client, None
    except paramiko.AuthenticationException:
        return (
            None,
            "Authentication failed. Перевір SSH key або SSH password для цього сервера. "
            "Якщо пароль не зберігається, введи його ще раз перед оновленням.",
        )
    except Exception as exc:  # pragma: no cover - depends on remote host
        return None, str(exc)


def _collect_channel_output(channel, timeout_seconds: float = 600.0) -> tuple[str, str, int]:
    deadline = time.monotonic() + timeout_seconds
    stdout_chunks: list[str] = []
    stderr_chunks: list[str] = []

    while True:
        while channel.recv_ready():
            stdout_chunks.append(channel.recv(4096).decode("utf-8", errors="replace"))
        while channel.recv_stderr_ready():
            stderr_chunks.append(channel.recv_stderr(4096).decode("utf-8", errors="replace"))

        if channel.exit_status_ready() and not channel.recv_ready() and not channel.recv_stderr_ready():
            break

        if time.monotonic() > deadline:
            raise TimeoutError(f"Оновлення сервера перевищило {int(timeout_seconds)} секунд.")

        time.sleep(0.2)

    exit_status = channel.recv_exit_status()
    while channel.recv_ready():
        stdout_chunks.append(channel.recv(4096).decode("utf-8", errors="replace"))
    while channel.recv_stderr_ready():
        stderr_chunks.append(channel.recv_stderr(4096).decode("utf-8", errors="replace"))

    return "".join(stdout_chunks).strip(), "".join(stderr_chunks).strip(), exit_status


def _run_remote_update_with_paramiko(
    server_host: str,
    server_port: str,
    server_user: str,
    ssh_key_path: str,
    server_password: str,
    server_path: str,
    restart: bool,
) -> tuple[bool, str]:
    client, error = _open_paramiko_client(
        server_host,
        server_port,
        server_user,
        ssh_key_path,
        server_password,
    )
    if client is None:
        return False, error or "Не вдалося встановити SSH-з'єднання."

    remote_path = shlex.quote(server_path.strip() or ".")
    command_parts = [
        f"cd {remote_path}",
        f"git config --global --replace-all safe.directory {remote_path}",
        "git pull",
    ]
    if restart:
        command_parts.append("sudo -S -p '' systemctl restart furniture-api furniture-bot")

    remote_command = " && ".join(command_parts)
    password = server_password.strip()

    try:
        stdin, stdout, stderr = client.exec_command(remote_command, get_pty=True, timeout=60)
        if restart and password:
            stdin.write(password + "\n")
            stdin.flush()

        stdout_text, stderr_text, exit_status = _collect_channel_output(stdout.channel, timeout_seconds=600.0)
        combined = "\n".join(part for part in [stdout_text, stderr_text] if part)
        if exit_status == 0:
            return True, combined or "Remote update completed successfully."
        return False, combined or f"Remote command finished with code {exit_status}"
    except Exception as exc:  # pragma: no cover - depends on remote host
        return False, str(exc)
    finally:
        client.close()


def format_server_block(
    main_db: str,
    legacy_db: str,
    server_path: str,
    server_host: str,
    server_port: str,
    server_user: str,
    ssh_key_path: str,
    restart: bool,
) -> str:
    lines = [
        "Команда входу на сервер:",
        format_ssh_command(server_host, server_port, server_user, ssh_key_path),
        "",
        "cd " + server_path,
        "git pull",
        remote_python_step('-m pip install -r requirements.txt'),
        format_linux_env(main_db, legacy_db),
        remote_python_step('scripts/safe_update_db.py'),
    ]
    if restart:
        lines.append("sudo systemctl restart furniture-api furniture-bot")
    return "\n".join(lines)


def git_available() -> bool:
    try:
        result = subprocess.run(
            ["git", "--version"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return False
    return result.returncode == 0


def git_config_value(key: str) -> str:
    result = subprocess.run(
        ["git", "config", "--get", key],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip()


def git_status_text() -> str:
    result = subprocess.run(
        ["git", "status", "--short", "--branch", "--untracked-files=all"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "Git status failed").strip())
    return result.stdout.strip() or "  ."


def git_status_entries() -> list[tuple[str, str]]:
    result = subprocess.run(
        ["git", "status", "--short", "--untracked-files=all"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "Git status failed").strip())

    entries: list[tuple[str, str]] = []
    for raw_line in result.stdout.splitlines():
        if len(raw_line) < 4:
            continue
        status = raw_line[:2].strip() or "??"
        path = raw_line[3:].strip()
        if path:
            entries.append((status, path))
    return entries


def file_sha256(path: Path) -> str | None:
    if not path.is_file():
        return None

    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


def load_update_package_state() -> dict[str, object]:
    if not UPDATE_PACKAGES_STATE_FILE.exists():
        latest_package = None
        latest_index = 0
        if UPDATE_PACKAGES_DIR.exists():
            for candidate in UPDATE_PACKAGES_DIR.glob("update_*.json"):
                index = update_package_index(candidate)
                if index is not None and index >= latest_index:
                    latest_index = index
                    latest_package = candidate

        if latest_package is None:
            return {}

        try:
            payload = json.loads(latest_package.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

        source_files = payload.get("source_files", [])
        if not isinstance(source_files, list):
            return {}

        return {
            "package_version": payload.get("package_version"),
            "created_at": payload.get("created_at"),
            "files": {
                path.replace("\\", "/").strip(): file_sha256(PROJECT_ROOT / path.replace("\\", "/").strip())
                for path in source_files
                if isinstance(path, str) and path.strip() and not is_generated_update_package_file(path)
            },
        }

    try:
        payload = json.loads(UPDATE_PACKAGES_STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    return payload if isinstance(payload, dict) else {}


def save_update_package_state(package_version: str, source_files: list[str]) -> None:
    UPDATE_PACKAGES_DIR.mkdir(parents=True, exist_ok=True)
    state = {
        "package_version": package_version,
        "created_at": current_timestamp(),
        "files": {
            path.replace("\\", "/").strip(): file_sha256(PROJECT_ROOT / path.replace("\\", "/").strip())
            for path in source_files
            if path.strip() and not is_generated_update_package_file(path)
        },
    }
    UPDATE_PACKAGES_STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def git_add_all() -> tuple[int, str]:
    result = subprocess.run(
        ["git", "add", "-A"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    output = (result.stdout + "\n" + result.stderr).strip()
    return result.returncode, output


def git_add_paths(paths: list[str]) -> tuple[int, str]:
    if not paths:
        return 0, ""

    result = subprocess.run(
        ["git", "add", "--", *paths],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    output = (result.stdout + "\n" + result.stderr).strip()
    return result.returncode, output


def git_staged_paths() -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return []

    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def git_push() -> tuple[int, str]:
    result = subprocess.run(
        ["git", "push"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    output = (result.stdout + "\n" + result.stderr).strip()
    return result.returncode, output


def python_command(*parts: str) -> list[str]:
    return [str(PYTHON), *parts]


def npm_command(*parts: str) -> list[str]:
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if not npm:
        return ["npm", *parts]
    return [npm, *parts]


def safe_subprocess_kwargs() -> dict:
    kwargs: dict = {}
    if CREATE_NO_WINDOW:
        kwargs["creationflags"] = CREATE_NO_WINDOW
    return kwargs


def git_commit(message: str, paths: list[str] | None = None) -> tuple[int, str]:
    command = ["git", "commit"]
    if paths:
        command.extend(["--only", "-m", message, "--", *paths])
    else:
        command.extend(["-m", message])
    result = subprocess.run(
        command,
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    output = (result.stdout + "\n" + result.stderr).strip()
    return result.returncode, output


def git_current_branch() -> str:
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def git_short_head_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def git_current_status_entries() -> list[tuple[str, str]]:
    if not git_available():
        return []

    try:
        return git_status_entries()
    except RuntimeError:
        return []


def update_package_index(path: Path) -> int | None:
    match = re.search(r"update_(\d+)\.(?:json|md)$", path.name, re.IGNORECASE)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def next_update_package_version() -> str:
    UPDATE_PACKAGES_DIR.mkdir(parents=True, exist_ok=True)
    indexes = [
        index
        for index in (
            update_package_index(path)
            for path in UPDATE_PACKAGES_DIR.glob("update_*.*")
        )
        if index is not None
    ]
    next_index = max(indexes, default=0) + 1
    return f"update_{next_index:04d}"


def normalize_update_file_type(path: str) -> str:
    normalized = path.replace("\\", "/").lower()

    if normalized.endswith((".db", ".sqlite", ".sqlite3")) or normalized.startswith(
        ("database/", "scripts/safe_update_db.py", "scripts/repair_", "scripts/seed_", "scripts/upgrade_")
    ):
        return "database"

    if normalized.startswith(("api/", "services/", "handlers/", "models/", "schemas/", "main.py", "main_api.py")):
        return "code"

    if normalized.startswith(("frontend/", "branding/", "runtime/", "build/")) or normalized.endswith(
        (".jsx", ".tsx", ".ts", ".js", ".css", ".scss", ".html", ".json")
    ):
        return "ui"

    if normalized.startswith(("docs/", "README", ".md")):
        return "docs"

    return "other"


def is_generated_update_package_file(path: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    return normalized.startswith("docs/update_packages/")


def build_update_package_plan(file_types: set[str]) -> list[str]:
    steps: list[str] = []

    def add_step(text: str) -> None:
        steps.append(f"{len(steps) + 1}. {text}")

    add_step("На сервері виконати `git pull`.")

    if "database" in file_types:
        add_step("Запустити `scripts/safe_update_db.py` з резервною копією.")

    if "ui" in file_types:
        add_step("Зібрати фронтенд після оновлення коду.")

    if "code" in file_types or "ui" in file_types:
        add_step("Перезапустити API, bot і фронтенди після оновлення.")

    if len(steps) == 1:
        add_step("Оновлення не потребує окремої міграції БД або перезапуску.")

    return steps


def build_update_package_payload(source_files: list[str]) -> dict[str, object]:
    normalized_files = []
    seen: set[str] = set()
    for path in source_files:
        rel_path = str(path).replace("\\", "/").strip()
        if not rel_path or rel_path in seen or is_generated_update_package_file(rel_path):
            continue
        seen.add(rel_path)
        normalized_files.append(rel_path)

    file_groups: dict[str, list[str]] = {
        "code": [],
        "database": [],
        "ui": [],
        "docs": [],
        "other": [],
    }

    for rel_path in normalized_files:
        file_groups[normalize_update_file_type(rel_path)].append(rel_path)

    package_version = next_update_package_version()
    created_at = current_timestamp()
    file_types = {kind for kind, values in file_groups.items() if values}

    return {
        "package_version": package_version,
        "created_at": created_at,
        "branch": git_current_branch() or None,
        "head_commit": git_short_head_commit() or None,
        "source_files": normalized_files,
        "file_groups": file_groups,
        "file_types": sorted(file_types),
        "server_plan": build_update_package_plan(file_types),
    }


def render_update_package_markdown(payload: dict[str, object]) -> str:
    lines = [
        f"# Update package {payload['package_version']}",
        "",
        f"- Created: {payload['created_at']}",
        f"- Branch: {payload.get('branch') or 'n/a'}",
        f"- Head commit: {payload.get('head_commit') or 'n/a'}",
        f"- File count: {len(payload.get('source_files', []))}",
        "",
        "## Files",
    ]

    file_groups = payload.get("file_groups", {})
    for group_name in ["code", "database", "ui", "docs", "other"]:
        files = file_groups.get(group_name, [])
        if not files:
            continue
        lines.append(f"- {group_name}:")
        for item in files:
            lines.append(f"  - {item}")

    lines.extend(
        [
            "",
            "## Server plan",
        ]
    )
    for step in payload.get("server_plan", []):
        lines.append(f"- {step}")

    return "\n".join(lines).strip() + "\n"


def render_update_package_json(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def as_bool(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on", "так"}:
            return True
        if lowered in {"0", "false", "no", "off", "ні"}:
            return False
    if value is None:
        return default
    return bool(value)


def current_timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def app_log(message: str) -> None:
    line = f"[{current_timestamp()}] {message}\n"
    try:
        with APP_LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(line)
    except OSError:
        pass


def read_json_lines(path: Path, limit: int = 200) -> list[dict[str, object]]:
    if not path.exists():
        return []

    lines = []
    try:
        raw_lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []

    for raw_line in raw_lines[-limit:]:
        try:
            item = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            lines.append(item)
    return lines


def history_category(action: str) -> str:
    if action.startswith("git."):
        return "Git"
    if action.startswith("process."):
        return "Процеси"
    if action.startswith("db."):
        return "БД"
    if action.startswith("settings."):
        return "Налаштування"
    if action.startswith("script."):
        return "Скрипти"
    return "Інше"


def history_search_text(entry: dict[str, object]) -> str:
    parts = [
        str(entry.get("timestamp", "")),
        str(entry.get("action", "")),
        str(entry.get("status", "")),
        str(entry.get("details", "")),
        json.dumps(entry.get("files", []), ensure_ascii=False),
        json.dumps(entry.get("command", []), ensure_ascii=False),
        json.dumps(entry.get("extra", {}), ensure_ascii=False),
    ]
    return " ".join(parts).lower()


def history_entry_date(entry: dict[str, object]) -> str:
    timestamp = str(entry.get("timestamp", ""))
    if not timestamp:
        return ""
    try:
        return datetime.fromisoformat(timestamp).date().isoformat()
    except ValueError:
        return timestamp[:10]


def resolve_component_files(patterns: list[str]) -> list[str]:
    resolved: list[str] = []
    seen: set[str] = set()

    for pattern in patterns:
        matches: list[Path]
        if any(token in pattern for token in "*?[]"):
            matches = [path for path in PROJECT_ROOT.glob(pattern) if path.is_file()]
        else:
            candidate = PROJECT_ROOT / pattern
            matches = [candidate] if candidate.is_file() else []

        for path in matches:
            try:
                rel_path = path.relative_to(PROJECT_ROOT).as_posix()
            except ValueError:
                rel_path = path.as_posix()
            if rel_path not in seen:
                seen.add(rel_path)
                resolved.append(rel_path)

    return resolved


def build_product_component_specs() -> list[dict[str, object]]:
    return [
        {
            "key": "api",
            "group": "Сервер",
            "name": "API",
            "summary": "FastAPI backend для auth, projects, catalog, audit і fitting holes.",
            "responsibility": "Приймає запити від інтерфейсів, працює з БД і віддає дані для аналізу та редагування.",
            "process_key": "api",
            "start_command": python_command(str(PROJECT_ROOT / "main_api.py")),
            "cwd": PROJECT_ROOT,
            "open_targets": [LOCAL_API_DOCS_URL],
            "file_patterns": [
                "main_api.py",
                "api/routes/*.py",
                "api/dependencies/*.py",
                "database/init_db.py",
                "database/repositories/*.py",
                "services/material_import_queue_service.py",
                "services/catalog_auto_refresh_service.py",
            ],
            "depends_on": ["База даних", "Frontend admin", "Frontend app"],
            "control": "Запуск / стоп",
        },
        {
            "key": "bot",
            "group": "Сервер",
            "name": "Бот",
            "summary": "Telegram-бот і фонові задачі синхронізації.",
            "responsibility": "Обробляє Telegram-взаємодію, ініціалізує БД, запускає планувальник і MT-логіку.",
            "process_key": "bot",
            "start_command": python_command(str(PROJECT_ROOT / "main.py")),
            "cwd": PROJECT_ROOT,
            "open_targets": [PROJECT_ROOT / "main.py"],
            "file_patterns": [
                "main.py",
                "handlers/*.py",
                "services/scheduler.py",
                "services/mt_parser.py",
                "services/mt_kits_parser.py",
                "services/production_*.py",
                "services/database.py",
            ],
            "depends_on": ["База даних", "MT-дані", "Планувальник"],
            "control": "Запуск / стоп",
        },
        {
            "key": "app",
            "group": "Інтерфейси",
            "name": "Frontend app",
            "summary": "Публічний калькулятор і 3D-інтерфейс.",
            "responsibility": "Показує користувацький інтерфейс, працює через API і відображає проектні дані.",
            "process_key": "frontend-app",
            "start_command": ["npm", "run", "dev"],
            "cwd": PROJECT_ROOT / "frontend" / "app",
            "open_targets": [LOCAL_APP_URL],
            "file_patterns": [
                "frontend/app/src/*.jsx",
                "frontend/app/src/components/*.jsx",
                "frontend/app/src/*.css",
                "frontend/app/vite.config.js",
                "frontend/app/package.json",
            ],
            "depends_on": ["API", "База даних"],
            "control": "Запуск / стоп",
        },
        {
            "key": "admin",
            "group": "Інтерфейси",
            "name": "Frontend admin",
            "summary": "Адмін-панель для керування продуктом.",
            "responsibility": "Дає доступ до керування проектами, каталогом, аудитом і сервісними діями.",
            "process_key": "frontend-admin",
            "start_command": ["npm", "run", "dev"],
            "cwd": PROJECT_ROOT / "frontend" / "admin",
            "open_targets": [LOCAL_ADMIN_URL],
            "file_patterns": [
                "frontend/admin/src/*.jsx",
                "frontend/admin/src/components/*.jsx",
                "frontend/admin/src/*.css",
                "frontend/admin/vite.config.js",
                "frontend/admin/package.json",
            ],
            "depends_on": ["API", "База даних"],
            "control": "Запуск / стоп",
        },
        {
            "key": "database",
            "group": "Дані",
            "name": "База даних",
            "summary": "Основна SQLite-база з даними продукту.",
            "responsibility": "Зберігає дані проектів, каталогів, користувачів і службову інформацію.",
            "process_key": None,
            "start_command": None,
            "cwd": PROJECT_ROOT,
            "open_targets": [PROJECT_ROOT / "furniture_platform.db", PROJECT_ROOT / "mebli_calculator.db"],
            "file_patterns": [
                "furniture_platform.db",
                "mebli_calculator.db",
                "database/init_db.py",
            ],
            "depends_on": ["API", "Бот", "Скрипти БД"],
            "control": "Відкрити",
        },
        {
            "key": "scripts-db",
            "group": "Утиліти",
            "name": "Скрипти БД",
            "summary": "Безпечні оновлення, repair і seed-скрипти.",
            "responsibility": "Оновлює структуру бази без втрати користувацьких даних.",
            "process_key": None,
            "start_command": None,
            "cwd": PROJECT_ROOT,
            "open_targets": [
                PROJECT_ROOT / "scripts" / "safe_update_db.py",
                PROJECT_ROOT / "scripts" / "repair_catalog_data.py",
                PROJECT_ROOT / "scripts" / "seed_confirmat_190106_holes.py",
                PROJECT_ROOT / "scripts" / "upgrade_fittings_schema.py",
            ],
            "file_patterns": [
                "scripts/safe_update_db.py",
                "scripts/repair_catalog_data.py",
                "scripts/seed_confirmat_190106_holes.py",
                "scripts/upgrade_fittings_schema.py",
                "scripts/catalog_snapshot.py",
            ],
            "depends_on": ["База даних"],
            "control": "Відкрити",
        },
        {
            "key": "product-center",
            "group": "Керування",
            "name": "Product Center",
            "summary": "Центральна програма керування продуктом.",
            "responsibility": "Запускає сервіси, відкриває сторінки, веде історію та звіти.",
            "process_key": None,
            "start_command": None,
            "cwd": PROJECT_ROOT,
            "open_targets": [
                PROJECT_ROOT / "scripts" / "db_update_wizard.py",
                PROJECT_ROOT / "product_center.pyw",
                PROJECT_ROOT / "product_center_launcher.py",
            ],
            "file_patterns": [
                "scripts/db_update_wizard.py",
                "product_center.pyw",
                "product_center_launcher.py",
                "product_center_settings.json",
                "product_center_history.jsonl",
            ],
            "depends_on": ["Усі компоненти"],
            "control": "Відкрити",
        },
        {
            "key": "background",
            "group": "Сервер",
            "name": "Фонові служби",
            "summary": "Матеріали, каталоги та синхронізація, що стартують разом з API.",
            "responsibility": "Підтримує черги імпорту і автоновлення каталогу у фоні.",
            "process_key": "api",
            "start_command": None,
            "cwd": PROJECT_ROOT,
            "open_targets": [
                PROJECT_ROOT / "services" / "material_import_queue_service.py",
                PROJECT_ROOT / "services" / "catalog_auto_refresh_service.py",
            ],
            "file_patterns": [
                "services/material_import_queue_service.py",
                "services/catalog_auto_refresh_service.py",
                "services/scheduler.py",
            ],
            "depends_on": ["API"],
            "control": "Працює через API",
        },
    ]


def component_files(spec: dict[str, object]) -> list[str]:
    patterns = [str(pattern) for pattern in spec.get("file_patterns", []) or []]
    return resolve_component_files(patterns)


def component_open_targets(spec: dict[str, object]) -> list[object]:
    return list(spec.get("open_targets", []) or [])


def component_control_label(spec: dict[str, object]) -> str:
    control = str(spec.get("control", "")).strip()
    if control:
        return control
    if spec.get("start_command"):
        return "Запуск / стоп"
    return "Відкрити"


def component_search_text(spec: dict[str, object]) -> str:
    parts = [
        str(spec.get("key", "")),
        str(spec.get("group", "")),
        str(spec.get("name", "")),
        str(spec.get("summary", "")),
        str(spec.get("responsibility", "")),
        str(spec.get("control", "")),
        " ".join(str(item) for item in spec.get("depends_on", []) or []),
        " ".join(component_files(spec)),
    ]
    return " ".join(parts).lower()


class WizardApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        app_log("WizardApp.__init__ start")
        self.title("Майстер оновлення бази даних")
        try:
            self.iconbitmap(default=str(PROJECT_ROOT / "branding" / "icons" / "favicon.ico"))
        except tk.TclError:
            pass
        self.geometry("1480x920")
        self.minsize(1200, 780)
        try:
            self.state("zoomed")
        except tk.TclError:
            pass

        self._setup_style()

        self.mode = tk.StringVar(value="local")
        self.main_db = tk.StringVar(value=default_main_db())
        self.legacy_db = tk.StringVar(value=default_legacy_db())
        self.server_path = tk.StringVar(value="/opt/furniture-stage")
        self.server_host = tk.StringVar(value="")
        self.server_port = tk.StringVar(value="22")
        self.server_user = tk.StringVar(value="")
        self.ssh_key_path = tk.StringVar(value="")
        self.server_password = tk.StringVar(value="")
        self.sudo_password = tk.StringVar(value="")
        self.backup = tk.BooleanVar(value=True)
        self.run_safe_update = tk.BooleanVar(value=True)
        self.restart_services = tk.BooleanVar(value=True)
        self.commit_message = tk.StringVar(value="Оновлення проєкту")
        self.catalog_city = tk.StringVar(value="Київ")
        self.catalog_warm_images = tk.BooleanVar(value=True)
        self.auto_refresh = tk.BooleanVar(value=True)
        self.allow_local_registration = tk.BooleanVar(value=False)
        self.allow_local_registration_test_mode = tk.BooleanVar(value=False)
        self.maintenance_message = tk.StringVar(
            value="Ми оновлюємо платформу. Ваші проєкти та дані збережені."
        )
        self.maintenance_eta = tk.StringVar(value="Найближчим часом")
        self.maintenance_preview_status = tk.StringVar(value="Серверний режим ще не налаштовано.")
        self.maintenance_server_control_status = tk.StringVar(value="Статус технічних робіт ще не перевірено.")
        self.maintenance_server_audit_status = tk.StringVar(value="Перевірку ще не виконано.")
        self.maintenance_server_audit_summary = tk.StringVar(
            value="Натисни «Перевірити сервер», щоб запустити read-only аудит production nginx."
        )
        self._maintenance_server_audit_report = ""
        self._maintenance_server_audit_window: tk.Toplevel | None = None
        self._maintenance_server_audit_running = False
        self._maintenance_server_control_running = False
        self._maintenance_server_control_last_result: object | None = None
        self._maintenance_server_control_details_window: tk.Toplevel | None = None
        self.map_search = tk.StringVar(value="")
        self.history_search = tk.StringVar(value="")
        self.history_filter = tk.StringVar(value="Усі")
        self.history_report_date = tk.StringVar(value=datetime.now().date().isoformat())
        self.update_package_source = tk.StringVar(value="changed")
        self.update_package_version = tk.StringVar(value="—")
        self.update_package_path = tk.StringVar(value="—")
        self.update_package_files_summary = tk.StringVar(value="Ще немає пакетів.")
        self.update_package_snapshot_summary = tk.StringVar(value="Вже упаковано: —")
        self.update_package_new_summary = tk.StringVar(value="Нові зміни: —")
        self.update_package_ready_summary = tk.StringVar(value="Готово до пакета: —")
        self._busy_tasks = 0
        self._last_update_package_payload: dict[str, object] | None = None
        self.activity_progress: ttk.Progressbar | None = None
        self._activity_tick_after: str | None = None
        self._activity_reset_after: str | None = None
        self.git_file_paths: list[str] = []
        self.managed_processes: dict[str, subprocess.Popen] = {}
        self.action_buttons: dict[str, list[ttk.Button]] = {}
        self.service_status_vars: dict[str, tk.StringVar] = {}
        self.service_status_labels: dict[str, ttk.Label] = {}
        self.component_launch_vars: dict[str, tk.StringVar] = {}
        self.component_launch_labels: dict[str, ttk.Label] = {}
        self.component_launch_markers: dict[str, ttk.Label] = {}
        self.launch_status_var = tk.StringVar(value="")
        self.product_map_specs = build_product_component_specs()
        self.product_map_specs_by_key = {str(spec["key"]): spec for spec in self.product_map_specs}
        self.product_map_selected_key: str | None = None
        self._saved_settings_snapshot = self.settings_data()
        self._startup_ready = False

        app_log("WizardApp.__init__ before build_ui")
        self._build_ui()
        app_log("WizardApp.__init__ after build_ui")
        self.load_settings()
        app_log("WizardApp.__init__ after load_settings")
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.update_idletasks()
        self.after(50, self._finish_startup)

    def _bring_to_front(self) -> None:
        try:
            self.deiconify()
            self.state("normal")
            self.lift()
            self.focus_force()
            self.attributes("-topmost", True)
            self.after(250, lambda: self.attributes("-topmost", False))
        except tk.TclError:
            pass

    def _finish_startup(self) -> None:
        self.refresh_db_preview()
        self.refresh_history()
        self.refresh_managed_processes()
        self.refresh_git_status_async()
        self.refresh_product_status_async()
        self._schedule_process_refresh()
        self.after(0, self._bring_to_front)
        self._startup_ready = True

    def refresh_all_views(self) -> None:
        app_log("refresh_all_views")
        self.refresh_db_preview()
        self.refresh_history()
        self.refresh_managed_processes()
        self.refresh_git_status_async()
        self.refresh_product_status_async()
        self.refresh_product_map()

    def _setup_style(self) -> None:
        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")

        palette = {
            "bg": "#eef2f1",
            "panel": "#ffffff",
            "panel_soft": "#f8faf9",
            "text": "#1f2d2b",
            "muted": "#667573",
            "accent": "#0f766e",
            "accent_dark": "#0b5f59",
            "accent_soft": "#d7f0ed",
            "line": "#d9e3e1",
            "success_bg": "#dcf5df",
            "success_fg": "#14532d",
            "success": "#dcf5df",
            "warn_bg": "#fff1c9",
            "warn_fg": "#7a4b00",
            "danger_bg": "#ffd7d7",
            "danger_fg": "#7f1d1d",
        }

        self.configure(background=palette["bg"])
        self.option_add("*Font", ("Segoe UI", 10))

        style.configure(".", background=palette["bg"], foreground=palette["text"])
        style.configure("Root.TFrame", background=palette["bg"])
        style.configure("Header.TFrame", background=palette["bg"])
        style.configure("AccentBar.TFrame", background=palette["accent"])
        style.configure("Pill.TLabel", background=palette["accent_soft"], foreground=palette["accent_dark"], font=("Segoe UI", 9, "bold"), padding=(10, 4))
        style.configure("Card.TLabelframe", background=palette["panel"], padding=16)
        style.configure("Card.TLabelframe.Label", background=palette["panel"], foreground=palette["text"], font=("Segoe UI Semibold", 10))
        style.configure("Title.TLabel", background=palette["bg"], foreground=palette["text"], font=("Segoe UI Semibold", 22))
        style.configure("Subtitle.TLabel", background=palette["bg"], foreground=palette["muted"], font=("Segoe UI", 10))
        style.configure("Hint.TLabel", background=palette["panel"], foreground=palette["muted"], font=("Segoe UI", 9))
        style.configure("Section.TLabel", background=palette["panel"], foreground=palette["text"], font=("Segoe UI Semibold", 11))
        style.configure("ServiceOnline.TLabel", background=palette["success_bg"], foreground=palette["success_fg"], font=("Segoe UI Semibold", 20))
        style.configure("ServiceReconnecting.TLabel", background=palette["warn_bg"], foreground=palette["warn_fg"], font=("Segoe UI Semibold", 20))
        style.configure("ServiceOffline.TLabel", background=palette["danger_bg"], foreground=palette["danger_fg"], font=("Segoe UI Semibold", 20))
        style.configure("ServiceUnknown.TLabel", background="#e7edf0", foreground="#334155", font=("Segoe UI Semibold", 20))
        style.configure("LaunchOnline.TLabel", background=palette["success_bg"], foreground=palette["success_fg"], font=("Segoe UI", 10, "bold"))
        style.configure("LaunchStarting.TLabel", background=palette["warn_bg"], foreground=palette["warn_fg"], font=("Segoe UI", 10, "bold"))
        style.configure("LaunchOffline.TLabel", background=palette["danger_bg"], foreground=palette["danger_fg"], font=("Segoe UI", 10, "bold"))
        style.configure("LaunchUnknown.TLabel", background="#e7edf0", foreground="#334155", font=("Segoe UI", 10, "bold"))
        style.configure("Primary.TButton", padding=(16, 9), font=("Segoe UI Semibold", 10), background=palette["accent"], foreground="#ffffff")
        style.configure("TButton", padding=(14, 8), font=("Segoe UI", 10), background="#edf2f1", foreground=palette["text"])
        style.configure("ActionIdle.TButton", padding=(14, 8), font=("Segoe UI", 10))
        style.configure("ActionStarting.TButton", padding=(14, 8), font=("Segoe UI", 10, "bold"), background=palette["warn_bg"], foreground=palette["warn_fg"])
        style.configure("ActionSuccess.TButton", padding=(14, 8), font=("Segoe UI", 10, "bold"), background=palette["success_bg"], foreground=palette["success_fg"])
        style.configure("ActionError.TButton", padding=(14, 8), font=("Segoe UI", 10, "bold"), background=palette["danger_bg"], foreground=palette["danger_fg"])
        style.map("TButton", background=[("active", "#e3ecea"), ("pressed", "#d6e2df")])
        style.map("Primary.TButton", background=[("active", palette["accent_dark"]), ("pressed", "#094a45")], foreground=[("disabled", "#d5e3e1")])
        style.map("ActionStarting.TButton", background=[("active", "#ffe8a3"), ("pressed", "#ffd966")])
        style.map("ActionSuccess.TButton", background=[("active", "#c8eec6"), ("pressed", "#b7e7b5")])
        style.map("ActionError.TButton", background=[("active", "#ffc2c2"), ("pressed", "#ffadad")])
        style.configure(
            "TNotebook",
            background=palette["bg"],
            borderwidth=0,
            tabmargins=(6, 6, 6, 0),
        )
        style.configure(
            "TNotebook.Tab",
            background="#dfe7e5",
            foreground=palette["muted"],
            padding=(16, 8),
            font=("Segoe UI", 10, "bold"),
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", palette["panel"]), ("active", "#eaf2f0")],
            foreground=[("selected", palette["text"]), ("active", palette["text"])],
        )
        style.configure(
            "Accent.Horizontal.TProgressbar",
            troughcolor="#e4ece9",
            background=palette["success_bg"],
            bordercolor="#d3e3dd",
            lightcolor=palette["success_bg"],
            darkcolor=palette["success_fg"],
        )
        style.configure(
            "Treeview",
            background=palette["panel"],
            fieldbackground=palette["panel"],
            foreground=palette["text"],
            rowheight=28,
            bordercolor=palette["line"],
            lightcolor=palette["panel"],
            darkcolor=palette["panel"],
        )
        style.configure(
            "Treeview.Heading",
            background="#dfe7e5",
            foreground=palette["text"],
            font=("Segoe UI Semibold", 9),
            relief="flat",
            padding=(8, 6),
        )
        style.map("Treeview", background=[("selected", palette["accent_soft"])], foreground=[("selected", palette["text"])])
        style.configure("TScrollbar", background=palette["bg"], troughcolor=palette["bg"], borderwidth=0, arrowsize=12)
        style.configure("TEntry", padding=6)
        style.configure("TCheckbutton", background=palette["panel"], foreground=palette["text"], padding=(4, 2))
        style.map("TCheckbutton", background=[("active", palette["panel"]), ("selected", palette["panel"])])

    def _register_action_button(self, key: str, button: ttk.Button) -> ttk.Button:
        self.action_buttons.setdefault(key, []).append(button)
        return button

    def _set_action_button_state(self, key: str, state: str) -> None:
        style_map = {
            "idle": "ActionIdle.TButton",
            "starting": "ActionStarting.TButton",
            "success": "ActionSuccess.TButton",
            "error": "ActionError.TButton",
        }
        style_name = style_map.get(state, "ActionIdle.TButton")
        for button in self.action_buttons.get(key, []):
            try:
                button.configure(style=style_name)
            except tk.TclError:
                pass

    def _service_url_for_key(self, key: str) -> str | None:
        if key == "api":
            return LOCAL_API_HEALTH_URL
        if key == "frontend-app":
            return LOCAL_APP_URL
        if key == "frontend-admin":
            return LOCAL_ADMIN_URL
        return None

    def _managed_button_state(self, key: str, proc: subprocess.Popen | None) -> str:
        if proc is None or proc.poll() is not None:
            return "idle"
        url = self._service_url_for_key(key)
        if url and not self._service_responds(url):
            return "starting"
        return "success"

    def _managed_component_status(self, key: str, proc: subprocess.Popen | None) -> str:
        if proc is None or proc.poll() is not None:
            return "не запущено"
        if key == "bot":
            return self._bot_runtime_status(True)
        url = self._service_url_for_key(key)
        if url and not self._service_responds(url):
            return "запускається..."
        return "працює"

    def _process_list_colors(self, status_text: str) -> tuple[str, str]:
        normalized = status_text.strip().lower()
        if "працює" in normalized or "online" in normalized:
            return "#d9f5d8", "#14532d"
        if "запуска" in normalized or "starting" in normalized:
            return "#fff2cc", "#7a4b00"
        if "token invalid" in normalized:
            return "#ffd6d6", "#7f1d1d"
        if "зупинено" in normalized or "offline" in normalized or "не запущено" in normalized:
            return "#ffd6d6", "#7f1d1d"
        return "#ffffff", "#1f2a29"

    def _service_status_style(self, status: str) -> str:
        normalized = status.strip().lower()
        if normalized == "online":
            return "ServiceOnline.TLabel"
        if normalized in {"reconnecting", "starting"}:
            return "ServiceReconnecting.TLabel"
        if normalized in {"offline", "token invalid"}:
            return "ServiceOffline.TLabel"
        return "ServiceUnknown.TLabel"

    def _apply_service_status_style(self, key: str, status: str) -> None:
        label = self.service_status_labels.get(key)
        if label is not None:
            label.configure(style=self._service_status_style(status))

    def _set_service_status(self, key: str, status: str) -> None:
        value = self.service_status_vars.setdefault(key, tk.StringVar())
        value.set(status)
        self._apply_service_status_style(key, status)

    def _set_launch_status(self, text: str) -> None:
        self.launch_status_var.set(text)

    def _set_component_launch_status(self, key: str, status: str) -> None:
        value = self.component_launch_vars.setdefault(key, tk.StringVar())
        value.set(status)
        label = self.component_launch_labels.get(key)
        if label is not None:
            label.configure(style=self._component_launch_style(status))
        marker = self.component_launch_markers.get(key)
        if marker is not None:
            marker.configure(foreground=self._component_launch_marker_color(status))

    def _component_launch_style(self, status: str) -> str:
        normalized = status.strip().lower()
        if normalized == "online":
            return "LaunchOnline.TLabel"
        if normalized == "starting":
            return "LaunchStarting.TLabel"
        if normalized in {"offline", "token invalid"}:
            return "LaunchOffline.TLabel"
        return "LaunchUnknown.TLabel"

    def _component_launch_marker_color(self, status: str) -> str:
        normalized = status.strip().lower()
        if normalized == "online":
            return "#1f7a1f"
        if normalized == "starting":
            return "#a26b00"
        if normalized in {"offline", "token invalid", "не запущено"}:
            return "#a61b1b"
        return "#475569"

    def _latest_app_log_lines(self, limit: int = 200) -> list[str]:
        log_path = PROJECT_ROOT / "product_center_app.log"
        if not log_path.exists():
            return []
        try:
            lines = log_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        if len(lines) <= limit:
            return lines
        return lines[-limit:]

    def _bot_runtime_status(self, bot_running: bool) -> str:
        if bot_running:
            lines = self._latest_app_log_lines()
            for line in reversed(lines):
                if "BOT_STATUS: unauthorized" in line:
                    return "token invalid"
                if "BOT_STATUS: reconnecting" in line:
                    return "reconnecting"
                if "BOT_STATUS: online" in line:
                    return "online"
            return "online"

        lines = self._latest_app_log_lines()
        for line in reversed(lines):
            if "BOT_STATUS: unauthorized" in line:
                return "token invalid"
            if "BOT_STATUS: reconnecting" in line:
                return "reconnecting"
            if "BOT_STATUS: online" in line:
                return "offline"
        return "offline"

    def _process_service_status(self, proc: subprocess.Popen | None, url_ok: bool) -> str:
        if proc is None or proc.poll() is not None:
            return "offline"
        if url_ok:
            return "online"
        return "starting"

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, style="Root.TFrame", padding=18)
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer, style="Header.TFrame")
        header.pack(fill="x")
        header.columnconfigure(0, weight=1)

        header_left = ttk.Frame(header, style="Header.TFrame")
        header_left.grid(row=0, column=0, sticky="ew")
        ttk.Label(header_left, text="Безпечне оновлення бази даних", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            header_left,
            text="Оберіть сценарій, поставте потрібні галочки і керуйте продуктом з одного вікна.",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(4, 0))

        header_right = ttk.Frame(header, style="Header.TFrame")
        header_right.grid(row=0, column=1, sticky="ne", padx=(16, 0))
        ttk.Label(header_right, text="Преміум центр керування", style="Pill.TLabel").pack(anchor="e")
        ttk.Label(
            header_right,
            text="Локальні сервіси, Git, історія і БД",
            style="Subtitle.TLabel",
        ).pack(anchor="e", pady=(8, 0))

        ttk.Separator(outer, orient="horizontal").pack(fill="x", pady=(14, 0))

        activity_row = ttk.Frame(outer, style="Root.TFrame")
        activity_row.pack(fill="x", pady=(14, 0))
        ttk.Label(activity_row, text="Виконання дії", style="Hint.TLabel").pack(side="left")
        self.activity_progress = ttk.Progressbar(
            activity_row,
            mode="determinate",
            maximum=100,
            value=0,
            style="Accent.Horizontal.TProgressbar",
        )
        self.activity_progress.pack(side="left", fill="x", expand=True, padx=(12, 0))

        quick_start = ttk.LabelFrame(outer, text="Швидкий старт", style="Card.TLabelframe")
        quick_start.pack(fill="x", pady=(14, 0))
        quick_start.columnconfigure(0, weight=1)
        ttk.Label(
            quick_start,
            text="Швидкий старт: 1) Продукт  2) Запустити весь продукт  3) Зелений = ок, червоний = проблема",
            style="Hint.TLabel",
            justify="left",
        ).pack(anchor="w")

        notebook = ttk.Notebook(outer)
        notebook.pack(fill="both", expand=True, pady=(16, 0))

        self.db_tab = ttk.Frame(notebook, style="Root.TFrame")
        self.git_tab = ttk.Frame(notebook, style="Root.TFrame")
        self.history_tab = ttk.Frame(notebook, style="Root.TFrame")
        self.map_tab = ttk.Frame(notebook, style="Root.TFrame")
        self.package_tab = ttk.Frame(notebook, style="Root.TFrame")
        self.product_tab = ttk.Frame(notebook, style="Root.TFrame")
        self.help_tab = ttk.Frame(notebook, style="Root.TFrame")
        notebook.add(self.db_tab, text="База")
        notebook.add(self.git_tab, text="Git")
        notebook.add(self.history_tab, text="Історія")
        notebook.add(self.map_tab, text="Карта продукту")
        notebook.add(self.package_tab, text="Версії")
        notebook.add(self.product_tab, text="Продукт")
        notebook.add(self.help_tab, text="Довідка")

        self._build_db_tab()
        self._build_git_tab()
        self._build_history_tab()
        self._build_map_tab()
        self._build_package_tab()
        self._build_product_tab()
        self._build_help_tab()
        self.bind_all("<MouseWheel>", self._on_mousewheel, add="+")

    def _build_scrollable_tab(self, tab: ttk.Frame) -> tuple[ttk.Frame, tk.Canvas]:
        container = ttk.Frame(tab, style="Root.TFrame")
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)

        canvas = tk.Canvas(container, highlightthickness=0, bd=0, bg=self.cget("background"))
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        canvas.configure(yscrollcommand=scrollbar.set)

        body = ttk.Frame(canvas, style="Root.TFrame", padding=4)
        body_window = canvas.create_window((0, 0), window=body, anchor="nw")

        def sync_scrollregion(_event: tk.Event | None = None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def sync_body_width(event: tk.Event) -> None:
            canvas.itemconfigure(body_window, width=event.width)

        body.bind("<Configure>", sync_scrollregion)
        canvas.bind("<Configure>", sync_body_width)
        return body, canvas

    def _widget_canvas(self, widget: tk.Misc | None) -> tk.Canvas | None:
        current = widget
        while current is not None:
            if isinstance(current, tk.Canvas):
                return current
            current = getattr(current, "master", None)
        return None

    def _schedule_activity_tick(self) -> None:
        if self.activity_progress is None or self._busy_tasks <= 0:
            return

        current_value = float(self.activity_progress["value"])
        next_value = min(90.0, current_value + 4.0)
        try:
            self.activity_progress.configure(value=next_value)
        except tk.TclError:
            return

        self._activity_tick_after = self.after(60, self._schedule_activity_tick)

    def _on_mousewheel(self, event: tk.Event) -> str | None:
        widget = getattr(event, "widget", None)
        if widget is None:
            return None
        widget_class = ""
        try:
            widget_class = widget.winfo_class()
        except tk.TclError:
            widget_class = ""
        if widget_class in {"Text", "Listbox", "Treeview"}:
            return None

        canvas = self._widget_canvas(widget)
        if canvas is None:
            return None

        delta = getattr(event, "delta", 0)
        if not delta:
            return None
        canvas.yview_scroll(int(-1 * (delta / 120)), "units")
        return "break"

    def _begin_activity(self) -> None:
        self._busy_tasks += 1
        if self._busy_tasks == 1 and self.activity_progress is not None:
            try:
                if self._activity_reset_after is not None:
                    self.after_cancel(self._activity_reset_after)
                    self._activity_reset_after = None
                if self._activity_tick_after is not None:
                    self.after_cancel(self._activity_tick_after)
                    self._activity_tick_after = None
                self.activity_progress.configure(value=0)
                self._schedule_activity_tick()
            except tk.TclError:
                pass

    def _end_activity(self) -> None:
        if self._busy_tasks > 0:
            self._busy_tasks -= 1
        if self._busy_tasks == 0 and self.activity_progress is not None:
            try:
                if self._activity_tick_after is not None:
                    self.after_cancel(self._activity_tick_after)
                    self._activity_tick_after = None
                self.activity_progress.configure(value=100)
                if self._activity_reset_after is not None:
                    self.after_cancel(self._activity_reset_after)
                self._activity_reset_after = self.after(220, self._reset_activity_progress)
            except tk.TclError:
                pass

    def _reset_activity_progress(self) -> None:
        self._activity_reset_after = None
        if self.activity_progress is None:
            return
        try:
            self.activity_progress.configure(value=0)
        except tk.TclError:
            pass

    def copy_update_package_plan(self) -> None:
        payload = self._last_update_package_payload
        if not payload:
            messagebox.showinfo("Немає плану", "Спочатку згенеруй або онови пакет версії.")
            return

        plan = payload.get("server_plan", []) or []
        text = "\n".join(str(item) for item in plan)
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()
        messagebox.showinfo("Скопійовано", "План дій скопійовано в буфер обміну.")

    def _build_db_tab(self) -> None:
        container = ttk.Frame(self.db_tab, style="Root.TFrame")
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)

        canvas = tk.Canvas(container, highlightthickness=0, bd=0, bg=self.cget("background"))
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        canvas.configure(yscrollcommand=scrollbar.set)

        body = ttk.Frame(canvas, style="Root.TFrame", padding=4)
        body_window = canvas.create_window((0, 0), window=body, anchor="nw")

        def sync_scrollregion(_event: tk.Event | None = None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def sync_body_width(event: tk.Event) -> None:
            canvas.itemconfigure(body_window, width=event.width)

        body.bind("<Configure>", sync_scrollregion)
        canvas.bind("<Configure>", sync_body_width)

        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(1, weight=1)

        settings = ttk.LabelFrame(body, text="Налаштування", style="Card.TLabelframe")
        settings.grid(row=0, column=0, columnspan=2, sticky="ew")
        settings.columnconfigure(1, weight=1)
        settings['padding'] = 18

        mode_box = ttk.Frame(settings)
        mode_box.grid(row=0, column=0, sticky="nw", padx=(0, 20))
        ttk.Label(mode_box, text="", style="Hint.TLabel").pack(anchor="w")
        ttk.Radiobutton(mode_box, text="Локальний тест", value="local", variable=self.mode, command=self.refresh_db_preview).pack(anchor="w", pady=(6, 0))
        ttk.Radiobutton(mode_box, text="Серверний сценарій", value="server", variable=self.mode, command=self.refresh_db_preview).pack(anchor="w")

        db_box = ttk.Frame(settings)
        db_box.grid(row=0, column=1, sticky="ew")
        db_box.columnconfigure(1, weight=1)
        self._add_entry(db_box, "Основна БД", self.main_db, 0)
        self._add_entry(db_box, "Legacy БД", self.legacy_db, 1)
        self._add_entry(db_box, "Шлях на сервері", self.server_path, 2)

        server_box = ttk.LabelFrame(settings, text="Дані входу до сервера", style="Card.TLabelframe")
        server_box.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        server_box.columnconfigure(1, weight=1)
        self._add_entry(server_box, "Host", self.server_host, 0)
        self._add_entry(server_box, "Port", self.server_port, 1)
        self._add_entry(server_box, "User", self.server_user, 2)
        self._add_entry(server_box, "SSH key", self.ssh_key_path, 3)
        self._add_entry(server_box, "SSH password", self.server_password, 4, show="*")
        self._add_entry(server_box, "Пароль адміна (sudo)", self.sudo_password, 5, show="*")
        ttk.Label(
            server_box,
            text="Пароль не зберігаємо в налаштуваннях. Якщо ключа немає, введи пароль вручну для перевірки.",
            style="Hint.TLabel",
        ).grid(row=6, column=0, columnspan=2, sticky="w", pady=(4, 0))

        options = ttk.LabelFrame(body, text="Галочки", style="Card.TLabelframe")
        options.grid(row=1, column=0, sticky="nsew", padx=(0, 10), pady=(16, 0))
        options['padding'] = 18
        options.columnconfigure(0, weight=1)
        ttk.Checkbutton(options, text="Зробити backup перед оновленням", variable=self.backup, command=self.refresh_db_preview).pack(anchor="w")
        ttk.Checkbutton(options, text="Запустити безпечне оновлення", variable=self.run_safe_update, command=self.refresh_db_preview).pack(anchor="w", pady=(4, 0))
        ttk.Checkbutton(options, text="Перезапустити сервіси після оновлення", variable=self.restart_services, command=self.refresh_db_preview).pack(anchor="w", pady=(4, 0))

        action_box = ttk.LabelFrame(body, text="Дії", style="Card.TLabelframe")
        action_box.grid(row=1, column=1, sticky="nsew", pady=(16, 0))
        action_box['padding'] = 18
        action_box.columnconfigure(0, weight=1)
        ttk.Button(action_box, text="Оновити перегляд", style="Primary.TButton", command=self.refresh_db_preview).pack(fill="x")
        ttk.Button(action_box, text="Скопіювати команди", command=self.copy_db_preview).pack(fill="x", pady=(8, 0))
        self._register_action_button("db-local-update", ttk.Button(action_box, text="Запустити локально", command=self.run_local_update)).pack(fill="x", pady=(8, 0))
        self._register_action_button("server-check", ttk.Button(action_box, text="Перевірити доступ до сервера", command=self.check_server_access)).pack(fill="x", pady=(8, 0))
        ttk.Button(action_box, text="Зберегти налаштування", command=self.save_settings).pack(fill="x", pady=(8, 0))
        ttk.Button(action_box, text="Скинути налаштування", command=self.reset_settings).pack(fill="x", pady=(8, 0))

        preview_box = ttk.LabelFrame(body, text="Попередній перегляд", style="Card.TLabelframe")
        preview_box.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=(16, 0))
        body.rowconfigure(2, weight=1)

        self.db_preview = tk.Text(preview_box, wrap="word", height=16, bg="#fbfaf7", fg="#1f2a29", relief="flat", borderwidth=0, padx=12, pady=12)
        self.db_preview.pack(fill="both", expand=True)

    def _build_git_tab(self) -> None:
        body, canvas = self._build_scrollable_tab(self.git_tab)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(1, weight=1)

        info = ttk.LabelFrame(body, text="Статус репозиторію", style="Card.TLabelframe")
        info.grid(row=0, column=0, columnspan=2, sticky="ew")
        info.columnconfigure(0, weight=1)

        repo_text = PROJECT_ROOT.as_posix()
        ttk.Label(info, text=f": {repo_text}", style="Hint.TLabel").pack(anchor="w")
        ttk.Label(info, text="Локальний коміт включає вибрані файли або вже підготовлені зміни. Кнопка “Підготувати всі” додає всі змінені файли.", style="Hint.TLabel").pack(anchor="w", pady=(4, 0))

        left = ttk.LabelFrame(body, text="Коміт", style="Card.TLabelframe")
        left.grid(row=1, column=0, sticky="nsew", padx=(0, 10), pady=(16, 0))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(6, weight=1)

        self._add_entry(left, "Повідомлення", self.commit_message, 0)
        ttk.Button(left, text="Оновити статус", command=self.refresh_git_status).grid(row=1, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(left, text="Показати файли", command=self.refresh_git_status).grid(row=2, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(left, text="Підготувати вибрані", command=self.stage_selected_changes).grid(row=3, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(left, text="Підготувати всі", command=self.stage_all_changes).grid(row=4, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(left, text="Коміт + Push", style="Primary.TButton", command=self.commit_and_push_selected_changes).grid(row=5, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(left, text="Зробити локальний коміт", command=self.commit_selected_changes).grid(row=6, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(left, text="Push до GitHub", command=self.push_current_branch).grid(row=7, column=0, sticky="ew", pady=(8, 0))

        files_box = ttk.LabelFrame(left, text="Змінені файли", style="Card.TLabelframe")
        files_box.grid(row=8, column=0, sticky="nsew", pady=(12, 0))
        files_box.columnconfigure(0, weight=1)
        files_box.rowconfigure(0, weight=1)

        files_frame = ttk.Frame(files_box)
        files_frame.grid(row=0, column=0, sticky="nsew")
        files_frame.columnconfigure(0, weight=1)
        files_frame.rowconfigure(0, weight=1)

        self.git_files = tk.Listbox(
            files_frame,
            selectmode="extended",
            bg="#fbfaf7",
            fg="#1f2a29",
            relief="flat",
            borderwidth=0,
            activestyle="dotbox",
        )
        self.git_files.grid(row=0, column=0, sticky="nsew")

        files_scroll = ttk.Scrollbar(files_frame, orient="vertical", command=self.git_files.yview)
        files_scroll.grid(row=0, column=1, sticky="ns")
        self.git_files.configure(yscrollcommand=files_scroll.set)

        file_buttons = ttk.Frame(files_box)
        file_buttons.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(file_buttons, text="Вибрати всі", command=self.select_all_git_files).pack(side="left")
        ttk.Button(file_buttons, text="Очистити вибір", command=self.clear_git_file_selection).pack(side="left", padx=(8, 0))

        self.git_config_label = ttk.Label(left, text="", style="Hint.TLabel", justify="left")
        self.git_config_label.grid(row=9, column=0, sticky="ew", pady=(12, 0))

        right = ttk.LabelFrame(body, text="Git-статус", style="Card.TLabelframe")
        right.grid(row=1, column=1, sticky="nsew", pady=(16, 0))
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)

        self.git_status = tk.Text(right, wrap="none", height=16, bg="#fbfaf7", fg="#1f2a29", relief="flat", borderwidth=0, padx=12, pady=12)
        self.git_status.grid(row=0, column=0, sticky="nsew")
        self._git_tab_canvas = canvas

    def _build_history_tab(self) -> None:
        body, canvas = self._build_scrollable_tab(self.history_tab)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(1, weight=1)

        header = ttk.LabelFrame(body, text="Журнал змін", style="Card.TLabelframe")
        header.grid(row=0, column=0, columnspan=2, sticky="ew")
        header.columnconfigure(0, weight=1)

        ttk.Label(
            header,
            text="Тут зберігається історія дій у програмі: запуски, Git-операції, зміни налаштувань і служб.",
            style="Hint.TLabel",
        ).pack(anchor="w")

        left = ttk.LabelFrame(body, text="Останні події", style="Card.TLabelframe")
        left.grid(row=1, column=0, sticky="nsew", padx=(0, 10), pady=(16, 0))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(0, weight=1)

        controls = ttk.Frame(left)
        controls.pack(fill="x")
        ttk.Button(controls, text="Оновити історію", command=self.refresh_history).pack(side="left")
        ttk.Button(controls, text="Відкрити файл", command=self.open_history_file).pack(side="left", padx=(8, 0))
        ttk.Button(controls, text="Очистити список", command=self.clear_history_view).pack(side="left", padx=(8, 0))
        ttk.Button(controls, text="Експорт CSV", command=self.export_history_csv).pack(side="left", padx=(8, 0))
        ttk.Button(controls, text="Звіт за день", command=self.generate_daily_report).pack(side="left", padx=(8, 0))

        search_row = ttk.Frame(left)
        search_row.pack(fill="x", pady=(10, 0))
        ttk.Label(search_row, text="Пошук:", style="Hint.TLabel").pack(side="left")
        search_entry = ttk.Entry(search_row, textvariable=self.history_search)
        search_entry.pack(side="left", fill="x", expand=True, padx=(8, 0))
        search_entry.bind("<KeyRelease>", lambda _event: self.refresh_history())
        ttk.Button(search_row, text="Очистити", command=self.clear_history_search).pack(side="left", padx=(8, 0))

        filter_row = ttk.Frame(left)
        filter_row.pack(fill="x", pady=(10, 0))
        ttk.Label(filter_row, text="Фільтр:", style="Hint.TLabel").pack(side="left")
        filter_box = ttk.Combobox(
            filter_row,
            textvariable=self.history_filter,
            values=["Усі", "Git", "Процеси", "БД", "Налаштування", "Скрипти", "Інше"],
            state="readonly",
            width=18,
        )
        filter_box.pack(side="left", padx=(8, 0))
        filter_box.bind("<<ComboboxSelected>>", lambda _event: self.refresh_history())

        report_row = ttk.Frame(left)
        report_row.pack(fill="x", pady=(10, 0))
        ttk.Label(report_row, text="Дата звіту:", style="Hint.TLabel").pack(side="left")
        ttk.Entry(report_row, textvariable=self.history_report_date, width=14).pack(side="left", padx=(8, 0))
        ttk.Button(report_row, text="Оновити звіт", command=self.generate_daily_report).pack(side="left", padx=(8, 0))

        list_frame = ttk.Frame(left)
        list_frame.pack(fill="both", expand=True, pady=(10, 0))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        self.history_list = tk.Listbox(
            list_frame,
            selectmode="single",
            bg="#fbfaf7",
            fg="#1f2a29",
            relief="flat",
            borderwidth=0,
        )
        self.history_list.grid(row=0, column=0, sticky="nsew")
        self.history_list.bind("<<ListboxSelect>>", lambda _event: self.show_selected_history_item())

        history_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.history_list.yview)
        history_scroll.grid(row=0, column=1, sticky="ns")
        self.history_list.configure(yscrollcommand=history_scroll.set)

        right = ttk.LabelFrame(body, text="Деталі події", style="Card.TLabelframe")
        right.grid(row=1, column=1, sticky="nsew", pady=(16, 0))
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)

        self.history_detail = tk.Text(
            right,
            wrap="word",
            height=16,
            bg="#fbfaf7",
            fg="#1f2a29",
            relief="flat",
            borderwidth=0,
            padx=12,
            pady=12,
        )
        self.history_detail.grid(row=0, column=0, sticky="nsew")
        self._history_tab_canvas = canvas

    def _build_map_tab(self) -> None:
        body, canvas = self._build_scrollable_tab(self.map_tab)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(1, weight=1)

        header = ttk.LabelFrame(body, text="Карта продукту", style="Card.TLabelframe")
        header.grid(row=0, column=0, columnspan=2, sticky="ew")
        header.columnconfigure(0, weight=1)

        ttk.Label(
            header,
            text="Тут видно, з чого складається продукт, за що відповідає кожна частина і що зараз працює.",
            style="Hint.TLabel",
        ).pack(anchor="w")

        search_row = ttk.Frame(header)
        search_row.pack(fill="x", pady=(10, 0))
        ttk.Label(search_row, text="Пошук", style="Hint.TLabel").pack(side="left")
        search_entry = ttk.Entry(search_row, textvariable=self.map_search)
        search_entry.pack(side="left", fill="x", expand=True, padx=(8, 8))
        search_entry.bind("<KeyRelease>", lambda _event: self.refresh_product_map())
        ttk.Button(search_row, text="Очистити", command=self.clear_map_search).pack(side="left")

        controls = ttk.Frame(header)
        controls.pack(fill="x", pady=(10, 0))
        ttk.Button(controls, text="Оновити карту", command=self.refresh_product_map).pack(side="left")
        self._register_action_button("map-start-component", ttk.Button(controls, text="Запустити компонент", command=self.start_selected_component)).pack(side="left", padx=(8, 0))
        ttk.Button(controls, text="Зупинити компонент", command=self.stop_selected_component).pack(side="left", padx=(8, 0))
        ttk.Button(controls, text="Відкрити ресурс", command=self.open_selected_component_resource).pack(side="left", padx=(8, 0))
        ttk.Button(controls, text="Відкрити файли", command=self.open_selected_component_files).pack(side="left", padx=(8, 0))
        ttk.Button(controls, text="Експорт карти", command=self.export_product_map).pack(side="left", padx=(8, 0))

        left = ttk.LabelFrame(body, text="Склад продукту", style="Card.TLabelframe")
        left.grid(row=1, column=0, sticky="nsew", padx=(0, 10), pady=(16, 0))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(0, weight=1)

        self.map_tree = ttk.Treeview(
            left,
            columns=("status", "control", "summary"),
            show="tree headings",
            selectmode="browse",
            height=16,
        )
        self.map_tree.heading("#0", text="Компонент")
        self.map_tree.heading("status", text="Стан")
        self.map_tree.heading("control", text="Керування")
        self.map_tree.heading("summary", text="Призначення")
        self.map_tree.column("#0", width=200, anchor="w")
        self.map_tree.column("status", width=120, anchor="w")
        self.map_tree.column("control", width=120, anchor="w")
        self.map_tree.column("summary", width=260, anchor="w")
        self.map_tree.grid(row=0, column=0, sticky="nsew")
        self.map_tree.bind("<<TreeviewSelect>>", lambda _event: self.show_selected_map_component())

        map_scroll = ttk.Scrollbar(left, orient="vertical", command=self.map_tree.yview)
        map_scroll.grid(row=0, column=1, sticky="ns")
        self.map_tree.configure(yscrollcommand=map_scroll.set)

        right = ttk.LabelFrame(body, text="Деталі компонента", style="Card.TLabelframe")
        right.grid(row=1, column=1, sticky="nsew", pady=(16, 0))
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        top = ttk.Frame(right)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(0, weight=1)

        self.map_title = ttk.Label(top, text="Оберіть компонент у карті", style="Title.TLabel")
        self.map_title.grid(row=0, column=0, sticky="w")
        self.map_status = ttk.Label(top, text="", style="Hint.TLabel")
        self.map_status.grid(row=1, column=0, sticky="w", pady=(4, 0))

        detail_box = ttk.Frame(right)
        detail_box.grid(row=1, column=0, sticky="nsew", pady=(12, 0))
        detail_box.columnconfigure(0, weight=1)
        detail_box.rowconfigure(0, weight=1)

        self.map_detail = tk.Text(
            detail_box,
            wrap="word",
            height=10,
            bg="#fbfaf7",
            fg="#1f2a29",
            relief="flat",
            borderwidth=0,
            padx=12,
            pady=12,
        )
        self.map_detail.grid(row=0, column=0, sticky="nsew")

        files_box = ttk.LabelFrame(right, text="Пов’язані файли", style="Card.TLabelframe")
        files_box.grid(row=2, column=0, sticky="nsew", pady=(12, 0))
        files_box.columnconfigure(0, weight=1)
        files_box.rowconfigure(0, weight=1)

        files_frame = ttk.Frame(files_box)
        files_frame.grid(row=0, column=0, sticky="nsew")
        files_frame.columnconfigure(0, weight=1)
        files_frame.rowconfigure(0, weight=1)

        self.map_files = tk.Listbox(
            files_frame,
            selectmode="browse",
            bg="#fbfaf7",
            fg="#1f2a29",
            relief="flat",
            borderwidth=0,
        )
        self.map_files.grid(row=0, column=0, sticky="nsew")
        map_files_scroll = ttk.Scrollbar(files_frame, orient="vertical", command=self.map_files.yview)
        map_files_scroll.grid(row=0, column=1, sticky="ns")
        self.map_files.configure(yscrollcommand=map_files_scroll.set)

        file_controls = ttk.Frame(files_box)
        file_controls.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(file_controls, text="Відкрити файл", command=self.open_selected_map_file).pack(side="left")
        ttk.Button(file_controls, text="Відкрити папку", command=self.open_selected_map_folder).pack(side="left", padx=(8, 0))
        ttk.Button(file_controls, text="Копіювати опис", command=self.copy_selected_component_summary).pack(side="left", padx=(8, 0))

        self.clear_map_detail()
        self._map_tab_canvas = canvas

    def _build_product_tab(self) -> None:
        container = ttk.Frame(self.product_tab, style="Root.TFrame")
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)

        canvas = tk.Canvas(container, highlightthickness=0, bd=0, bg=self.cget("background"))
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        canvas.configure(yscrollcommand=scrollbar.set)

        body = ttk.Frame(canvas, style="Root.TFrame", padding=4)
        body_window = canvas.create_window((0, 0), window=body, anchor="nw")

        def sync_scrollregion(_event: tk.Event | None = None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def sync_body_width(event: tk.Event) -> None:
            canvas.itemconfigure(body_window, width=event.width)

        body.bind("<Configure>", sync_scrollregion)
        canvas.bind("<Configure>", sync_body_width)

        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(1, weight=1)

        quick = ttk.LabelFrame(body, text="Швидкі дії", style="Card.TLabelframe")
        quick.grid(row=0, column=0, columnspan=2, sticky="ew")
        quick.columnconfigure(0, weight=1)

        quick_head = ttk.Frame(quick)
        quick_head.pack(fill="x")
        ttk.Label(
            quick_head,
            text="Тут зібрані найчастіші дії для продукту: локальні сервіси, оновлення БД, утиліти та відкриття файлів.",
            style="Hint.TLabel",
        ).pack(side="left", fill="x", expand=True)
        quick_controls = ttk.Frame(quick_head)
        quick_controls.pack(side="right")
        ttk.Button(quick_controls, text="Оновити все", command=self.refresh_all_views).pack(side="left")
        ttk.Button(quick_controls, text="Оновити стан", command=self.refresh_product_status).pack(side="left")
        ttk.Checkbutton(quick_controls, text="Автооновлення списку процесів", variable=self.auto_refresh).pack(side="left", padx=(8, 0))
        ttk.Label(quick, textvariable=self.launch_status_var, style="Hint.TLabel").pack(anchor="w", pady=(6, 0))

        launch_row = ttk.Frame(quick)
        launch_row.pack(fill="x", pady=(8, 0))
        for index, (key, label) in enumerate([("api", "API"), ("bot", "Bot"), ("frontend-app", "App"), ("frontend-admin", "Admin")]):
            cell = ttk.Frame(launch_row, style="Root.TFrame")
            cell.grid(row=0, column=index, sticky="ew", padx=(0 if index == 0 else 8, 0))
            launch_row.columnconfigure(index, weight=1)
            header = ttk.Frame(cell, style="Root.TFrame")
            header.pack(anchor="w", fill="x")
            marker = ttk.Label(header, text="●", style="Hint.TLabel")
            marker.pack(side="left")
            ttk.Label(header, text=f" {label}", style="Hint.TLabel").pack(side="left")
            value = tk.StringVar(value="не запускалось")
            self.component_launch_vars[key] = value
            launch_label = ttk.Label(cell, textvariable=value, style="LaunchUnknown.TLabel")
            launch_label.pack(anchor="w", fill="x")
            self.component_launch_labels[key] = launch_label
            self.component_launch_markers[key] = marker

        status_row = ttk.Frame(quick)
        status_row.pack(fill="x", pady=(10, 0))
        for index, (key, label) in enumerate([("api", "API"), ("app", "App"), ("admin", "Admin"), ("bot", "Bot")]):
            cell = ttk.Frame(status_row, style="Root.TFrame")
            cell.grid(row=0, column=index, sticky="ew", padx=(0 if index == 0 else 10, 0))
            status_row.columnconfigure(index, weight=1)
            ttk.Label(cell, text=label, style="Hint.TLabel").pack(anchor="w")
            value = tk.StringVar(value="невідомо")
            self.service_status_vars[key] = value
            status_label = ttk.Label(cell, textvariable=value, style="ServiceUnknown.TLabel")
            status_label.pack(anchor="w", fill="x")
            self.service_status_labels[key] = status_label
            self._apply_service_status_style(key, value.get())

        legend = ttk.Frame(quick, style="Root.TFrame")
        legend.pack(fill="x", pady=(8, 0))
        for index, (color, text) in enumerate([
            ("#1f7a1f", "зелений = працює"),
            ("#a26b00", "жовтий = запускається"),
            ("#a61b1b", "червоний = проблема"),
        ]):
            item = ttk.Frame(legend, style="Root.TFrame")
            item.grid(row=0, column=index, sticky="w", padx=(0 if index == 0 else 18, 0))
            ttk.Label(item, text="●", foreground=color, style="Hint.TLabel").pack(side="left")
            ttk.Label(item, text=f" {text}", style="Hint.TLabel").pack(side="left")
        ttk.Label(
            quick,
            text="Пояснення: якщо компонент уже запущений, але ще не відповідає, він буде жовтим. Зелений означає, що все готово.",
            style="Hint.TLabel",
        ).pack(anchor="w", pady=(6, 0))

        left = ttk.LabelFrame(body, text="Локальні сервіси", style="Card.TLabelframe")
        left.grid(row=1, column=0, sticky="nsew", padx=(0, 10), pady=(16, 0))
        left.columnconfigure(0, weight=1)

        self._register_action_button("api", ttk.Button(left, text="Запустити API", command=self.start_local_api)).pack(fill="x")
        self._register_action_button("bot", ttk.Button(left, text="Запустити бота", command=self.start_local_bot)).pack(fill="x", pady=(8, 0))
        self._register_action_button("frontend-app", ttk.Button(left, text="Запустити app", command=self.start_app_frontend)).pack(fill="x", pady=(8, 0))
        self._register_action_button("frontend-admin", ttk.Button(left, text="Запустити admin", command=self.start_admin_frontend)).pack(fill="x", pady=(8, 0))
        self._register_action_button("start-full-stack", ttk.Button(left, text="Запустити весь продукт", command=self.start_full_local_stack)).pack(fill="x", pady=(8, 0))
        ttk.Button(left, text="Відкрити всі сторінки", command=self.open_all_local_pages).pack(fill="x", pady=(8, 0))
        ttk.Button(left, text="Оновити список процесів", command=self.refresh_managed_processes).pack(fill="x", pady=(8, 0))
        ttk.Button(left, text="Перезапустити вибраний процес", command=self.restart_selected_process).pack(fill="x", pady=(8, 0))
        ttk.Button(left, text="Зупинити вибраний процес", command=self.stop_selected_process).pack(fill="x", pady=(8, 0))
        ttk.Button(left, text="Зупинити всі процеси", command=self.stop_all_processes).pack(fill="x", pady=(8, 0))

        process_box = ttk.LabelFrame(left, text="Запущені процеси", style="Card.TLabelframe")
        process_box.pack(fill="both", expand=True, pady=(12, 0))
        process_box.columnconfigure(0, weight=1)
        process_box.rowconfigure(0, weight=1)

        self.process_list = tk.Listbox(
            process_box,
            selectmode="single",
            bg="#fbfaf7",
            fg="#1f2a29",
            relief="flat",
            borderwidth=0,
        )
        self.process_list.pack(fill="both", expand=True)
        self.process_list_colors_enabled = True

        right = ttk.LabelFrame(body, text="Скрипти продукту", style="Card.TLabelframe")
        right.grid(row=1, column=1, sticky="nsew", pady=(16, 0))
        right.columnconfigure(0, weight=1)

        open_box = ttk.LabelFrame(right, text="Відкрити", style="Card.TLabelframe")
        open_box.pack(fill="x")
        ttk.Button(open_box, text="Папку проєкту", command=self.open_project_folder).pack(fill="x")
        ttk.Button(open_box, text="Основну БД", command=self.open_main_database).pack(fill="x", pady=(8, 0))
        ttk.Button(open_box, text="Legacy БД", command=self.open_legacy_database).pack(fill="x", pady=(8, 0))
        ttk.Button(open_box, text="README", command=self.open_readme).pack(fill="x", pady=(8, 0))
        ttk.Button(open_box, text="Інструкцію по оновленню", command=self.open_workflow_doc).pack(fill="x", pady=(8, 0))
        ttk.Button(open_box, text="Проста інструкція", command=self.open_simple_guide).pack(fill="x", pady=(8, 0))
        ttk.Button(open_box, text="API /docs", command=self.open_api_docs).pack(fill="x", pady=(8, 0))
        ttk.Button(open_box, text="Frontend app", command=self.open_frontend_app).pack(fill="x", pady=(8, 0))
        ttk.Button(open_box, text="Frontend admin", command=self.open_frontend_admin).pack(fill="x", pady=(8, 0))

        diagnostics_box = ttk.LabelFrame(right, text="Діагностика", style="Card.TLabelframe")
        diagnostics_box.pack(fill="x", pady=(12, 0))
        ttk.Button(diagnostics_box, text="Лог програми", command=lambda: self._open_path(APP_LOG_PATH)).pack(fill="x")
        ttk.Button(diagnostics_box, text="Лог запуску", command=self.open_launch_log).pack(fill="x")
        ttk.Button(diagnostics_box, text="Лог помилок", command=self.open_launch_error_log).pack(fill="x", pady=(8, 0))

        self._register_action_button("db-init", ttk.Button(right, text="Ініціалізувати БД", command=self.run_init_database)).pack(fill="x")
        self._register_action_button("db-safe-update", ttk.Button(right, text="Безпечне оновлення БД", command=self.run_safe_update_db)).pack(fill="x", pady=(8, 0))
        self._register_action_button("db-repair-catalog", ttk.Button(right, text="Repair catalog data", command=self.run_repair_catalog)).pack(fill="x", pady=(8, 0))
        self._register_action_button("db-repair-catalog-images", ttk.Button(right, text="Довантажити картинки каталогу", command=self.run_repair_catalog_images)).pack(fill="x", pady=(8, 0))
        self._register_action_button("db-seed-confirmat", ttk.Button(right, text="Seed confirmat holes", command=self.run_seed_confirmat)).pack(fill="x", pady=(8, 0))
        self._register_action_button("db-upgrade-fittings", ttk.Button(right, text="Upgrade fittings schema", command=self.run_upgrade_fittings_schema)).pack(fill="x", pady=(8, 0))

        frontend_box = ttk.LabelFrame(right, text="Фронтенд", style="Card.TLabelframe")
        frontend_box.pack(fill="x", pady=(12, 0))
        self._register_action_button("frontend-app", ttk.Button(frontend_box, text="Запустити app", command=self.start_app_frontend)).pack(fill="x")
        self._register_action_button("frontend-admin", ttk.Button(frontend_box, text="Запустити admin", command=self.start_admin_frontend)).pack(fill="x", pady=(8, 0))

        maintenance_box = ttk.LabelFrame(right, text="Технічні роботи", style="Card.TLabelframe")
        maintenance_box.pack(fill="x", pady=(12, 0))
        self._add_entry(maintenance_box, "Повідомлення", self.maintenance_message, 0)
        self._add_entry(maintenance_box, "Орієнт. час", self.maintenance_eta, 1)
        ttk.Label(
            maintenance_box,
            textvariable=self.maintenance_preview_status,
            style="Hint.TLabel",
            justify="left",
            wraplength=420,
        ).grid(row=2, column=0, sticky="w", pady=(6, 0))
        ttk.Label(
            maintenance_box,
            textvariable=self.maintenance_server_control_status,
            style="Hint.TLabel",
            justify="left",
            wraplength=420,
        ).grid(row=3, column=0, sticky="w", pady=(6, 0))
        maintenance_actions = ttk.Frame(maintenance_box)
        maintenance_actions.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        maintenance_actions.columnconfigure(0, weight=1)
        maintenance_actions.columnconfigure(1, weight=1)
        maintenance_actions.columnconfigure(2, weight=1)
        maintenance_actions.columnconfigure(3, weight=1)
        maintenance_actions.columnconfigure(4, weight=1)
        ttk.Button(maintenance_actions, text="Переглянути заглушку", command=self.preview_maintenance_page).grid(row=0, column=0, sticky="ew")
        ttk.Button(maintenance_actions, text="Оновити статус", command=self.refresh_maintenance_server_control_status).grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Button(maintenance_actions, text="Увімкнути техроботи", command=self.run_maintenance_server_enable).grid(row=0, column=2, sticky="ew", padx=8)
        ttk.Button(maintenance_actions, text="Вимкнути техроботи", command=self.run_maintenance_server_disable).grid(row=0, column=3, sticky="ew")
        ttk.Button(maintenance_actions, text="Деталі", command=self.open_maintenance_server_control_details).grid(row=0, column=4, sticky="ew", padx=(8, 0))
        owner_access_actions = ttk.Frame(maintenance_box)
        owner_access_actions.grid(row=5, column=0, sticky="ew", pady=(10, 0))
        owner_access_actions.columnconfigure(0, weight=1)
        owner_access_actions.columnconfigure(1, weight=1)
        ttk.Button(owner_access_actions, text="Відкрити сайт як власник", command=self.open_maintenance_owner_login).grid(row=0, column=0, sticky="ew")
        ttk.Button(owner_access_actions, text="Завершити власницький доступ", command=self.open_maintenance_owner_logout).grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Label(
            maintenance_box,
            text="Власницький доступ діє лише у браузері, в якому виконано вхід.",
            style="Hint.TLabel",
            justify="left",
            wraplength=420,
        ).grid(row=6, column=0, sticky="w", pady=(8, 0))
        ttk.Label(
            maintenance_box,
            textvariable=self.maintenance_server_audit_status,
            style="Hint.TLabel",
            justify="left",
            wraplength=420,
        ).grid(row=7, column=0, sticky="w", pady=(8, 0))
        ttk.Label(
            maintenance_box,
            textvariable=self.maintenance_server_audit_summary,
            style="Hint.TLabel",
            justify="left",
            wraplength=420,
        ).grid(row=8, column=0, sticky="w", pady=(4, 0))
        maintenance_audit_actions = ttk.Frame(maintenance_box)
        maintenance_audit_actions.grid(row=9, column=0, sticky="ew", pady=(10, 0))
        maintenance_audit_actions.columnconfigure(0, weight=1)
        maintenance_audit_actions.columnconfigure(1, weight=1)
        maintenance_audit_actions.columnconfigure(2, weight=1)
        ttk.Button(maintenance_audit_actions, text="Перевірити сервер", command=self.run_maintenance_server_audit).grid(row=0, column=0, sticky="ew")
        ttk.Button(maintenance_audit_actions, text="Перевірити з sudo", command=self.run_maintenance_server_audit_privileged).grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Button(maintenance_audit_actions, text="Показати звіт", command=self.open_maintenance_server_audit_report).grid(row=0, column=2, sticky="ew")
        ttk.Label(
            maintenance_box,
            text="Буде доступно після налаштування сервера.",
            style="Hint.TLabel",
            justify="left",
            wraplength=420,
        ).grid(row=10, column=0, sticky="w", pady=(8, 0))

        params = ttk.LabelFrame(right, text="Параметри", style="Card.TLabelframe")
        params.pack(fill="x", pady=(12, 0))
        self._add_entry(params, "Місто", self.catalog_city, 0)
        ttk.Checkbutton(params, text="Прогрівати зображення", variable=self.catalog_warm_images).grid(row=1, column=0, sticky="w", pady=(4, 0))
        ttk.Checkbutton(
            params,
            text="Дозволити локальну реєстрацію",
            variable=self.allow_local_registration,
        ).grid(row=2, column=0, sticky="w", pady=(4, 0))
        ttk.Label(
            params,
            text="Після зміни цього прапорця локальний API потрібно перезапустити.",
            style="Hint.TLabel",
            justify="left",
        ).grid(row=3, column=0, sticky="w", pady=(4, 0))
        ttk.Checkbutton(
            params,
            text="Локальний тест підтвердження телефону",
            variable=self.allow_local_registration_test_mode,
        ).grid(row=4, column=0, sticky="w", pady=(8, 0))
        ttk.Label(
            params,
            text="Після зміни цього прапорця локальний API потрібно перезапустити.",
            style="Hint.TLabel",
            justify="left",
        ).grid(row=5, column=0, sticky="w", pady=(4, 0))

        log_box = ttk.LabelFrame(body, text="Журнал дій", style="Card.TLabelframe")
        log_box.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=(16, 0))
        body.rowconfigure(2, weight=1)
        log_box.columnconfigure(0, weight=1)
        log_box.rowconfigure(0, weight=1)

        self.product_log = tk.Text(
            log_box,
            wrap="word",
            height=10,
            bg="#fbfaf7",
            fg="#1f2a29",
            relief="flat",
            borderwidth=0,
            padx=12,
            pady=12,
        )
        self.product_log.pack(fill="both", expand=True)

    def _build_package_tab(self) -> None:
        body, canvas = self._build_scrollable_tab(self.package_tab)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(1, weight=1)

        header = ttk.LabelFrame(body, text="Версії оновлень", style="Card.TLabelframe")
        header.grid(row=0, column=0, columnspan=2, sticky="ew")
        header.columnconfigure(1, weight=1)
        header['padding'] = 18

        ttk.Label(
            header,
            text="Тут збирається пакет змін: номер версії, список файлів і кроки для сервера.",
            style="Hint.TLabel",
        ).grid(row=0, column=0, columnspan=2, sticky="w")
        self._add_entry(header, "Версія пакета", self.update_package_version, 1)
        self._add_entry(header, "Шлях файлу", self.update_package_path, 2)
        self._add_entry(header, "Файлів у пакеті", self.update_package_files_summary, 3)

        source_box = ttk.LabelFrame(body, text="Звідки брати зміни", style="Card.TLabelframe")
        source_box.grid(row=1, column=0, sticky="nsew", padx=(0, 10), pady=(16, 0))
        source_box.columnconfigure(0, weight=1)
        source_box['padding'] = 18

        ttk.Radiobutton(
            source_box,
            text="Автоматично: змінені файли",
            value="changed",
            variable=self.update_package_source,
            command=self.refresh_update_package_preview,
        ).pack(anchor="w")
        ttk.Radiobutton(
            source_box,
            text="Вибрані файли у вкладці Git",
            value="selected",
            variable=self.update_package_source,
            command=self.refresh_update_package_preview,
        ).pack(anchor="w")
        ttk.Radiobutton(
            source_box,
            text="Усі змінені файли у Git",
            value="all",
            variable=self.update_package_source,
            command=self.refresh_update_package_preview,
        ).pack(anchor="w", pady=(4, 0))

        ttk.Button(source_box, text="Оновити перегляд", command=self.refresh_update_package_preview).pack(fill="x", pady=(12, 0))
        ttk.Button(source_box, text="Створити пакет версії", style="Primary.TButton", command=self.create_update_package).pack(fill="x", pady=(8, 0))
        self._register_action_button("server-update", ttk.Button(source_box, text="Оновити сервер", command=self.run_server_update)).pack(fill="x", pady=(8, 0))
        ttk.Button(source_box, text="Відкрити папку пакетів", command=self.open_update_packages_folder).pack(fill="x", pady=(8, 0))
        ttk.Button(source_box, text="Відкрити інструкцію", command=self.open_workflow_doc).pack(fill="x", pady=(8, 0))
        ttk.Button(source_box, text="Скопіювати план", command=self.copy_update_package_plan).pack(fill="x", pady=(8, 0))

        preview_box = ttk.LabelFrame(body, text="Поточний пакет", style="Card.TLabelframe")
        preview_box.grid(row=1, column=1, sticky="nsew", pady=(16, 0))
        preview_box.columnconfigure(0, weight=1)
        preview_box.rowconfigure(1, weight=1)
        preview_box['padding'] = 18

        status_bar = ttk.Frame(preview_box, style="Root.TFrame")
        status_bar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        status_bar.columnconfigure(0, weight=1)
        status_bar.columnconfigure(1, weight=1)
        status_bar.columnconfigure(2, weight=1)
        ttk.Label(status_bar, textvariable=self.update_package_snapshot_summary, style="Hint.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(status_bar, textvariable=self.update_package_new_summary, style="Hint.TLabel").grid(row=0, column=1, sticky="w")
        ttk.Label(status_bar, textvariable=self.update_package_ready_summary, style="Hint.TLabel").grid(row=0, column=2, sticky="w")

        self.update_package_preview = tk.Text(
            preview_box,
            wrap="word",
            height=20,
            bg="#fbfaf7",
            fg="#1f2a29",
            relief="flat",
            borderwidth=0,
            padx=12,
            pady=12,
        )
        self.update_package_preview.grid(row=1, column=0, sticky="nsew")
        self._package_tab_canvas = canvas

        self.refresh_update_package_preview()

    def _build_help_tab(self) -> None:
        body, canvas = self._build_scrollable_tab(self.help_tab)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(1, weight=1)

        header = ttk.LabelFrame(body, text="Швидкий старт", style="Card.TLabelframe")
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        header["padding"] = 18

        ttk.Label(
            header,
            text="Ця вкладка допомагає працювати без плутанини: спочатку локальна перевірка, потім пакет версії, далі Git і сервер.",
            style="Hint.TLabel",
            justify="left",
        ).grid(row=0, column=0, sticky="w")

        steps = ttk.Frame(header, style="Root.TFrame")
        steps.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        steps.columnconfigure(0, weight=1)
        step_texts = [
            "1. Змінив код або дані локально.",
            "2. Перейшов у вкладку Продукт або База і перевірив, що все відкривається без помилок.",
            "3. Перейшов у вкладку Версії і натиснув Оновити перегляд.",
            "4. Якщо все ок, натиснув Створити пакет версії.",
            "5. Далі зробив Git commit і push тільки для тих файлів, які справді змінились.",
            "6. На сервері застосував саме нову версію пакета або оновлення бази.",
        ]
        for idx, text in enumerate(step_texts):
            ttk.Label(steps, text=text, style="Hint.TLabel", justify="left").grid(row=idx, column=0, sticky="w", pady=(0, 4))

        actions = ttk.Frame(header, style="Root.TFrame")
        actions.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=1)
        actions.columnconfigure(2, weight=1)
        ttk.Button(actions, text="Відкрити довідку", command=self.open_help_guide).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ttk.Button(actions, text="Відкрити workflow", command=self.open_workflow_doc).grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Button(actions, text="Папка скрінів", command=lambda: self._open_path(PROJECT_ROOT / "docs" / "screenshots")).grid(row=0, column=2, sticky="ew", padx=(8, 0))

        details = ttk.LabelFrame(body, text="Що означають кроки", style="Card.TLabelframe")
        details.grid(row=1, column=0, sticky="nsew", pady=(16, 0))
        details.columnconfigure(0, weight=1)
        details["padding"] = 18

        guide_text = (
            "Локально:\n"
            "• Змінюєш код або дані.\n"
            "• Перевіряєш у програмі, чи немає помилок.\n"
            "• Дивишся вкладку Версії, щоб пакет включав тільки змінені файли.\n\n"
            "Git:\n"
            "• Commit робиш після того, як упевнився, що локально все працює.\n"
            "• До пакета версії потрапляє лише те, що змінилось.\n"
            "• Якщо файл не редагувався, він не повинен повторюватися у новому пакеті.\n\n"
            "База даних:\n"
            "• Якщо змінились лише дані, фіксуєш їх окремо і перевіряєш у БД.\n"
            "• Якщо змінились і код, і БД, краще розділити це на два зрозумілі кроки.\n"
        )
        guide = tk.Text(
            details,
            wrap="word",
            height=11,
            bg="#fbfaf7",
            fg="#1f2a29",
            relief="flat",
            borderwidth=0,
            padx=12,
            pady=12,
        )
        guide.grid(row=0, column=0, sticky="nsew")
        guide.insert("1.0", guide_text)
        guide.configure(state="disabled")

        images_box = ttk.LabelFrame(body, text="Скріншоти", style="Card.TLabelframe")
        images_box.grid(row=2, column=0, sticky="nsew", pady=(16, 0))
        images_box.columnconfigure(0, weight=1)
        images_box["padding"] = 18

        self._help_images: list[tk.PhotoImage] = []
        screenshots = [
            ("1. Версії та прогрес", PROJECT_ROOT / "docs" / "screenshots" / "help_versions_smooth_loading.png"),
            ("2. Пакет змін", PROJECT_ROOT / "docs" / "screenshots" / "help_versions_package_view.png"),
            ("3. Проблема з текстом", PROJECT_ROOT / "docs" / "screenshots" / "help_versions_text_issue.png"),
            ("4. Завершене завантаження", PROJECT_ROOT / "docs" / "screenshots" / "help_versions_progress.png"),
        ]
        for idx, (title, image_path) in enumerate(screenshots):
            row = ttk.Frame(images_box, style="Root.TFrame")
            row.grid(row=idx, column=0, sticky="ew", pady=(0, 16))
            row.columnconfigure(0, weight=1)
            ttk.Label(row, text=title, style="Hint.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))
            try:
                image = tk.PhotoImage(file=str(image_path))
                self._help_images.append(image)
                ttk.Label(row, image=image).grid(row=1, column=0, sticky="w")
            except tk.TclError:
                ttk.Label(row, text=f"Не вдалося завантажити {image_path.name}", style="Hint.TLabel").grid(row=1, column=0, sticky="w")

        self._help_tab_canvas = canvas

    def _add_entry(
        self,
        parent: ttk.Frame,
        label: str,
        variable: tk.StringVar,
        row_index: int,
        *,
        show: str | None = None,
    ) -> None:
        row = ttk.Frame(parent)
        row.grid(row=row_index, column=0, sticky="ew", pady=4)
        row.columnconfigure(1, weight=1)
        ttk.Label(row, text=label, width=16, style="Hint.TLabel").grid(row=0, column=0, sticky="w")
        entry_kwargs: dict[str, object] = {"textvariable": variable}
        if show is not None:
            entry_kwargs["show"] = show
        ttk.Entry(row, **entry_kwargs).grid(row=0, column=1, sticky="ew")

    def db_preview_text(self) -> str:
        main_db = self.main_db.get().strip()

        if self.mode.get() == "local":
            lines = [
                "Локальний сценарій",
                "",
                "Змінні середовища:",
                format_local_env(main_db),
            ]
            if self.run_safe_update.get():
                lines.extend(
                    [
                        "",
                        "Запуск:",
                        " ".join(build_local_command(main_db, self.backup.get())),
                    ]
                )
            return "\n".join(lines)

        legacy_db = self.legacy_db.get().strip()
        server_path = self.server_path.get().strip()
        server_host = self.server_host.get().strip()
        server_port = self.server_port.get().strip()
        server_user = self.server_user.get().strip()
        ssh_key_path = self.ssh_key_path.get().strip()
        server_password = self.server_password.get().strip()

        lines = [
            "Серверний сценарій",
            "",
            "Команди для сервера:",
            format_server_block(
                main_db,
                legacy_db,
                server_path,
                server_host,
                server_port,
                server_user,
                ssh_key_path,
                self.restart_services.get(),
            ),
        ]
        if server_password and not ssh_key_path:
            lines.extend(
                [
                    "",
                    "SSH auth: password",
                    "Пароль вводиться тільки для перевірки доступу і не зберігається.",
                ]
            )
        return "\n".join(lines)

    def refresh_db_preview(self) -> None:
        self.db_preview.delete("1.0", "end")
        self.db_preview.insert("1.0", self.db_preview_text())

    def copy_db_preview(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(self.db_preview_text())
        self.update()
        messagebox.showinfo("Скопійовано", "Текст команд скопійовано в буфер обміну.")

    def settings_data(self) -> dict[str, object]:
        return {
            "mode": self.mode.get(),
            "main_db": self.main_db.get(),
            "legacy_db": self.legacy_db.get(),
            "server_path": self.server_path.get(),
            "server_host": self.server_host.get(),
            "server_port": self.server_port.get(),
            "server_user": self.server_user.get(),
            "ssh_key_path": self.ssh_key_path.get(),
            "backup": self.backup.get(),
            "run_safe_update": self.run_safe_update.get(),
            "restart_services": self.restart_services.get(),
            "commit_message": self.commit_message.get(),
            "catalog_city": self.catalog_city.get(),
            "catalog_warm_images": self.catalog_warm_images.get(),
            "auto_refresh": self.auto_refresh.get(),
            "allow_local_registration": self.allow_local_registration.get(),
            "allow_local_registration_test_mode": self.allow_local_registration_test_mode.get(),
            "map_search": self.map_search.get(),
            "history_search": self.history_search.get(),
            "history_filter": self.history_filter.get(),
            "history_report_date": self.history_report_date.get(),
        }

    def load_settings(self) -> None:
        if not SETTINGS_PATH.exists():
            self._saved_settings_snapshot = self.settings_data()
            return
        try:
            data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self._saved_settings_snapshot = self.settings_data()
            return

        if isinstance(data, dict):
            self.mode.set(str(data.get("mode", self.mode.get())))
            self.main_db.set(str(data.get("main_db", self.main_db.get())))
            self.legacy_db.set(str(data.get("legacy_db", self.legacy_db.get())))
            self.server_path.set(str(data.get("server_path", self.server_path.get())))
            self.server_host.set(str(data.get("server_host", self.server_host.get())))
            self.server_port.set(str(data.get("server_port", self.server_port.get())))
            self.server_user.set(str(data.get("server_user", self.server_user.get())))
            self.ssh_key_path.set(str(data.get("ssh_key_path", self.ssh_key_path.get())))
            self.server_password.set("")
            self.sudo_password.set("")
            self.backup.set(as_bool(data.get("backup"), self.backup.get()))
            self.run_safe_update.set(as_bool(data.get("run_safe_update"), self.run_safe_update.get()))
            self.restart_services.set(as_bool(data.get("restart_services"), self.restart_services.get()))
            self.commit_message.set(str(data.get("commit_message", self.commit_message.get())))
            self.catalog_city.set(str(data.get("catalog_city", self.catalog_city.get())))
            self.catalog_warm_images.set(as_bool(data.get("catalog_warm_images"), self.catalog_warm_images.get()))
            self.auto_refresh.set(as_bool(data.get("auto_refresh"), self.auto_refresh.get()))
            self.allow_local_registration.set(as_bool(data.get("allow_local_registration"), self.allow_local_registration.get()))
            self.allow_local_registration_test_mode.set(
                as_bool(data.get("allow_local_registration_test_mode"), self.allow_local_registration_test_mode.get())
            )
            self.map_search.set(str(data.get("map_search", self.map_search.get())))
            self.history_search.set(str(data.get("history_search", self.history_search.get())))
            self.history_filter.set(str(data.get("history_filter", self.history_filter.get())))
            self.history_report_date.set(str(data.get("history_report_date", self.history_report_date.get())))
        self._saved_settings_snapshot = self.settings_data()

    def save_settings(self, notify: bool = True) -> None:
        before = dict(self._saved_settings_snapshot)
        after = self.settings_data()
        try:
            SETTINGS_PATH.write_text(json.dumps(after, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError as exc:
            if notify:
                messagebox.showerror("Не вдалося зберегти", str(exc))
            return
        changed = {
            key: {"before": before.get(key), "after": after.get(key)}
            for key in after
            if before.get(key) != after.get(key)
        }
        self.record_history(
            "settings.save",
            details=f"Збережено налаштування в {SETTINGS_PATH.name}",
            extra={"changed": changed},
        )
        self._saved_settings_snapshot = after
        self._append_product_log(f"[Налаштування] Збережено в {SETTINGS_PATH.name}")
        if notify:
            messagebox.showinfo("Збережено", "Налаштування збережено.")

    def reset_settings(self) -> None:
        self.mode.set("local")
        self.main_db.set(default_main_db())
        self.legacy_db.set(default_legacy_db())
        self.server_path.set("/opt/furniture-stage")
        self.server_host.set("")
        self.server_port.set("22")
        self.server_user.set("")
        self.ssh_key_path.set("")
        self.server_password.set("")
        self.sudo_password.set("")
        self.backup.set(True)
        self.run_safe_update.set(True)
        self.restart_services.set(True)
        self.commit_message.set("Оновлення проєкту")
        self.catalog_city.set("Київ")
        self.catalog_warm_images.set(True)
        self.auto_refresh.set(True)
        self.allow_local_registration.set(False)
        self.allow_local_registration_test_mode.set(False)
        self.map_search.set("")
        self.history_search.set("")
        self.history_filter.set("Усі")
        self.history_report_date.set(datetime.now().date().isoformat())
        self.refresh_db_preview()
        self.refresh_product_status()
        self.record_history("settings.reset", details="Повернуто стандартні налаштування")
        messagebox.showinfo("Скинуто", "Налаштування повернено до стандартних.")

    def on_close(self) -> None:
        self.save_settings(notify=False)
        self.destroy()

    def check_server_access(self) -> None:
        host = self.server_host.get().strip()
        port = self.server_port.get().strip() or "22"
        user = self.server_user.get().strip()
        key_path = self.ssh_key_path.get().strip()
        server_password = self.server_password.get().strip()

        if not host or not user:
            messagebox.showwarning("Не вистачає даних", "Заповни хоча б Host і User для перевірки доступу до сервера.")
            return

        if key_path:
            command = build_ssh_probe_command(host, port, user, key_path)
            if not command:
                messagebox.showwarning("Не вистачає даних", "Неможливо зібрати команду перевірки сервера.")
                return

            self._run_script_async("Перевірка доступу до сервера", command, button_key="server-check")
            return

        if not server_password:
            messagebox.showwarning(
                "Не вистачає даних",
                "Вкажи або SSH key, або SSH password для перевірки доступу.",
            )
            return

        self._begin_activity()

        def worker() -> None:
            success, output = _probe_server_with_paramiko(host, port, user, key_path, server_password)

            def finish() -> None:
                self._end_activity()
                if success:
                    messagebox.showinfo("Готово", "Перевірка доступу до сервера успішна.")
                    self._set_action_button_state("server-check", "success")
                else:
                    messagebox.showerror("Помилка", f"Перевірка доступу до сервера завершено з кодом 255.\n{output}")
                    self._set_action_button_state("server-check", "error")

            self.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def run_server_update(self) -> None:
        payload = self._last_update_package_payload
        if not isinstance(payload, dict):
            messagebox.showinfo("Немає пакета", "Спочатку створи або онови пакет версії.")
            return

        host = self.server_host.get().strip()
        port = self.server_port.get().strip() or "22"
        user = self.server_user.get().strip()
        key_path = self.ssh_key_path.get().strip()
        server_password = self.server_password.get().strip()
        sudo_password = self.sudo_password.get().strip()
        server_path = self.server_path.get().strip()

        if not host or not user:
            messagebox.showwarning("Не вистачає даних", "Заповни хоча б Host і User для оновлення сервера.")
            return

        if not key_path and not server_password:
            messagebox.showwarning(
                "Не вистачає даних",
                "Для оновлення сервера вкажи або SSH key, або SSH password.",
            )
            return

        source_files = [str(item) for item in payload.get("source_files", []) or []]
        file_types = {str(item) for item in payload.get("file_types", []) or []}
        need_db_update = "database" in file_types
        need_restart = self.restart_services.get() and bool(file_types & {"code", "ui", "database"})
        need_requirements = any(path.replace("\\", "/") == "requirements.txt" for path in source_files)
        sudo_secret = sudo_password or server_password

        if need_restart and not sudo_secret:
            messagebox.showwarning(
                "Не вистачає даних",
                "Для перезапуску сервісів введи пароль адміна (sudo) або SSH пароль, якщо він підходить і для sudo.",
            )
            return

        self._set_launch_status("Оновлення сервера: підключення...")
        self._append_product_log("[Сервер] Починаємо автоматичне оновлення.")

        self._begin_activity()

        def worker() -> None:
            try:
                client, error = _open_paramiko_client(
                    host,
                    port,
                    user,
                    key_path,
                    server_password,
                )
                if client is None:
                    self.after(0, lambda: self._finish_remote_update(False, error or "Не вдалося підключитися до сервера."))
                    return

                transport = client.get_transport()
                if transport is not None:
                    transport.set_keepalive(30)

                remote_steps = [
                    f"git config --global --replace-all safe.directory {shlex.quote(server_path or '.')}",
                    "git status --short --branch --untracked-files=all",
                    "env GIT_TERMINAL_PROMPT=0 git pull --ff-only",
                ]
                if need_requirements:
                    remote_steps.append(remote_python_step('-m pip install -r requirements.txt'))
                if need_db_update and self.run_safe_update.get():
                    remote_steps.append(remote_python_step('scripts/safe_update_db.py'))
                remote_steps.append("cd frontend/admin && npm run build")
                remote_steps.append(
                    f"mkdir -p {shlex.quote(REMOTE_ADMIN_WEBROOT)} && cp -a dist/. {shlex.quote(REMOTE_ADMIN_WEBROOT)}/",
                )
                if need_restart:
                    remote_steps.append("sudo -S -p '' systemctl restart furniture-api furniture-bot")
                    remote_steps.append(
                        remote_python_step('../../scripts/wait_for_api_ready.py --url http://127.0.0.1:8000/health --timeout 90'),
                    )

                remote_path = shlex.quote(server_path or ".")
                remote_command = f"cd {remote_path} && " + " && ".join(remote_steps)
                self.after(0, lambda: self._set_launch_status("Оновлення сервера: git pull..."))
                stdin, stdout, stderr = client.exec_command(remote_command, get_pty=True, timeout=120)
                if need_restart and sudo_secret:
                    self.after(0, lambda: self._set_launch_status("Оновлення сервера: перезапуск сервісів..."))
                    stdin.write(sudo_secret + "\n")
                    stdin.flush()

                stdout_text, stderr_text, exit_status = _collect_channel_output(stdout.channel, timeout_seconds=900.0)
                combined = "\n".join(part for part in [stdout_text, stderr_text] if part)
                if exit_status == 0:
                    self.after(0, lambda: self._finish_remote_update(True, combined or "Оновлення сервера завершено успішно."))
                else:
                    self.after(0, lambda: self._finish_remote_update(False, combined or f"Команда завершилась з кодом {exit_status}"))
            except Exception as exc:  # pragma: no cover - depends on remote host
                error_text = f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__
                trace_text = traceback.format_exc(limit=3)
                self.after(0, lambda: self._finish_remote_update(False, f"{error_text}\n{trace_text}"))
            finally:
                try:
                    client.close()  # type: ignore[name-defined]
                except Exception:
                    pass

        threading.Thread(target=worker, daemon=True).start()

    def _finish_remote_update(self, success: bool, output: str) -> None:
        self._end_activity()
        self._set_launch_status("Оновлення сервера завершено." if success else "Оновлення сервера не вдалося.")
        message = output.strip() or "Немає додаткового виводу."
        self._append_product_log(f"[Сервер] {message}")
        self.record_history(
            "server.remote_update",
            details="Автоматичне оновлення сервера через Product Center",
            status="ok" if success else "error",
            extra={"output": message},
        )
        if success:
            messagebox.showinfo("Готово", "Оновлення сервера виконано успішно.")
            self._set_action_button_state("server-update", "success")
        else:
            messagebox.showerror("Помилка", f"Оновлення сервера не вдалося.\n{message}")
            self._set_action_button_state("server-update", "error")

    def run_local_update(self) -> None:
        if self.mode.get() != "local":
            messagebox.showwarning("Серверний режим", "Локальне виконання доступне лише в режимі локального тесту.")
            return

        main_db = self.main_db.get().strip()
        command = build_local_command(main_db, self.backup.get())
        env = os.environ.copy()
        env["FURNITURE_PLATFORM_DB_PATH"] = main_db

        try:
            result = subprocess.run(command, cwd=str(PROJECT_ROOT), env=env, capture_output=True, text=True, check=False)
        except OSError as exc:
            messagebox.showerror("Помилка виконання", str(exc))
            self._set_action_button_state("db-local-update", "error")
            self.record_history(
                "db.local_update",
                details="Локальне безпечне оновлення не запустилося",
                command=command,
                status="error",
                extra={"error": str(exc)},
            )
            return

        output = []
        if result.stdout.strip():
            output.append(result.stdout.strip())
        if result.stderr.strip():
            output.append(result.stderr.strip())

        self.db_preview.delete("1.0", "end")
        self.db_preview.insert("1.0", "\n\n".join(output) or "Немає виводу.")

        if result.returncode == 0:
            messagebox.showinfo("Готово", "Локальне безпечне оновлення завершено.")
            self._set_action_button_state("db-local-update", "success")
        else:
            messagebox.showerror("Помилка", f"Локальне безпечне оновлення завершилось з кодом {result.returncode}.")
            self._set_action_button_state("db-local-update", "error")
        self.record_history(
            "db.local_update",
            details="Локальне безпечне оновлення БД",
            command=command,
            status="ok" if result.returncode == 0 else "error",
            extra={
                "returncode": result.returncode,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
            },
        )

    def refresh_git_status(self) -> None:
        if not git_available():
            self._set_git_status("Git не знайдено в системі.")
            self.git_config_label.configure(text="")
            self.git_file_paths = []
            self._set_git_files([])
            return

        try:
            status = git_status_text()
            entries = git_status_entries()
        except RuntimeError as exc:
            self._set_git_status(str(exc))
            self.git_config_label.configure(text="")
            self.git_file_paths = []
            self._set_git_files([])
            return

        self._set_git_status(status)
        self.git_file_paths = [path for _, path in entries]
        self._set_git_files(entries)

        user_name = git_config_value("user.name")
        user_email = git_config_value("user.email")
        if user_name and user_email:
            self.git_config_label.configure(text=f"Git user: {user_name} <{user_email}>")
        else:
            self.git_config_label.configure(text="У Git ще не налаштовано user.name або user.email.")

    def refresh_git_status_async(self) -> None:
        def worker() -> None:
            try:
                if not git_available():
                    data = ("Git не знайдено в системі.", "", [], [])
                else:
                    status = git_status_text()
                    entries = git_status_entries()
                    user_name = git_config_value("user.name")
                    user_email = git_config_value("user.email")
                    if user_name and user_email:
                        config_text = f"Git user: {user_name} <{user_email}>"
                    else:
                        config_text = "У Git ще не налаштовано user.name або user.email."
                    data = (status, config_text, [path for _, path in entries], entries)
            except Exception as exc:
                data = (str(exc), "", [], [])

            def finish() -> None:
                status, config_text, file_paths, entries = data
                self._set_git_status(status)
                self.git_config_label.configure(text=config_text)
                self.git_file_paths = file_paths
                self._set_git_files(entries)

            self.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def _set_git_status(self, text: str) -> None:
        self.git_status.delete("1.0", "end")
        self.git_status.insert("1.0", text)

    def _set_git_files(self, entries: list[tuple[str, str]]) -> None:
        self.git_files.delete(0, "end")
        if not entries:
            self.git_files.insert("end", "Немає змінених файлів.")
            return

        for status, path in entries:
            self.git_files.insert("end", f"[{status}] {path}")

    def select_all_git_files(self) -> None:
        if self.git_file_paths:
            self.git_files.selection_set(0, "end")

    def clear_git_file_selection(self) -> None:
        self.git_files.selection_clear(0, "end")

    def selected_git_paths(self) -> list[str]:
        selected_indices = list(self.git_files.curselection())
        return [
            self.git_file_paths[index]
            for index in selected_indices
            if 0 <= index < len(self.git_file_paths)
        ]

    def _restore_git_file_selection(self, paths: list[str]) -> None:
        if not paths:
            return

        selected_indices = [
            index
            for index, path in enumerate(self.git_file_paths)
            if path in paths
        ]
        if selected_indices:
            self.git_files.selection_set(selected_indices[0], selected_indices[-1])

    def stage_selected_changes(self) -> None:
        if not git_available():
            messagebox.showerror("Git не знайдено", "Система не бачить команду git.")
            return

        paths = self.selected_git_paths()
        if not paths:
            messagebox.showwarning("Нічого не вибрано", "Спочатку вибери хоча б один файл у списку.")
            return

        code, output = git_add_paths(paths)
        self.refresh_git_status()
        self._restore_git_file_selection(paths)
        if code == 0:
            messagebox.showinfo("Готово", "Вибрані файли підготовлено до коміту.")
            self._append_product_log(
                f"[Git] Підготовлено {len(paths)} вибраних файлів."
            )
        else:
            messagebox.showerror("Помилка", output or "Не вдалося підготувати вибрані файли.")
        self.record_history(
            "git.stage.selected",
            details="Підготовка вибраних файлів",
            files=paths,
            status="ok" if code == 0 else "error",
            extra={"output": output},
        )
    def stage_all_changes(self) -> None:
        if not git_available():
            messagebox.showerror("Git не знайдено", "Система не бачить команду git.")
            return

        code, output = git_add_all()
        self.refresh_git_status()
        if code == 0:
            messagebox.showinfo("Готово", "Усі зміни підготовлено до коміту.")
        else:
            messagebox.showerror("Помилка", output or "Не вдалося виконати git add -A.")
        self.record_history(
            "git.stage.all",
            details="Підготовка всіх змін",
            status="ok" if code == 0 else "error",
            extra={"output": output},
        )

    def commit_selected_changes(self) -> bool:
        if not git_available():
            messagebox.showerror("Git не знайдено", "Система не бачить команду git.")
            return False

        message = self.commit_message.get().strip()
        if not message:
            messagebox.showwarning("Порожнє повідомлення", "Вкажи текст для коміту.")
            return False

        user_name = git_config_value("user.name")
        user_email = git_config_value("user.email")
        if not user_name or not user_email:
            messagebox.showwarning(
                "Git не налаштовано",
                "Для коміту треба встановити user.name і user.email у Git.",
            )
            return False

        paths = self.selected_git_paths()
        staged_files = paths if paths else git_staged_paths()
        if paths:
            add_code, add_output = git_add_paths(paths)
            if add_code != 0:
                messagebox.showerror("Помилка add", add_output or "Не вдалося підготувати вибрані файли.")
                return False
        elif not staged_files:
            messagebox.showwarning(
                "Нічого не вибрано для коміту",
                "Спочатку вибери файли у списку або підготуй зміни кнопкою «Підготувати вибрані».",
            )
            return False

        commit_code, commit_output = git_commit(message, paths if paths else None)
        self.refresh_git_status()
        if commit_code == 0:
            messagebox.showinfo("Коміт створено", commit_output or "Локальний коміт успішно створено.")
            self.record_history(
                "git.commit",
                details=message,
                files=staged_files,
                status="ok",
                extra={"output": commit_output},
            )
            return True
        else:
            messagebox.showerror("Помилка коміту", commit_output or "Git не зміг створити коміт.")
            self.record_history(
                "git.commit",
                details=message,
                files=staged_files,
                status="error",
                extra={"output": commit_output},
            )
            return False

    def push_current_branch(self) -> None:
        if not git_available():
            messagebox.showerror("Git не знайдено", "Система не бачить команду git.")
            return

        should_push = messagebox.askyesno(
            "Підтвердити push",
            "Відправити поточну гілку на віддалений репозиторій?",
        )
        if not should_push:
            return

        code, output = git_push()
        self.refresh_git_status()
        if code == 0:
            messagebox.showinfo("Push виконано", output or "Зміни успішно відправлено.")
        else:
            messagebox.showerror("Помилка push", output or "Git не зміг виконати push.")
        self.record_history(
            "git.push",
            details="Відправка змін у віддалений репозиторій",
            status="ok" if code == 0 else "error",
            extra={"output": output},
        )

    def commit_and_push_selected_changes(self) -> None:
        committed = self.commit_selected_changes()
        if not committed:
            return
        if not git_available():
            return

        code, output = git_push()
        self.refresh_git_status()
        if code == 0:
            messagebox.showinfo("Коміт і push", output or "Коміт виконано і зміни відправлено.")
        else:
            messagebox.showerror("Помилка push", output or "Коміт створено, але push не вдалося виконати.")
        self.record_history(
            "git.commit_push",
            details=self.commit_message.get().strip(),
            files=self.selected_git_paths() or self.git_file_paths,
            status="ok" if code == 0 else "error",
            extra={"output": output},
        )
    def _append_product_log(self, text: str) -> None:
        self.product_log.insert("end", text.rstrip() + "\n")
        self.product_log.see("end")

    def record_history(
        self,
        action: str,
        *,
        details: str = "",
        files: list[str] | None = None,
        command: list[str] | None = None,
        status: str = "ok",
        extra: dict[str, object] | None = None,
    ) -> None:
        entry: dict[str, object] = {
            "timestamp": current_timestamp(),
            "action": action,
            "status": status,
        }
        if details:
            entry["details"] = details
        if files:
            entry["files"] = files
        if command:
            entry["command"] = command
        if extra:
            entry["extra"] = extra

        try:
            with HISTORY_PATH.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError as exc:
            self._append_product_log(f"[Історія] Не вдалося записати подію: {exc}")
            return

        self.refresh_history()

    def refresh_history(self) -> None:
        entries = read_json_lines(HISTORY_PATH, limit=250)
        if not hasattr(self, "history_list"):
            return

        selected_filter = self.history_filter.get()
        search_text = self.history_search.get().strip().lower()
        if selected_filter and selected_filter != "Усі":
            entries = [entry for entry in entries if history_category(str(entry.get("action", ""))) == selected_filter]
        if search_text:
            entries = [entry for entry in entries if search_text in history_search_text(entry)]

        self.history_list.delete(0, "end")
        if not entries:
            self.history_list.insert("end", "Історія поки що порожня.")
            self.history_detail.delete("1.0", "end")
            self.history_detail.insert("1.0", "Поки що немає записів.")
            return

        ordered_entries = list(reversed(entries))
        for entry in ordered_entries:
            timestamp = str(entry.get("timestamp", ""))
            action = str(entry.get("action", ""))
            status = str(entry.get("status", ""))
            category = history_category(action)
            summary = str(entry.get("details", ""))
            label = f"{timestamp} | {category} | {action} | {status}"
            if summary:
                label = f"{label} | {summary}"
            self.history_list.insert("end", label)

        self._history_entries_cache = ordered_entries
        self.show_selected_history_item(default_first=True)

    def show_selected_history_item(self, default_first: bool = False) -> None:
        if not hasattr(self, "history_detail"):
            return

        selection = self.history_list.curselection()
        if not selection:
            if default_first and getattr(self, "_history_entries_cache", None):
                entry = self._history_entries_cache[0]
            else:
                return
        else:
            index = selection[0]
            cache = getattr(self, "_history_entries_cache", [])
            if not cache or index >= len(cache):
                return
            entry = cache[index]

        self.history_detail.delete("1.0", "end")
        self.history_detail.insert("1.0", json.dumps(entry, ensure_ascii=False, indent=2))

    def open_history_file(self) -> None:
        self._open_path(HISTORY_PATH)

    def clear_history_search(self) -> None:
        self.history_search.set("")
        self.refresh_history()

    def clear_history_view(self) -> None:
        if hasattr(self, "history_list"):
            self.history_list.delete(0, "end")
        if hasattr(self, "history_detail"):
            self.history_detail.delete("1.0", "end")
            self.history_detail.insert("1.0", "Подання очищено. Файл історії не видалено.")

    def export_history_csv(self) -> None:
        entries = read_json_lines(HISTORY_PATH, limit=5000)
        selected_filter = self.history_filter.get()
        search_text = self.history_search.get().strip().lower()
        if selected_filter and selected_filter != "Усі":
            entries = [entry for entry in entries if history_category(str(entry.get("action", ""))) == selected_filter]
        if search_text:
            entries = [entry for entry in entries if search_text in history_search_text(entry)]

        export_path = PROJECT_ROOT / f"product_center_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        try:
            with export_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["timestamp", "category", "action", "status", "details", "files", "command", "extra"],
                )
                writer.writeheader()
                for entry in entries:
                    writer.writerow(
                        {
                            "timestamp": entry.get("timestamp", ""),
                            "category": history_category(str(entry.get("action", ""))),
                            "action": entry.get("action", ""),
                            "status": entry.get("status", ""),
                            "details": entry.get("details", ""),
                            "files": json.dumps(entry.get("files", []), ensure_ascii=False),
                            "command": json.dumps(entry.get("command", []), ensure_ascii=False),
                            "extra": json.dumps(entry.get("extra", {}), ensure_ascii=False),
                        }
                    )
        except OSError as exc:
            messagebox.showerror("Не вдалося експортувати", str(exc))
            return

        self.record_history(
            "history.export",
            details=f"Експортовано історію в {export_path.name}",
            status="ok",
            extra={"path": str(export_path), "filter": selected_filter},
        )
        messagebox.showinfo("Експорт завершено", f"Історію експортовано в:\n{export_path}")

    def refresh_product_map(self) -> None:
        if not hasattr(self, "map_tree"):
            return

        query = self.map_search.get().strip().lower() if hasattr(self, "map_search") else ""
        specs = [
            spec
            for spec in self.product_map_specs
            if not query or query in component_search_text(spec)
        ]

        self.map_tree.delete(*self.map_tree.get_children())
        self.map_item_to_key: dict[str, str] = {}
        self.map_group_to_items: dict[str, list[str]] = {}
        group_nodes: dict[str, str] = {}

        for spec in specs:
            group = str(spec.get("group", "Інше"))
            if group not in group_nodes:
                group_nodes[group] = self.map_tree.insert("", "end", iid=f"group::{group}", text=group, values=("", "", ""))

        for spec in specs:
            key = str(spec["key"])
            group = str(spec.get("group", "Інше"))
            group_node = group_nodes[group]
            status = self.component_status_text(spec)
            control = component_control_label(spec)
            item_id = f"component::{key}"
            self.map_tree.insert(
                group_node,
                "end",
                iid=item_id,
                text=str(spec.get("name", key)),
                values=(status, control, str(spec.get("summary", ""))),
            )
            self.map_item_to_key[item_id] = key
            self.map_group_to_items.setdefault(group_node, []).append(item_id)

        for group_name, node_id in group_nodes.items():
            count = len(self.map_group_to_items.get(node_id, []))
            self.map_tree.item(node_id, text=f"{group_name} ({count})")
            if count == 0:
                self.map_tree.item(node_id, values=("порожньо", "", ""))

        selected = self.product_map_selected_key
        if selected:
            if selected in self.product_map_specs_by_key and (not query or query in component_search_text(self.product_map_specs_by_key[selected])):
                self.select_map_component(selected)
            elif specs:
                self.select_map_component(str(specs[0]["key"]))
            else:
                self.clear_map_detail()
        else:
            first = specs[0]["key"] if specs else None
            if first:
                self.select_map_component(str(first))
            else:
                self.clear_map_detail()

    def component_status_text(self, spec: dict[str, object]) -> str:
        parts: list[str] = []
        process_key = spec.get("process_key")
        if process_key:
            proc = self.managed_processes.get(str(process_key))
            if proc and proc.poll() is None:
                parts.append(f"процес: PID {proc.pid}")
            else:
                parts.append("процес: зупинено")

        open_targets = component_open_targets(spec)
        url_targets = [str(target) for target in open_targets if isinstance(target, str) and target.startswith("http")]
        if url_targets:
            online = any(self._service_responds(url) for url in url_targets)
            parts.append(f"web: {'online' if online else 'offline'}")

        file_count = len(component_files(spec))
        if file_count:
            parts.append(f"файлів: {file_count}")

        if not parts:
            parts.append("готово")

        return " | ".join(parts)

    def selected_map_item_id(self) -> str | None:
        selection = self.map_tree.selection() if hasattr(self, "map_tree") else ()
        if not selection:
            return None
        return selection[0]

    def selected_map_component_spec(self) -> dict[str, object] | None:
        item_id = self.selected_map_item_id()
        if not item_id:
            return None
        key = self.map_item_to_key.get(item_id)
        if not key:
            return None
        return self.product_map_specs_by_key.get(key)

    def select_map_component(self, key: str) -> None:
        item_id = f"component::{key}"
        if hasattr(self, "map_tree") and self.map_tree.exists(item_id):
            self.map_tree.selection_set(item_id)
            self.map_tree.focus(item_id)
            self.map_tree.see(item_id)
            self.show_selected_map_component()

    def show_selected_map_component(self, default_first: bool = False) -> None:
        if not hasattr(self, "map_detail"):
            return

        item_id = self.selected_map_item_id()
        if not item_id:
            if default_first and self.product_map_specs:
                self.select_map_component(str(self.product_map_specs[0]["key"]))
            else:
                self.clear_map_detail()
            return

        key = self.map_item_to_key.get(item_id)
        if key:
            self.product_map_selected_key = key
            spec = self.product_map_specs_by_key.get(key)
            if spec:
                self.display_map_component(spec)
            return

        if item_id.startswith("group::"):
            self.product_map_selected_key = None
            self.display_map_group(item_id)
            return

    def display_map_component(self, spec: dict[str, object]) -> None:
        name = str(spec.get("name", spec.get("key", "")))
        group = str(spec.get("group", ""))
        summary = str(spec.get("summary", ""))
        responsibility = str(spec.get("responsibility", ""))
        status = self.component_status_text(spec)
        depends_on = [str(item) for item in spec.get("depends_on", []) or []]
        file_paths = component_files(spec)
        open_targets = component_open_targets(spec)

        self.map_title.configure(text=name)
        self.map_status.configure(text=f"{group} | {status}")

        lines = [
            f"Компонент: {name}",
            f"Група: {group}",
            "",
            "Що це означає:",
            summary,
            "",
            "Відповідає за:",
            responsibility,
            "",
            "Стан:",
            status,
            "",
            "Залежить від:",
            ", ".join(depends_on) if depends_on else "Немає явних залежностей",
            "",
            "Відкриття:",
        ]
        if open_targets:
            for target in open_targets:
                lines.append(f"- {target}")
        else:
            lines.append("- Немає окремого ресурсу для відкриття")
        lines.extend(["", "Файли:"])
        if file_paths:
            for path in file_paths:
                lines.append(f"- {path}")
        else:
            lines.append("- Файли не знайдено")

        self.map_detail.delete("1.0", "end")
        self.map_detail.insert("1.0", "\n".join(lines))

        self.map_files.delete(0, "end")
        for path in file_paths:
            self.map_files.insert("end", path)

    def display_map_group(self, group_item_id: str) -> None:
        group_name = self.map_tree.item(group_item_id, "text")
        child_ids = list(self.map_tree.get_children(group_item_id))
        child_specs = [self.product_map_specs_by_key[self.map_item_to_key[item_id]] for item_id in child_ids if item_id in self.map_item_to_key]
        statuses = [f"- {str(spec.get('name', ''))}: {self.component_status_text(spec)}" for spec in child_specs]

        self.map_title.configure(text=group_name)
        self.map_status.configure(text=f"Компонентів: {len(child_specs)}")
        self.map_detail.delete("1.0", "end")
        self.map_detail.insert(
            "1.0",
            "\n".join(
                [
                    f"Група: {group_name}",
                    "",
                    "У цій групі:",
                    *(statuses if statuses else ["- Порожньо"]),
                    "",
                    "Порада:",
                    "Оберіть конкретний компонент, щоб побачити файли, залежності та керування.",
                ]
            ),
        )
        self.map_files.delete(0, "end")

    def clear_map_detail(self) -> None:
        self.map_title.configure(text="Оберіть компонент у карті")
        self.map_status.configure(text="")
        self.map_detail.delete("1.0", "end")
        self.map_detail.insert("1.0", "Карта ще не має вибраного компонента.")
        self.map_files.delete(0, "end")

    def open_selected_component_resource(self) -> None:
        spec = self.selected_map_component_spec()
        if not spec:
            messagebox.showwarning("Нічого не вибрано", "Спочатку обери компонент у карті продукту.")
            return
        targets = component_open_targets(spec)
        if not targets:
            messagebox.showinfo("Немає ресурсу", "Для цього компонента немає окремого ресурсу для відкриття.")
            return

        target = targets[0]
        if isinstance(target, str) and target.startswith("http"):
            webbrowser.open(target)
        else:
            self._open_path(Path(str(target)))
        self.record_history(
            "map.open_resource",
            details=str(spec.get("name", "")),
            extra={"target": str(target)},
        )

    def open_selected_component_files(self) -> None:
        spec = self.selected_map_component_spec()
        if not spec:
            messagebox.showwarning("Нічого не вибрано", "Спочатку обери компонент у карті продукту.")
            return

        file_paths = component_files(spec)
        if not file_paths:
            messagebox.showinfo("Немає файлів", "Для цього компонента не знайдено пов’язаних файлів.")
            return

        self._open_path(PROJECT_ROOT / file_paths[0])
        self.record_history(
            "map.open_files",
            details=str(spec.get("name", "")),
            files=file_paths,
        )

    def open_selected_map_file(self) -> None:
        spec = self.selected_map_component_spec()
        if not spec:
            messagebox.showwarning("Нічого не вибрано", "Спочатку обери компонент у карті продукту.")
            return

        selected_indices = list(self.map_files.curselection()) if hasattr(self, "map_files") else []
        if selected_indices and self.map_files.size() > selected_indices[0]:
            path_text = self.map_files.get(selected_indices[0])
        else:
            file_paths = component_files(spec)
            if not file_paths:
                messagebox.showinfo("Немає файлів", "Для цього компонента не знайдено файлів.")
                return
            path_text = file_paths[0]

        self._open_path(PROJECT_ROOT / path_text)
        self.record_history(
            "map.open_file",
            details=str(spec.get("name", "")),
            files=[path_text],
        )

    def open_selected_map_folder(self) -> None:
        spec = self.selected_map_component_spec()
        if not spec:
            messagebox.showwarning("Нічого не вибрано", "Спочатку обери компонент у карті продукту.")
            return

        selected_indices = list(self.map_files.curselection()) if hasattr(self, "map_files") else []
        if selected_indices and self.map_files.size() > selected_indices[0]:
            path_text = self.map_files.get(selected_indices[0])
        else:
            file_paths = component_files(spec)
            if not file_paths:
                messagebox.showinfo("Немає файлів", "Для цього компонента не знайдено файлів.")
                return
            path_text = file_paths[0]

        self._open_path((PROJECT_ROOT / path_text).parent)
        self.record_history(
            "map.open_folder",
            details=str(spec.get("name", "")),
            files=[path_text],
        )

    def copy_selected_component_summary(self) -> None:
        spec = self.selected_map_component_spec()
        if not spec:
            messagebox.showwarning("Нічого не вибрано", "Спочатку обери компонент у карті продукту.")
            return

        payload = "\n".join(
            [
                f"Компонент: {spec.get('name', '')}",
                f"Група: {spec.get('group', '')}",
                f"Що робить: {spec.get('summary', '')}",
                f"Стан: {self.component_status_text(spec)}",
            ]
        )
        self.clipboard_clear()
        self.clipboard_append(payload)
        self.update()
        self.record_history("map.copy_summary", details=str(spec.get("name", "")))
        messagebox.showinfo("Скопійовано", "Короткий опис компонента скопійовано в буфер.")

    def clear_map_search(self) -> None:
        self.map_search.set("")
        self.refresh_product_map()

    def export_product_map(self) -> None:
        query = self.map_search.get().strip().lower()
        specs = [
            spec
            for spec in self.product_map_specs
            if not query or query in component_search_text(spec)
        ]
        if not specs:
            messagebox.showinfo("Немає даних", "Немає компонентів для експорту з поточним фільтром.")
            return

        export_path = PROJECT_ROOT / f"product_center_map_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        lines: list[str] = []
        lines.append("# Карта продукту")
        lines.append("")
        lines.append(f"- Згенеровано: {current_timestamp()}")
        lines.append(f"- Компонентів: {len(specs)}")
        if query:
            lines.append(f"- Фільтр: `{self.map_search.get().strip()}`")
        lines.append("")

        grouped: dict[str, list[dict[str, object]]] = {}
        for spec in specs:
            grouped.setdefault(str(spec.get("group", "Інше")), []).append(spec)

        for group in sorted(grouped):
            lines.append(f"## {group}")
            lines.append("")
            for spec in grouped[group]:
                name = str(spec.get("name", ""))
                key = str(spec.get("key", ""))
                summary = str(spec.get("summary", ""))
                responsibility = str(spec.get("responsibility", ""))
                status = self.component_status_text(spec)
                depends_on = [str(item) for item in spec.get("depends_on", []) or []]
                files = component_files(spec)
                lines.append(f"### {name} (`{key}`)")
                lines.append("")
                lines.append(f"- Стан: {status}")
                lines.append(f"- Що робить: {summary}")
                lines.append(f"- Відповідає за: {responsibility}")
                lines.append(f"- Залежить від: {', '.join(depends_on) if depends_on else 'немає явних залежностей'}")
                lines.append(f"- Керування: {component_control_label(spec)}")
                if files:
                    lines.append("- Файли:")
                    for path in files:
                        lines.append(f"  - {path}")
                else:
                    lines.append("- Файли: не знайдено")
                lines.append("")

        try:
            export_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        except OSError as exc:
            messagebox.showerror("Не вдалося експортувати", str(exc))
            return

        self.record_history(
            "map.export",
            details=export_path.name,
            status="ok",
            extra={"path": str(export_path), "filter": self.map_search.get().strip()},
        )
        self._append_product_log(f"[Карта] Експортовано у {export_path.name}")
        messagebox.showinfo("Експорт завершено", f"Карту продукту експортовано в:\n{export_path}")
        self._open_path(export_path)

    def start_selected_component(self) -> None:
        spec = self.selected_map_component_spec()
        if not spec:
            messagebox.showwarning("Нічого не вибрано", "Спочатку обери компонент у карті продукту.")
            return

        start_command = spec.get("start_command")
        process_key = str(spec.get("process_key") or "")
        if not start_command or not process_key:
            messagebox.showinfo("Запуск недоступний", "Для цього компонента окремий запуск не налаштовано.")
            return

        env = None
        if process_key in {"api", "bot"}:
            env = {
                "FURNITURE_PLATFORM_DB_PATH": self.main_db.get().strip(),
                "FURNITURE_LEGACY_DB_PATH": self.legacy_db.get().strip(),
            }

        self.record_history(
            "map.start_component",
            details=str(spec.get("name", "")),
            command=[str(item) for item in start_command],
            extra={"process_key": process_key},
        )
        self._start_managed_process(
            process_key,
            str(spec.get("name", process_key)),
            [str(item) for item in start_command],
            env=env,
            cwd=Path(str(spec.get("cwd", PROJECT_ROOT))),
        )

    def stop_selected_component(self) -> None:
        spec = self.selected_map_component_spec()
        if not spec:
            messagebox.showwarning("Нічого не вибрано", "Спочатку обери компонент у карті продукту.")
            return

        process_key = str(spec.get("process_key") or "")
        if not process_key:
            messagebox.showinfo("Зупинка недоступна", "Для цього компонента окремий процес не налаштовано.")
            return

        proc = self.managed_processes.get(process_key)
        if not proc:
            messagebox.showinfo("Процес не знайдено", "Компонент зараз не запущений.")
            return

        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except Exception:
                proc.kill()
        self.record_history(
            "map.stop_component",
            details=str(spec.get("name", "")),
            extra={"process_key": process_key, "pid": proc.pid},
        )
        self._append_product_log(f"[{spec.get('name', process_key)}] Зупинено")
        self.refresh_managed_processes()

    def generate_daily_report(self) -> None:
        report_date = self.history_report_date.get().strip()
        if not report_date:
            messagebox.showwarning("Дата не вказана", "Вкажи дату звіту у форматі YYYY-MM-DD.")
            return

        try:
            datetime.strptime(report_date, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Невірна дата", "Дата має бути у форматі YYYY-MM-DD.")
            return

        entries = read_json_lines(HISTORY_PATH, limit=10000)
        entries = [entry for entry in entries if history_entry_date(entry) == report_date]

        if not entries:
            messagebox.showinfo("Немає даних", f"За {report_date} записів у історії немає.")
            self.record_history(
                "history.report",
                details=f"Спроба сформувати звіт за {report_date}",
                status="ok",
                extra={"report_date": report_date, "entries": 0},
            )
            return

        category_counts = Counter(history_category(str(entry.get("action", ""))) for entry in entries)
        action_counts = Counter(str(entry.get("action", "")) for entry in entries)
        file_counter = Counter()
        for entry in entries:
            for path in entry.get("files", []) or []:
                file_counter[str(path)] += 1

        report_path = PROJECT_ROOT / f"product_center_report_{report_date}.md"
        lines: list[str] = []
        lines.append(f"# Звіт за {report_date}")
        lines.append("")
        lines.append(f"- Записів: {len(entries)}")
        lines.append(f"- Категорій: {len(category_counts)}")
        lines.append(f"- Унікальних дій: {len(action_counts)}")
        lines.append("")
        lines.append("## По категоріях")
        for category, count in category_counts.most_common():
            lines.append(f"- {category}: {count}")
        lines.append("")
        lines.append("## Найчастіші дії")
        for action, count in action_counts.most_common(20):
            lines.append(f"- {action}: {count}")
        lines.append("")
        lines.append("## Найчастіше змінювані файли")
        if file_counter:
            for path, count in file_counter.most_common(20):
                lines.append(f"- {path}: {count}")
        else:
            lines.append("- Немає даних про файли.")
        lines.append("")
        lines.append("## Останні події")
        for entry in entries[-25:]:
            ts = str(entry.get("timestamp", ""))
            action = str(entry.get("action", ""))
            status = str(entry.get("status", ""))
            details = str(entry.get("details", ""))
            line = f"- `{ts}` {action} ({status})"
            if details:
                line += f": {details}"
            lines.append(line)

        try:
            report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        except OSError as exc:
            messagebox.showerror("Не вдалося створити звіт", str(exc))
            return

        self.record_history(
            "history.report",
            details=f"Сформовано звіт за {report_date}",
            status="ok",
            extra={"report_date": report_date, "path": str(report_path), "entries": len(entries)},
        )
        self._append_product_log(f"[Звіт] Створено файл {report_path.name}")
        messagebox.showinfo("Звіт створено", f"Готово: {report_path}")
        self._open_path(report_path)

    def _open_path(self, path: Path) -> None:
        if not path.exists():
            messagebox.showerror("Файл не знайдено", f"Не знайдено: {path}")
            return
        try:
            os.startfile(str(path))
        except OSError as exc:
            messagebox.showerror("Не вдалося відкрити", str(exc))

    def open_project_folder(self) -> None:
        self._open_path(PROJECT_ROOT)

    def open_main_database(self) -> None:
        self._open_path(Path(self.main_db.get().strip()))

    def open_legacy_database(self) -> None:
        self._open_path(Path(self.legacy_db.get().strip()))

    def open_readme(self) -> None:
        self._open_path(PROJECT_ROOT / "README.md")

    def open_workflow_doc(self) -> None:
        self._open_path(PROJECT_ROOT / "docs" / "db_update_workflow.md")

    def open_simple_guide(self) -> None:
        self._open_path(PROJECT_ROOT / "docs" / "product_center_simple_guide.md")

    def open_help_guide(self) -> None:
        self._open_path(PROJECT_ROOT / "docs" / "product_center_help.md")

    def open_update_packages_folder(self) -> None:
        UPDATE_PACKAGES_DIR.mkdir(parents=True, exist_ok=True)
        self._open_path(UPDATE_PACKAGES_DIR)

    def open_api_docs(self) -> None:
        webbrowser.open(LOCAL_API_DOCS_URL)

    def open_frontend_app(self) -> None:
        webbrowser.open(LOCAL_APP_URL)

    def open_frontend_admin(self) -> None:
        webbrowser.open(LOCAL_ADMIN_URL)

    def open_maintenance_owner_login(self) -> None:
        webbrowser.open(OWNER_LOGIN_URL)

    def open_maintenance_owner_logout(self) -> None:
        webbrowser.open(OWNER_LOGOUT_URL)

    def open_all_local_pages(self) -> None:
        webbrowser.open(LOCAL_API_DOCS_URL)
        webbrowser.open(LOCAL_ADMIN_URL)
        webbrowser.open(LOCAL_APP_URL)

    def preview_maintenance_page(self) -> None:
        message = self.maintenance_message.get().strip()
        eta = self.maintenance_eta.get().strip()
        try:
            preview_path = create_maintenance_preview_file(message=message, eta=eta)
        except OSError as exc:
            messagebox.showerror("Не вдалося створити preview", str(exc))
            return
        except Exception as exc:
            messagebox.showerror("Не вдалося створити preview", str(exc))
            return

        self.maintenance_preview_status.set(f"Готово: {preview_path}")
        self._open_path(preview_path)

    def _finish_maintenance_server_control(self, result: object | None = None, error_text: str | None = None) -> None:
        self._maintenance_server_control_running = False
        self._end_activity()

        if error_text is not None:
            self._maintenance_server_control_last_result = None
            self.maintenance_server_control_status.set(f"Помилка: {error_text}")
            self._append_product_log(f"[Технічні роботи] {error_text}")
            messagebox.showerror("Не вдалося виконати дію", error_text)
            return

        if result is None:
            return

        control_result = result
        self._maintenance_server_control_last_result = control_result
        action = str(getattr(control_result, "action", "status"))
        status_label = str(getattr(control_result, "status_label", "unknown"))
        stage = str(getattr(control_result, "stage", "unknown"))
        exit_code = getattr(control_result, "exit_code", None)
        exit_code_text = "n/a" if exit_code is None else str(exit_code)
        message_text = str(getattr(control_result, "message", "")).strip() or "Готово."
        self.maintenance_server_control_status.set(
            f"{message_text} | stage={stage} | exit={exit_code_text} | "
            f"nginx={getattr(control_result, 'nginx_status', 'unknown')} | "
            f"public={getattr(control_result, 'public_http', 'n/a')} | "
            f"admin={getattr(control_result, 'admin_http', 'n/a')} | "
            f"openapi={getattr(control_result, 'openapi_http', 'n/a')} | "
            f"image={getattr(control_result, 'image_http', 'n/a')}"
        )
        enabled_state = getattr(control_result, "enabled", None)
        if enabled_state is True:
            preview_status = "Технічні роботи увімкнені"
        elif enabled_state is False:
            preview_status = "Технічні роботи вимкнені"
        else:
            preview_status = "Статус технічних робіт не визначено"
        self.maintenance_preview_status.set(preview_status)
        publish_related = bool(getattr(control_result, "local_html_path", None) or getattr(control_result, "remote_html_path", None))
        if action == "publish" or publish_related:
            self._append_product_log(
                f"[Технічні роботи] maintenance.publish: {status_label} | stage={stage} | exit={exit_code_text} | {message_text}"
            )
            self.record_history(
                "maintenance.publish",
                status="ok" if getattr(control_result, "success", False) else "error",
                details=f"stage={stage}; exit={exit_code_text}; {message_text}",
                extra={
                    "stage": stage,
                    "exit_code": exit_code,
                    "message": message_text,
                },
            )
        else:
            self._append_product_log(f"[Технічні роботи] {action}: {status_label}")
        if not getattr(control_result, "success", False):
            messagebox.showwarning("Дію завершено з попередженнями", message_text)

    def open_maintenance_server_control_details(self) -> None:
        result = self._maintenance_server_control_last_result
        if result is None:
            messagebox.showinfo(
                "Немає даних",
                "Спочатку натисни «Оновити статус», «Увімкнути техроботи» або «Вимкнути техроботи».",
            )
            return

        if (
            self._maintenance_server_control_details_window is not None
            and self._maintenance_server_control_details_window.winfo_exists()
        ):
            window = self._maintenance_server_control_details_window
            window.deiconify()
            window.lift()
            window.focus_force()
            return

        window = tk.Toplevel(self)
        window.title("Деталі технічних робіт")
        window.geometry("920x700")
        window.minsize(700, 480)
        window.transient(self)
        window.columnconfigure(0, weight=1)
        window.rowconfigure(1, weight=1)
        self._maintenance_server_control_details_window = window

        header = ttk.Frame(window, style="Root.TFrame", padding=16)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="Деталі технічних робіт", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text="Тут показано лише безпечні дані: stage, код завершення, очищені stdout/stderr та шляхи до файлів.",
            style="Hint.TLabel",
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(6, 0))

        body = ttk.Frame(window, style="Root.TFrame", padding=(16, 0, 16, 16))
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)

        text = tk.Text(
            body,
            wrap="word",
            bg="#fbfaf7",
            fg="#1f2a29",
            relief="flat",
            borderwidth=0,
            padx=12,
            pady=12,
        )
        text.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(body, orient="vertical", command=text.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        text.configure(yscrollcommand=scroll.set)

        def value_or_na(value: object) -> str:
            if value is None:
                return "n/a"
            text_value = str(value).strip()
            return text_value or "n/a"

        lines = [
            f"Action: {value_or_na(getattr(result, 'action', None))}",
            f"Success: {value_or_na(getattr(result, 'success', None))}",
            f"Stage: {value_or_na(getattr(result, 'stage', None))}",
            f"Exit code: {value_or_na(getattr(result, 'exit_code', None))}",
            f"Status label: {value_or_na(getattr(result, 'status_label', None))}",
            f"Message: {value_or_na(getattr(result, 'message', None))}",
            "",
            "Safe stdout:",
            value_or_na(getattr(result, 'safe_stdout', None)),
            "",
            "Safe stderr:",
            value_or_na(getattr(result, 'safe_stderr', None)),
            "",
            f"Local HTML SHA-256: {value_or_na(getattr(result, 'local_html_sha256', None))}",
            f"Local image SHA-256: {value_or_na(getattr(result, 'local_image_sha256', None))}",
            f"Remote HTML SHA-256: {value_or_na(getattr(result, 'remote_html_sha256', None))}",
            f"Remote image SHA-256: {value_or_na(getattr(result, 'remote_image_sha256', None))}",
            f"Local HTML path: {value_or_na(getattr(result, 'local_html_path', None))}",
            f"Local image path: {value_or_na(getattr(result, 'local_image_path', None))}",
            f"Remote HTML path: {value_or_na(getattr(result, 'remote_html_path', None))}",
            f"Remote image path: {value_or_na(getattr(result, 'remote_image_path', None))}",
        ]
        text.insert("1.0", "\n".join(lines))
        text.configure(state="disabled")

    def refresh_maintenance_server_control_status(self) -> None:
        if self._maintenance_server_control_running:
            return

        server_host = self.server_host.get().strip()
        server_port = self.server_port.get().strip() or "22"
        server_user = self.server_user.get().strip()
        ssh_key_path = self.ssh_key_path.get().strip()
        server_password = self.server_password.get().strip()

        if not server_host or not server_user:
            messagebox.showwarning(
                "Дані сервера",
                "Для перевірки статусу потрібні введені адреса сервера і SSH-користувач.",
            )
            return

        sudo_password = self._prompt_sudo_password()
        if sudo_password is None:
            self.maintenance_server_control_status.set("Перевірку скасовано.")
            return

        self._maintenance_server_control_running = True
        self.maintenance_server_control_status.set("Перевіряю статус...")
        self._begin_activity()

        def finish(result: object | None = None, error_text: str | None = None) -> None:
            self._finish_maintenance_server_control(result=result, error_text=error_text)

        def worker() -> None:
            try:
                result = run_maintenance_server_status(
                    server_host,
                    server_port,
                    server_user,
                    ssh_key_path,
                    server_password,
                    sudo_password,
                )
            except Exception as exc:  # pragma: no cover - remote dependent
                self.after(0, lambda: finish(error_text=str(exc)))
                return
            self.after(0, lambda: finish(result=result))

        threading.Thread(target=worker, daemon=True).start()

    def run_maintenance_server_enable(self) -> None:
        if self._maintenance_server_control_running:
            return

        if not messagebox.askyesno(
            "Увімкнути техроботи",
            "Сайт, адмінка та API будуть тимчасово недоступні для користувачів і повернуть сторінку технічних робіт. Продовжити?",
        ):
            return

        server_host = self.server_host.get().strip()
        server_port = self.server_port.get().strip() or "22"
        server_user = self.server_user.get().strip()
        ssh_key_path = self.ssh_key_path.get().strip()
        server_password = self.server_password.get().strip()
        message = self.maintenance_message.get().strip()
        eta = self.maintenance_eta.get().strip()

        if not server_host or not server_user:
            messagebox.showwarning(
                "Дані сервера",
                "Для увімкнення техробіт потрібні введені адреса сервера і SSH-користувач.",
            )
            return

        sudo_password = self._prompt_sudo_password()
        if sudo_password is None:
            self.maintenance_server_control_status.set("Увімкнення скасовано.")
            return

        self._maintenance_server_control_running = True
        self.maintenance_server_control_status.set("Підготовка сторінки і увімкнення...")
        self._begin_activity()

        def finish(result: object | None = None, error_text: str | None = None) -> None:
            self._finish_maintenance_server_control(result=result, error_text=error_text)

        def worker() -> None:
            try:
                result = run_maintenance_server_enable(
                    server_host,
                    server_port,
                    server_user,
                    ssh_key_path,
                    server_password,
                    sudo_password,
                    message,
                    eta,
                )
            except Exception as exc:  # pragma: no cover - remote dependent
                self.after(0, lambda: finish(error_text=str(exc)))
                return
            self.after(0, lambda: finish(result=result))

        threading.Thread(target=worker, daemon=True).start()

    def run_maintenance_server_disable(self) -> None:
        if self._maintenance_server_control_running:
            return

        if not messagebox.askyesno(
            "Вимкнути техроботи",
            "Сайт, адмінка та API знову стануть доступними для користувачів. Продовжити?",
        ):
            return

        server_host = self.server_host.get().strip()
        server_port = self.server_port.get().strip() or "22"
        server_user = self.server_user.get().strip()
        ssh_key_path = self.ssh_key_path.get().strip()
        server_password = self.server_password.get().strip()

        if not server_host or not server_user:
            messagebox.showwarning(
                "Дані сервера",
                "Для вимкнення техробіт потрібні введені адреса сервера і SSH-користувач.",
            )
            return

        sudo_password = self._prompt_sudo_password()
        if sudo_password is None:
            self.maintenance_server_control_status.set("Вимкнення скасовано.")
            return

        self._maintenance_server_control_running = True
        self.maintenance_server_control_status.set("Вимикаю техроботи...")
        self._begin_activity()

        def finish(result: object | None = None, error_text: str | None = None) -> None:
            self._finish_maintenance_server_control(result=result, error_text=error_text)

        def worker() -> None:
            try:
                result = run_maintenance_server_disable(
                    server_host,
                    server_port,
                    server_user,
                    ssh_key_path,
                    server_password,
                    sudo_password,
                )
            except Exception as exc:  # pragma: no cover - remote dependent
                self.after(0, lambda: finish(error_text=str(exc)))
                return
            self.after(0, lambda: finish(result=result))

        threading.Thread(target=worker, daemon=True).start()

    def _prompt_sudo_password(self) -> str | None:
        dialog = tk.Toplevel(self)
        dialog.title("sudo-пароль")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        dialog.columnconfigure(0, weight=1)

        result: dict[str, str | None] = {"value": None}
        password_var = tk.StringVar(value="")

        body = ttk.Frame(dialog, padding=16, style="Root.TFrame")
        body.grid(row=0, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)

        ttk.Label(
            body,
            text="Введи sudo-пароль для одноразової privileged read-only перевірки.",
            style="Hint.TLabel",
            justify="left",
            wraplength=420,
        ).grid(row=0, column=0, sticky="w")
        entry = ttk.Entry(body, textvariable=password_var, show="*")
        entry.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        entry.focus_set()

        buttons = ttk.Frame(body, style="Root.TFrame")
        buttons.grid(row=2, column=0, sticky="e", pady=(16, 0))

        def accept() -> None:
            value = password_var.get()
            if not value:
                messagebox.showwarning("Порожній пароль", "Введи sudo-пароль або натисни Скасувати.")
                return
            result["value"] = value
            dialog.destroy()

        def cancel() -> None:
            result["value"] = None
            password_var.set("")
            dialog.destroy()

        ttk.Button(buttons, text="Скасувати", command=cancel).pack(side="right")
        ttk.Button(buttons, text="Продовжити", style="Primary.TButton", command=accept).pack(side="right", padx=(0, 8))
        dialog.protocol("WM_DELETE_WINDOW", cancel)

        self.wait_window(dialog)
        value = result["value"]
        password_var.set("")
        return value

    def run_maintenance_server_audit(self) -> None:
        if self._maintenance_server_audit_running:
            return

        server_host = self.server_host.get().strip()
        server_port = self.server_port.get().strip() or "22"
        server_user = self.server_user.get().strip()
        ssh_key_path = self.ssh_key_path.get().strip()
        server_password = self.server_password.get().strip()

        if not server_host or not server_user:
            messagebox.showwarning(
                "Дані сервера",
                "Для read-only аудиту потрібні введені адреса сервера і SSH-користувач.",
            )
            return

        self._maintenance_server_audit_running = True
        self.maintenance_server_audit_status.set("Перевіряю сервер...")
        self.maintenance_server_audit_summary.set("Виконую read-only аудит production nginx.")
        self._maintenance_server_audit_report = ""
        self._begin_activity()

        def finish(result: object | None = None, error_text: str | None = None) -> None:
            self._maintenance_server_audit_running = False
            self._end_activity()

            if error_text is not None:
                self.maintenance_server_audit_status.set("Перевірку завершено з помилкою.")
                self.maintenance_server_audit_summary.set(error_text)
                self._maintenance_server_audit_report = f"Server audit\n\n{error_text}\n"
                self._append_product_log(f"[Аудит сервера] {error_text}")
                messagebox.showerror("Не вдалося перевірити сервер", error_text)
                return

            if result is None:
                return

            audit_result = result
            status_text = "Готово" if getattr(audit_result, "success", False) else "Завершено з попередженнями"
            self.maintenance_server_audit_status.set(f"{status_text}: {getattr(audit_result, 'status', 'unknown')}")
            self.maintenance_server_audit_summary.set(
                str(getattr(audit_result, "summary", "")).strip() or "Аудит завершено."
            )
            self._maintenance_server_audit_report = str(getattr(audit_result, "report", "")).strip()
            self._append_product_log(f"[Аудит сервера] {self.maintenance_server_audit_summary.get()}")
            if not getattr(audit_result, "success", False):
                messagebox.showwarning(
                    "Аудит завершено з попередженнями",
                    self.maintenance_server_audit_summary.get(),
                )

        def worker() -> None:
            try:
                result = audit_maintenance_server(
                    server_host,
                    server_port,
                    server_user,
                    ssh_key_path,
                    server_password,
                )
            except Exception as exc:  # pragma: no cover - remote dependent
                self.after(0, lambda: finish(error_text=str(exc)))
                return
                self.after(0, lambda: finish(result=result))

        threading.Thread(target=worker, daemon=True).start()

    def run_maintenance_server_audit_privileged(self) -> None:
        if self._maintenance_server_audit_running:
            return

        server_host = self.server_host.get().strip()
        server_port = self.server_port.get().strip() or "22"
        server_user = self.server_user.get().strip()
        ssh_key_path = self.ssh_key_path.get().strip()
        server_password = self.server_password.get().strip()

        if not server_host or not server_user:
            messagebox.showwarning(
                "Дані сервера",
                "Для privileged read-only аудиту потрібні введені адреса сервера і SSH-користувач.",
            )
            return

        sudo_password = self._prompt_sudo_password()
        if sudo_password is None:
            self.maintenance_server_audit_status.set("Привілейовану перевірку скасовано.")
            self.maintenance_server_audit_summary.set("sudo-пароль не введено.")
            return

        self._maintenance_server_audit_running = True
        self.maintenance_server_audit_status.set("Привілейована перевірка...")
        self.maintenance_server_audit_summary.set("Виконую privileged read-only аудит production nginx.")
        self._maintenance_server_audit_report = ""
        self._begin_activity()
        sudo_secret_box = {"value": sudo_password}

        def finish(result: object | None = None, error_text: str | None = None) -> None:
            self._maintenance_server_audit_running = False
            self._end_activity()

            if error_text is not None:
                self.maintenance_server_audit_status.set("Привілейовану перевірку завершено з помилкою.")
                self.maintenance_server_audit_summary.set(error_text)
                self._maintenance_server_audit_report = f"privileged read-only server audit for production nginx\n\n{error_text}\n"
                self._append_product_log("[Аудит сервера] Privileged read-only audit failed.")
                self.record_history("maintenance.server_audit_privileged", status="error")
                messagebox.showerror("Не вдалося перевірити сервер", error_text)
                sudo_secret_box["value"] = ""
                return

            if result is None:
                sudo_secret_box["value"] = ""
                return

            audit_result = result
            status_text = "Готово" if getattr(audit_result, "success", False) else "Завершено з попередженнями"
            self.maintenance_server_audit_status.set(f"{status_text}: {getattr(audit_result, 'status', 'unknown')}")
            self.maintenance_server_audit_summary.set(
                str(getattr(audit_result, "summary", "")).strip() or "Привілейовану перевірку завершено."
            )
            self._maintenance_server_audit_report = str(getattr(audit_result, "report", "")).strip()
            self._append_product_log(f"[Аудит сервера] {self.maintenance_server_audit_summary.get()}")
            self.record_history(
                "maintenance.server_audit_privileged",
                status="ok" if getattr(audit_result, "success", False) else "error",
            )
            if not getattr(audit_result, "success", False):
                messagebox.showwarning(
                    "Аудит завершено з попередженнями",
                    self.maintenance_server_audit_summary.get(),
                )
            sudo_secret_box["value"] = ""

        def worker() -> None:
            try:
                result = audit_privileged_maintenance_server(
                    server_host,
                    server_port,
                    server_user,
                    ssh_key_path,
                    server_password,
                    sudo_secret_box["value"],
                )
            except Exception as exc:  # pragma: no cover - remote dependent
                self.after(0, lambda: finish(error_text=str(exc)))
                return
            self.after(0, lambda: finish(result=result))

        threading.Thread(target=worker, daemon=True).start()

    def open_maintenance_server_audit_report(self) -> None:
        if not self._maintenance_server_audit_report.strip():
            messagebox.showinfo(
                "Звіт ще не готовий",
                "Спочатку натисни «Перевірити сервер».",
            )
            return

        if self._maintenance_server_audit_window is not None and self._maintenance_server_audit_window.winfo_exists():
            window = self._maintenance_server_audit_window
            window.deiconify()
            window.lift()
            window.focus_force()
            return

        window = tk.Toplevel(self)
        window.title("Звіт read-only аудиту сервера")
        window.geometry("980x760")
        window.minsize(760, 520)
        window.transient(self)
        window.columnconfigure(0, weight=1)
        window.rowconfigure(1, weight=1)
        self._maintenance_server_audit_window = window

        header = ttk.Frame(window, style="Root.TFrame", padding=16)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="Звіт read-only аудиту production nginx", style="Section.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            header,
            text="Детальний звіт показує лише зчитаний стан, без змін на сервері.",
            style="Hint.TLabel",
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(6, 0))

        body = ttk.Frame(window, style="Root.TFrame", padding=(16, 0, 16, 16))
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)

        text = tk.Text(
            body,
            wrap="word",
            bg="#fbfaf7",
            fg="#1f2a29",
            relief="flat",
            borderwidth=0,
            padx=12,
            pady=12,
        )
        text.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(body, orient="vertical", command=text.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        text.configure(yscrollcommand=scroll.set)
        text.insert("1.0", self._maintenance_server_audit_report)
        text.configure(state="disabled")

    def open_launch_log(self) -> None:
        self._open_path(PROJECT_ROOT / "product_center_launch.log")

    def open_launch_error_log(self) -> None:
        self._open_path(PROJECT_ROOT / "product_center_launch_error.log")

    def _update_package_candidates(self) -> list[tuple[str, str]]:
        entries = git_current_status_entries()
        return [
            (status, path)
            for status, path in entries
            if not is_generated_update_package_file(path)
        ]

    def _update_package_file_state(self) -> tuple[dict[str, str], list[str], list[str], list[str]]:
        snapshot = load_update_package_state().get("files", {})
        if not isinstance(snapshot, dict):
            snapshot = {}

        current_files = [path for _, path in self._update_package_candidates()]
        packed_files: list[str] = []
        new_files: list[str] = []
        ready_files: list[str] = []

        for path in current_files:
            current_hash = file_sha256(PROJECT_ROOT / path)
            if snapshot.get(path) == current_hash:
                packed_files.append(path)
            else:
                new_files.append(path)

        if self.update_package_source.get() == "selected":
            selected = [path for path in self.selected_git_paths() if not is_generated_update_package_file(path)]
            ready_files = [path for path in selected if path in new_files]
        else:
            ready_files = list(new_files)

        return snapshot, packed_files, new_files, ready_files

    def _prepare_update_package_payload(
        self,
        source_mode: str,
        selected_paths: list[str] | None = None,
    ) -> dict[str, object]:
        snapshot, packed_files, new_files, ready_files = self._update_package_file_state()
        source_files = ready_files
        if source_mode == "selected":
            selected = [
                path
                for path in (selected_paths or [])
                if not is_generated_update_package_file(path)
            ]
            source_files = [path for path in selected if path in new_files]

        result: dict[str, object] = {
            "packed_count": len(packed_files),
            "new_count": len(new_files),
            "ready_count": len(source_files),
            "source_files": source_files,
        }

        if source_files:
            result["payload"] = build_update_package_payload(source_files)

        return result

    def _update_package_source_files(self) -> list[str]:
        source_mode = self.update_package_source.get()
        selected_paths = self.selected_git_paths() if source_mode == "selected" else []
        result = self._prepare_update_package_payload(source_mode, selected_paths)
        payload = result.get("payload")
        if not isinstance(payload, dict):
            return []
        self._last_update_package_payload = payload
        return list(payload.get("source_files", []))

    def _render_update_package_preview(self, payload: dict[str, object]) -> str:
        lines = [
            f"Версія: {payload['package_version']}",
            f"Створено: {payload['created_at']}",
            f"Гілка: {payload.get('branch') or 'n/a'}",
            f"Коміт: {payload.get('head_commit') or 'n/a'}",
            f"Файлів: {len(payload.get('source_files', []))}",
            "",
            "Файли по групах:",
        ]

        file_groups = payload.get("file_groups", {}) or {}
        for group_name, title in [
            ("code", "Код"),
            ("database", "База"),
            ("ui", "Інтерфейс"),
            ("docs", "Документація"),
            ("other", "Інше"),
        ]:
            files = list(file_groups.get(group_name, []) or [])
            if not files:
                continue
            lines.append(f"- {title}:")
            for item in files:
                lines.append(f"  - {item}")

        lines.extend(["", "План для сервера:"])
        for step in payload.get("server_plan", []) or []:
            lines.append(f"- {step}")

        return "\n".join(lines)

    def refresh_update_package_preview(self) -> None:
        self._begin_activity()
        source_mode = self.update_package_source.get()
        selected_paths = self.selected_git_paths() if source_mode == "selected" else []

        def worker() -> None:
            result = self._prepare_update_package_payload(source_mode, selected_paths)

            def finish() -> None:
                try:
                    self.update_package_snapshot_summary.set(f"Вже упаковано: {result.get('packed_count', 0)}")
                    self.update_package_new_summary.set(f"Нові зміни: {result.get('new_count', 0)}")
                    self.update_package_ready_summary.set(f"Готово до пакета: {result.get('ready_count', 0)}")

                    payload = result.get("payload")
                    if not isinstance(payload, dict):
                        self._last_update_package_payload = None
                        self.update_package_version.set("—")
                        self.update_package_path.set("—")
                        self.update_package_files_summary.set("Немає змінених файлів для пакета.")
                        self.update_package_preview.delete("1.0", "end")
                        self.update_package_preview.insert("1.0", "Ще немає змін, з яких можна зібрати пакет версії.")
                        return

                    self._last_update_package_payload = payload
                    package_version = str(payload["package_version"])
                    package_path = UPDATE_PACKAGES_DIR / f"{package_version}.json"
                    self.update_package_version.set(package_version)
                    self.update_package_path.set(package_path.as_posix())
                    self.update_package_files_summary.set(
                        f"{len(payload.get('source_files', []))} файлів, {len(payload.get('file_types', []))} груп"
                    )
                    self.update_package_preview.delete("1.0", "end")
                    self.update_package_preview.insert("1.0", self._render_update_package_preview(payload))
                finally:
                    self._end_activity()

            self.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def create_update_package(self) -> None:
        source_files = self._update_package_source_files()
        if not source_files:
            messagebox.showwarning("Немає змін", "Спочатку вибери файли у Git або зміни щось у проєкті.")
            return

        self._begin_activity()
        payload = build_update_package_payload(source_files)
        package_version = str(payload["package_version"])
        package_json_path = UPDATE_PACKAGES_DIR / f"{package_version}.json"
        package_md_path = UPDATE_PACKAGES_DIR / f"{package_version}.md"
        UPDATE_PACKAGES_DIR.mkdir(parents=True, exist_ok=True)

        try:
            package_json_path.write_text(render_update_package_json(payload), encoding="utf-8")
            package_md_path.write_text(render_update_package_markdown(payload), encoding="utf-8")
        except OSError as exc:
            self._end_activity()
            messagebox.showerror("Не вдалося зберегти пакет", str(exc))
            return

        save_update_package_state(package_version, list(payload.get("source_files", [])))
        self._last_update_package_payload = payload

        self.update_package_version.set(package_version)
        self.update_package_path.set(package_json_path.as_posix())
        self.update_package_files_summary.set(
            f"{len(payload.get('source_files', []))} файлів, {len(payload.get('file_types', []))} груп"
        )
        self.update_package_preview.delete("1.0", "end")
        self.update_package_preview.insert("1.0", self._render_update_package_preview(payload))
        self.refresh_update_package_preview()
        self._end_activity()
        self.record_history(
            "update.package.create",
            details=f"Створено пакет {package_version}",
            files=list(payload.get("source_files", [])),
            status="ok",
            extra={
                "json_path": package_json_path.as_posix(),
                "md_path": package_md_path.as_posix(),
                "branch": payload.get("branch"),
                "head_commit": payload.get("head_commit"),
            },
        )
        messagebox.showinfo(
            "Пакет створено",
            f"Пакет {package_version} збережено у docs/update_packages.",
        )

    def _service_responds(self, url: str, timeout: float = 1.5) -> bool:
        try:
            with urlopen(url, timeout=timeout) as response:
                return 200 <= getattr(response, "status", 200) < 500
        except URLError:
            return False
        except OSError:
            return False

    def refresh_product_status(self) -> None:
        api_up = self._service_responds(LOCAL_API_HEALTH_URL)
        app_up = self._service_responds(LOCAL_APP_URL)
        admin_up = self._service_responds(LOCAL_ADMIN_URL)

        api_proc = self.managed_processes.get("api")
        bot_proc = self.managed_processes.get("bot")
        bot_running = bot_proc is not None and bot_proc.poll() is None
        bot_status = self._bot_runtime_status(bot_running)

        self._set_service_status("api", self._process_service_status(api_proc, api_up))
        self._set_service_status("app", self._process_service_status(self.managed_processes.get("frontend-app"), app_up))
        self._set_service_status("admin", self._process_service_status(self.managed_processes.get("frontend-admin"), admin_up))
        self._set_service_status("bot", bot_status)
        self._set_action_button_state("api", self._managed_button_state("api", api_proc))
        self._set_action_button_state("frontend-app", self._managed_button_state("frontend-app", self.managed_processes.get("frontend-app")))
        self._set_action_button_state("frontend-admin", self._managed_button_state("frontend-admin", self.managed_processes.get("frontend-admin")))
        self._set_action_button_state("bot", "success" if bot_running else "idle")
        self._set_component_launch_status("api", self._managed_component_status("api", api_proc))
        self._set_component_launch_status("frontend-app", self._managed_component_status("frontend-app", self.managed_processes.get("frontend-app")))
        self._set_component_launch_status("frontend-admin", self._managed_component_status("frontend-admin", self.managed_processes.get("frontend-admin")))
        self._set_component_launch_status("bot", self._managed_component_status("bot", bot_proc))

        if api_proc is not None and api_proc.poll() is not None:
            self._append_product_log(f"[API] завершився з кодом {api_proc.returncode}")
        if bot_proc is not None and bot_proc.poll() is not None:
            self._append_product_log(f"[Bot] завершився з кодом {bot_proc.returncode}")

    def refresh_product_status_async(self) -> None:
        def worker() -> None:
            api_up = self._service_responds(LOCAL_API_HEALTH_URL)
            app_up = self._service_responds(LOCAL_APP_URL)
            admin_up = self._service_responds(LOCAL_ADMIN_URL)

            api_proc = self.managed_processes.get("api")
            bot_proc = self.managed_processes.get("bot")
            bot_running = bot_proc is not None and bot_proc.poll() is None
            bot_status = self._bot_runtime_status(bot_running)

            def finish() -> None:
                self._set_service_status("api", self._process_service_status(api_proc, api_up))
                self._set_service_status("app", self._process_service_status(self.managed_processes.get("frontend-app"), app_up))
                self._set_service_status("admin", self._process_service_status(self.managed_processes.get("frontend-admin"), admin_up))
                self._set_service_status("bot", bot_status)
                self._set_action_button_state("api", self._managed_button_state("api", api_proc))
                self._set_action_button_state("frontend-app", self._managed_button_state("frontend-app", self.managed_processes.get("frontend-app")))
                self._set_action_button_state("frontend-admin", self._managed_button_state("frontend-admin", self.managed_processes.get("frontend-admin")))
                self._set_action_button_state("bot", "success" if bot_running else "idle")
                self._set_component_launch_status("api", self._managed_component_status("api", api_proc))
                self._set_component_launch_status("frontend-app", self._managed_component_status("frontend-app", self.managed_processes.get("frontend-app")))
                self._set_component_launch_status("frontend-admin", self._managed_component_status("frontend-admin", self.managed_processes.get("frontend-admin")))
                self._set_component_launch_status("bot", self._managed_component_status("bot", bot_proc))

                if api_proc is not None and api_proc.poll() is not None:
                    self._append_product_log(f"[API] завершився з кодом {api_proc.returncode}")
                if bot_proc is not None and bot_proc.poll() is not None:
                    self._append_product_log(f"[Bot] завершився з кодом {bot_proc.returncode}")

            self.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def _run_script_async(
        self,
        title: str,
        command: list[str],
        env: dict[str, str] | None = None,
        button_key: str | None = None,
    ) -> None:
        self._append_product_log(f"[{title}] Запуск: {' '.join(command)}")
        self._begin_activity()
        self.record_history(
            "script.run",
            details=title,
            command=command,
            status="queued",
        )

        def worker() -> None:
            merged_env = os.environ.copy()
            if env:
                merged_env.update(env)

            try:
                result = subprocess.run(
                    command,
                    cwd=str(PROJECT_ROOT),
                    env=merged_env,
                    capture_output=True,
                    text=True,
                    check=False,
                    **safe_subprocess_kwargs(),
                )
            except Exception as exc:
                self.after(0, lambda: self._append_product_log(f"[{title}] Помилка запуску: {exc}"))
                if button_key:
                    self.after(0, lambda: self._set_action_button_state(button_key, "error"))
                self.after(
                    0,
                    lambda: self.record_history(
                        "script.run",
                        details=title,
                        command=command,
                        status="error",
                        extra={"error": str(exc)},
                    ),
                )
                self.after(0, self._end_activity)
                return

            combined = "\n".join(
                part.strip()
                for part in (result.stdout, result.stderr)
                if part and part.strip()
            ).strip() or "Немає виводу."

            def finish() -> None:
                self._append_product_log(f"[{title}] Код завершення: {result.returncode}")
                self._append_product_log(combined)
                if result.returncode == 0:
                    messagebox.showinfo("Готово", f"{title} завершено успішно.")
                    if button_key:
                        self._set_action_button_state(button_key, "success")
                else:
                    messagebox.showerror("Помилка", f"{title} завершено з кодом {result.returncode}.")
                    if button_key:
                        self._set_action_button_state(button_key, "error")
                self.record_history(
                    "script.run",
                    details=title,
                    command=command,
                    status="ok" if result.returncode == 0 else "error",
                    extra={
                        "returncode": result.returncode,
                        "stdout": result.stdout.strip(),
                        "stderr": result.stderr.strip(),
                    },
                )
                self._end_activity()

            self.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def _start_managed_process(
        self,
        key: str,
        title: str,
        command: list[str],
        env: dict[str, str] | None = None,
        cwd: Path = PROJECT_ROOT,
    ) -> None:
        existing = self.managed_processes.get(key)
        if existing and existing.poll() is None:
            messagebox.showinfo("Процес вже працює", f"{title} уже запущено.")
            self._set_action_button_state(key, "success")
            self.refresh_managed_processes()
            return

        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)

        try:
            proc = subprocess.Popen(
                command,
                cwd=str(cwd),
                env=merged_env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                **safe_subprocess_kwargs(),
            )
        except Exception as exc:
            messagebox.showerror("Помилка запуску", f"{title}: {exc}")
            self._set_action_button_state(key, "error")
            self.record_history(
                "process.start",
                details=title,
                command=command,
                status="error",
                extra={"cwd": str(cwd), "error": str(exc)},
            )
            return

        self.managed_processes[key] = proc
        self._set_action_button_state(key, "starting")
        self._set_component_launch_status(key, "запускається...")
        self._append_product_log(f"[{title}] Запущено, PID={proc.pid}")
        self.record_history(
            "process.start",
            details=title,
            command=command,
            status="ok",
            extra={"cwd": str(cwd), "pid": proc.pid},
        )
        self.refresh_managed_processes()
        self.refresh_product_status_async()

    def refresh_managed_processes(self) -> None:
        self.process_list.delete(0, "end")
        if not self.managed_processes:
            self.process_list.insert("end", "Немає запущених процесів.")
            if getattr(self, "process_list_colors_enabled", False):
                try:
                    self.process_list.itemconfig(0, background="#ffffff", foreground="#1f2a29")
                except tk.TclError:
                    pass
            for key in list(self.action_buttons):
                self._set_action_button_state(key, "idle")
            return

        stale_keys: list[str] = []
        for key, proc in self.managed_processes.items():
            if proc.poll() is not None:
                stale_keys.append(key)
                status = f"зупинено, код {proc.returncode}"
                self._set_action_button_state(key, "idle")
            else:
                status = f"працює, PID {proc.pid}"
                self._set_action_button_state(key, self._managed_button_state(key, proc))
            self._set_component_launch_status(key, self._managed_component_status(key, proc))
            self.process_list.insert("end", f"{key}: {status}")
            if getattr(self, "process_list_colors_enabled", False):
                row_bg, row_fg = self._process_list_colors(status)
                try:
                    self.process_list.itemconfig(self.process_list.size() - 1, background=row_bg, foreground=row_fg)
                except tk.TclError:
                    pass

        for key in stale_keys:
            self.managed_processes.pop(key, None)

    def selected_process_key(self) -> str | None:

        selection = self.process_list.curselection()
        if not selection:
            return None
        item = self.process_list.get(selection[0])
        if ": " not in item:
            return None
        return item.split(": ", 1)[0]

    def stop_selected_process(self) -> None:
        key = self.selected_process_key()
        if not key:
            messagebox.showwarning("Нічого не вибрано", "Спочатку вибери процес у списку.")
            return

        proc = self.managed_processes.get(key)
        if not proc:
            messagebox.showwarning("Процес не знайдено", "Вибраний процес уже неактивний.")
            self.refresh_managed_processes()
            return

        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except Exception:
                proc.kill()
        self._append_product_log(f"[{key}] Зупинено")
        self.record_history(
            "process.stop",
            details=f"Зупинено процес {key}",
            status="ok",
            extra={"pid": proc.pid},
        )
        self.refresh_managed_processes()

    def restart_selected_process(self) -> None:
        key = self.selected_process_key()
        if not key:
            messagebox.showwarning("Нічого не вибрано", "Спочатку вибери процес у списку.")
            return

        restart_map = {
            "api": self.start_local_api,
            "bot": self.start_local_bot,
            "frontend-app": self.start_app_frontend,
            "frontend-admin": self.start_admin_frontend,
        }
        stop_only = {"api", "bot", "frontend-app", "frontend-admin"}
        if key in stop_only:
            self.stop_selected_process()
            restart = restart_map.get(key)
            if restart:
                self.after(500, restart)
            return

        messagebox.showinfo("Перезапуск", "Для цього процесу перезапуск не налаштовано.")

    def stop_all_processes(self) -> None:
        for key in list(self.managed_processes):
            proc = self.managed_processes.get(key)
            if not proc:
                continue
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except Exception:
                    proc.kill()
            self._append_product_log(f"[{key}] Зупинено")
            self.record_history(
                "process.stop_all",
                details=f"Зупинено процес {key}",
                status="ok",
                extra={"pid": proc.pid},
            )
        self.refresh_managed_processes()

    def _schedule_process_refresh(self) -> None:
        if self.auto_refresh.get():
            self.refresh_managed_processes()
            self.refresh_product_status_async()
        self.after(2500, self._schedule_process_refresh)

    def start_all_local_services(self) -> None:
        self.start_local_api()
        self.start_local_bot()
        self.start_app_frontend()
        self.start_admin_frontend()

    def start_full_local_stack(self) -> None:
        self._append_product_log("[Пакетний запуск] Стартуємо локальний API, бот, app та admin.")
        self._set_launch_status("Запускається весь продукт...")
        self._begin_activity()
        self.record_history(
            "process.start_full_stack",
            details="Запуск всього локального продукту",
            status="ok",
        )
        self._set_action_button_state("start-full-stack", "starting")
        self.start_all_local_services()

        def opener() -> None:
            ready = False
            for _ in range(30):
                api_up = self._service_responds(LOCAL_API_HEALTH_URL)
                app_up = self._service_responds(LOCAL_APP_URL)
                admin_up = self._service_responds(LOCAL_ADMIN_URL)
                api_proc = self.managed_processes.get("api")
                bot_proc = self.managed_processes.get("bot")
                bot_running = bot_proc is not None and bot_proc.poll() is None
                if api_up and app_up and admin_up and api_proc is not None and api_proc.poll() is None and bot_running:
                    ready = True
                    break
                threading.Event().wait(0.5)
            self.after(0, self.open_all_local_pages)
            self.after(0, self.refresh_managed_processes)
            self.after(0, self.refresh_product_status)
            def finish_status() -> None:
                self._set_action_button_state("start-full-stack", "success" if ready else "error")
                self._set_launch_status("Продукт запущено." if ready else "Запуск не завершився повністю.")
                self._end_activity()

            self.after(0, finish_status)

        threading.Thread(target=opener, daemon=True).start()

    def start_local_api(self) -> None:
        existing = self.managed_processes.get("api")
        if existing and existing.poll() is None:
            existing.terminate()
            try:
                existing.wait(timeout=5)
            except Exception:
                existing.kill()
            self.managed_processes.pop("api", None)

        mode_label = "enabled" if self.allow_local_registration_test_mode.get() else "disabled"
        self.record_history(
            "registration.test_mode",
            details=f"Local phone verification test mode: {mode_label}",
            status="ok",
        )
        self._append_product_log(f"Local phone verification test mode: {mode_label}")
        env = {
            "FURNITURE_PLATFORM_DB_PATH": self.main_db.get().strip(),
            "FURNITURE_LEGACY_DB_PATH": self.legacy_db.get().strip(),
            "FURNITURE_ALLOW_LOCAL_PUBLIC_REGISTRATION": "1" if self.allow_local_registration.get() else "0",
            "FURNITURE_REGISTRATION_LOCAL_TEST_MODE": "true" if self.allow_local_registration_test_mode.get() else "false",
        }
        self._start_managed_process(
            "api",
            "Локальний API",
            python_command(str(PROJECT_ROOT / "main_api.py")),
            env=env,
        )

    def start_local_bot(self) -> None:
        env = {
            "FURNITURE_PLATFORM_DB_PATH": self.main_db.get().strip(),
            "FURNITURE_LEGACY_DB_PATH": self.legacy_db.get().strip(),
        }
        self._start_managed_process(
            "bot",
            "Локальний бот",
            python_command(str(PROJECT_ROOT / "main.py")),
            env=env,
        )

    def run_init_database(self) -> None:
        env = {
            "FURNITURE_PLATFORM_DB_PATH": self.main_db.get().strip(),
            "FURNITURE_LEGACY_DB_PATH": self.legacy_db.get().strip(),
        }
        self._run_script_async(
            "Ініціалізація БД",
            python_command(str(PROJECT_ROOT / "scripts" / "safe_update_db.py"), "--no-backup"),
            env=env,
            button_key="db-init",
        )

    def run_safe_update_db(self) -> None:
        env = {
            "FURNITURE_PLATFORM_DB_PATH": self.main_db.get().strip(),
            "FURNITURE_LEGACY_DB_PATH": self.legacy_db.get().strip(),
        }
        self._run_script_async(
            "Безпечне оновлення БД",
            python_command(str(PROJECT_ROOT / "scripts" / "safe_update_db.py")),
            env=env,
            button_key="db-safe-update",
        )

    def run_repair_catalog(self) -> None:
        env = {
            "FURNITURE_PLATFORM_DB_PATH": self.main_db.get().strip(),
            "FURNITURE_LEGACY_DB_PATH": self.legacy_db.get().strip(),
        }
        command = python_command(
            str(PROJECT_ROOT / "scripts" / "repair_catalog_data.py"),
            "--database",
            self.main_db.get().strip(),
            "--city",
            self.catalog_city.get().strip() or "Київ",
        )
        if self.catalog_warm_images.get():
            command.append("--warm-images")
        command.append("--apply")
        self._run_script_async("Repair catalog data", command, env=env, button_key="db-repair-catalog")

    def run_repair_catalog_images(self) -> None:
        should_run = messagebox.askyesno(
            "Підтвердити довантаження",
            "Буде створено резервну копію БД і довантажено лише відсутні картинки матеріалів, крайок та фурнітури. Назви, ціни та видимість каталогу не змінюються. Продовжити?",
        )
        if not should_run:
            return

        env = {
            "FURNITURE_PLATFORM_DB_PATH": self.main_db.get().strip(),
            "FURNITURE_LEGACY_DB_PATH": self.legacy_db.get().strip(),
        }
        command = python_command(
            str(PROJECT_ROOT / "scripts" / "repair_catalog_data.py"),
            "--database",
            self.main_db.get().strip(),
            "--city",
            self.catalog_city.get().strip() or "Київ",
            "--warm-images",
            "--images-only",
            "--apply",
        )
        self._run_script_async(
            "Довантажити картинки каталогу",
            command,
            env=env,
            button_key="db-repair-catalog-images",
        )

    def run_seed_confirmat(self) -> None:
        command = python_command(
            str(PROJECT_ROOT / "scripts" / "seed_confirmat_190106_holes.py"),
            "--database",
            self.main_db.get().strip(),
            "--apply",
        )
        self._run_script_async("Seed confirmat holes", command, button_key="db-seed-confirmat")

    def run_upgrade_fittings_schema(self) -> None:
        command = python_command(
            str(PROJECT_ROOT / "scripts" / "upgrade_fittings_schema.py"),
            "--database",
            self.main_db.get().strip(),
        )
        self._run_script_async("Upgrade fittings schema", command, button_key="db-upgrade-fittings")

    def start_app_frontend(self) -> None:
        self._start_managed_process(
            "frontend-app",
            "Frontend app",
            npm_command("run", "dev"),
            cwd=PROJECT_ROOT / "frontend" / "app",
        )

    def start_admin_frontend(self) -> None:
        self._start_managed_process(
            "frontend-admin",
            "Frontend admin",
            npm_command("run", "dev"),
            cwd=PROJECT_ROOT / "frontend" / "admin",
        )


def main() -> int:
    prepare_tk_runtime()
    app = WizardApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

