from __future__ import annotations

import traceback
from pathlib import Path

from scripts.db_update_wizard import main


def _write_launch_error(message: str) -> None:
    log_path = Path(__file__).resolve().parent / "product_center_launch_error.log"
    try:
        log_path.write_text(message, encoding="utf-8")
    except OSError:
        pass


def _write_app_error(message: str) -> None:
    log_path = Path(__file__).resolve().parent / "product_center_app.log"
    try:
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(message + "\n")
    except OSError:
        pass


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        error_text = traceback.format_exc()
        _write_launch_error(error_text)
        _write_app_error(error_text)
        raise
