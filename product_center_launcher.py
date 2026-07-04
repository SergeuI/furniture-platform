from __future__ import annotations

import os
import shutil
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


def _candidate_pythons(root: Path) -> list[Path]:
    system_base = Path(sys.base_prefix)
    candidates = [
        system_base / "pythonw.exe",
        system_base / "python.exe",
        root / ".venv" / "Scripts" / "pythonw.exe",
        root / ".venv" / "Scripts" / "python.exe",
        Path(shutil.which("pythonw.exe") or ""),
        Path(shutil.which("python.exe") or ""),
    ]
    return [candidate for candidate in candidates if candidate and candidate.exists()]


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

    python_command = next((candidate for candidate in _candidate_pythons(root)), None)
    if python_command is None:
        message = "Не знайдено придатний Python/pyw для запуску програми."
        _write_launch_error(message)
        _append_launch_log(f"error {message}")
        return 1

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
