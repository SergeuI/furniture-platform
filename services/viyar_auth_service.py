import asyncio
import json
import subprocess
import sys
from pathlib import Path


WORKER_PATH = Path(__file__).with_name("viyar_auth_worker.py")
WORKER_TIMEOUT_SECONDS = 35


def _normalize_viyar_error(raw_error) -> str:
    text = str(raw_error or "").strip()

    if not text:
        return (
            "Viyar authorization failed without a detailed error. "
            "Please verify your Viyar credentials and site availability."
        )

    if "ERR_NETWORK_ACCESS_DENIED" in text:
        return (
            "Network access to Viyar is blocked for this backend process. "
            "Check firewall, proxy, or server network rules."
        )

    if "Executable doesn't exist" in text or "browserType.launch" in text:
        return (
            "Playwright browser is not available. Install Chromium for Playwright "
            "on the backend environment."
        )

    return text


def _login_viyar_and_get_cookie_subprocess(email: str, password: str) -> dict:
    payload = {
        "email": email,
        "password": password,
    }

    try:
        completed = subprocess.run(
            [sys.executable, str(WORKER_PATH)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=WORKER_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": (
                f"Viyar authorization worker timed out after "
                f"{WORKER_TIMEOUT_SECONDS} seconds"
            ),
        }
    except Exception as exc:
        return {
            "success": False,
            "error": _normalize_viyar_error(exc),
        }

    stdout = (completed.stdout or "").strip()
    stderr = (completed.stderr or "").strip()

    if not stdout:
        return {
            "success": False,
            "error": _normalize_viyar_error(
                stderr
                or f"Viyar authorization worker exited with code {completed.returncode}"
            ),
        }

    try:
        result = json.loads(stdout)
    except json.JSONDecodeError:
        return {
            "success": False,
            "error": _normalize_viyar_error(
                stderr or f"Invalid Viyar authorization worker response: {stdout[:400]}"
            ),
        }

    if not isinstance(result, dict):
        return {
            "success": False,
            "error": "Invalid Viyar authorization worker payload",
        }

    if not result.get("success"):
        result["error"] = _normalize_viyar_error(result.get("error"))

    return result


async def login_viyar_and_get_cookie(email: str, password: str) -> dict:
    return await asyncio.to_thread(
        _login_viyar_and_get_cookie_subprocess,
        email,
        password,
    )
