from __future__ import annotations

import argparse
import base64
import html
import tempfile
import uuid
import webbrowser
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = PROJECT_ROOT / "resources" / "maintenance" / "maintenance.html"
HERO_IMAGE_PATH = PROJECT_ROOT / "resources" / "maintenance" / "maintenance-hero.png"

DEFAULT_MESSAGE = "Ваші проєкти та дані збережені."
DEFAULT_ETA = "Найближчим часом"


def load_template() -> str:
    return TEMPLATE_PATH.read_text(encoding="utf-8")


def load_hero_data_uri() -> str:
    hero_bytes = HERO_IMAGE_PATH.read_bytes()
    encoded = base64.b64encode(hero_bytes).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def render_maintenance_preview_html(message: str = DEFAULT_MESSAGE, eta: str = DEFAULT_ETA) -> str:
    template = load_template()
    replacements = {
        "title": "Ведуться технічні роботи",
        "hero_src": load_hero_data_uri(),
        "maintenance_message": message,
        "eta": eta,
        "button": "Оновити сторінку",
    }
    for key, value in replacements.items():
        template = template.replace(f"{{{{{key}}}}}", html.escape(value))
    return template


def create_preview_file(
    message: str = DEFAULT_MESSAGE,
    eta: str = DEFAULT_ETA,
    output_path: str | Path | None = None,
    *,
    open_in_browser: bool = False,
) -> Path:
    target = Path(output_path) if output_path is not None else Path(tempfile.gettempdir()) / f"mpfc-maintenance-preview-{uuid.uuid4().hex}.html"
    target.write_text(render_maintenance_preview_html(message=message, eta=eta), encoding="utf-8")
    if open_in_browser:
        webbrowser.open(target.as_uri())
    return target


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create a local maintenance preview page.")
    parser.add_argument("--message", default=DEFAULT_MESSAGE, help="Message shown to users.")
    parser.add_argument("--eta", default=DEFAULT_ETA, help="Estimated completion time.")
    parser.add_argument("--output", default="", help="Optional output file path.")
    parser.add_argument("--no-open", action="store_true", help="Do not open the preview in a browser.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    preview_path = create_preview_file(
        message=args.message,
        eta=args.eta,
        output_path=args.output or None,
        open_in_browser=not args.no_open,
    )
    print(preview_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
