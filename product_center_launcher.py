from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import traceback
from datetime import datetime
from pathlib import Path


CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _repo_python(root: Path) -> Path:
    candidate = root / ".venv" / "Scripts" / "python.exe"
    if candidate.exists():
        return candidate
    raise FileNotFoundError(f"Missing canonical repo Python: {candidate}")


def _tk_env(root: Path) -> dict[str, str]:
    base = root / "runtime" / "tcl"
    tcl_dir = base / "tcl8.6"
    tk_dir = base / "tk8.6"
    env: dict[str, str] = {}
    if tcl_dir.exists():
        env["TCL_LIBRARY"] = str(tcl_dir)
    if tk_dir.exists():
        env["TK_LIBRARY"] = str(tk_dir)
    return env


def _is_windows_admin() -> bool:
    if os.name != "nt":
        return True
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _shell_runas(file_path: Path, parameters: str, directory: Path) -> int:
    if os.name != "nt":
        return 0
    try:
        return int(
            ctypes.windll.shell32.ShellExecuteW(
                None,
                "runas",
                str(file_path),
                parameters,
                str(directory),
                1,
            )
        )
    except Exception:
        return 0


def _append_launch_log(message: str) -> None:
    log_path = project_root() / "product_center_launch.log"
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}\n"
    try:
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(line)
    except OSError:
        pass


def _write_launch_error(message: str) -> None:
    log_path = project_root() / "product_center_launch_error.log"
    try:
        log_path.write_text(message, encoding="utf-8")
    except OSError:
        pass


def launch() -> int:
    root = project_root()
    script = root / "product_center.pyw"
    _append_launch_log(f"start root={root} script={script}")

    if not script.exists():
        message = f"Не знайдено файл запуску: {script}"
        _write_launch_error(message)
        _append_launch_log(f"error {message}")
        return 1

    try:
        python_command = _repo_python(root)
    except FileNotFoundError as exc:
        message = str(exc)
        _write_launch_error(message)
        _append_launch_log(f"error {message}")
        return 1

    if not _is_windows_admin():
        env = os.environ.copy()
        env.update(_tk_env(root))
        _append_launch_log("not elevated, relaunching product_center.pyw as administrator")
        result = _shell_runas(python_command, f'"{script}"', root)
        if result <= 32:
            message = f"Не вдалося запустити Product Center з правами адміністратора (ShellExecute={result})."
            _write_launch_error(message)
            _append_launch_log(f"error {message}")
            return 1
        return 0

    try:
        env = os.environ.copy()
        env.update(_tk_env(root))
        _append_launch_log(
            f"python={python_command} tcl={env.get('TCL_LIBRARY', '')} tk={env.get('TK_LIBRARY', '')}"
        )
        subprocess.Popen(
            [str(python_command), str(script)],
            cwd=str(root),
            env=env,
            creationflags=CREATE_NO_WINDOW,
        )
        _append_launch_log("launched product_center.pyw")
    except Exception:
        error_text = traceback.format_exc()
        _write_launch_error(error_text)
        _append_launch_log("error " + error_text.replace("\n", " | "))
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(launch())
