from __future__ import annotations

import html
import re
import secrets
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OWNER_TEMPLATE_DIR = PROJECT_ROOT / "resources" / "maintenance"
OWNER_SERVER_TEMPLATE_DIR = OWNER_TEMPLATE_DIR / "server"

OWNER_SITE_URL = "https://mpfc.com.ua"
OWNER_LOGIN_URL = f"{OWNER_SITE_URL}/__maintenance_owner/login"
OWNER_LOGOUT_URL = f"{OWNER_SITE_URL}/__maintenance_owner/logout"
OWNER_COOKIE_NAME = "mpfc_maintenance_owner"
OWNER_LOGIN_USERNAME = "mpfc-owner"
OWNER_COOKIE_MAX_AGE_SECONDS = 7200
OWNER_AUTH_REALM = "MP Furniture Owner Access"

OWNER_ACCESS_TEMPLATE_PATH = OWNER_TEMPLATE_DIR / "owner-access.html"
OWNER_LOGOUT_TEMPLATE_PATH = OWNER_TEMPLATE_DIR / "owner-logout.html"
OWNER_NGINX_MAP_TEMPLATE_PATH = OWNER_SERVER_TEMPLATE_DIR / "nginx-owner-map.conf.template"
OWNER_NGINX_LOADER_TEMPLATE_PATH = OWNER_SERVER_TEMPLATE_DIR / "nginx-owner-loader.conf.template"
OWNER_NGINX_LOCATIONS_TEMPLATE_PATH = OWNER_SERVER_TEMPLATE_DIR / "nginx-owner-locations.conf.template"
OWNER_MAINTENANCE_FLAG_PATH = "/opt/furniture-maintenance/maintenance.flag"
OWNER_SITE_INCLUDE_LINE = "include /etc/nginx/secure/mpfc-maintenance-owner-locations.conf;"
OWNER_GATE_VARIABLE = "$mpfc_maintenance_gate_file"


def _load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _render_text(template: str, replacements: dict[str, str], *, escape_html: bool = True) -> str:
    rendered = template
    for key, value in replacements.items():
        replacement = html.escape(value) if escape_html else value
        rendered = rendered.replace(f"{{{{{key}}}}}", replacement)
    return rendered


def _escape_nginx_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _escape_nginx_regex_token(value: str) -> str:
    return re.escape(value)


def generate_owner_cookie_token(length_bytes: int = 24) -> str:
    return secrets.token_urlsafe(length_bytes)


def render_owner_access_html(
    *,
    site_url: str = OWNER_SITE_URL,
    login_url: str = OWNER_LOGIN_URL,
    logout_url: str = OWNER_LOGOUT_URL,
) -> str:
    template = _load_text(OWNER_ACCESS_TEMPLATE_PATH)
    return _render_text(
        template,
        {
            "site_url": site_url,
            "login_url": login_url,
            "logout_url": logout_url,
            "brand": "MP Furniture Calculator",
        },
    )


def render_owner_logout_html(
    *,
    site_url: str = OWNER_SITE_URL,
    login_url: str = OWNER_LOGIN_URL,
) -> str:
    template = _load_text(OWNER_LOGOUT_TEMPLATE_PATH)
    return _render_text(
        template,
        {
            "site_url": site_url,
            "login_url": login_url,
            "brand": "MP Furniture Calculator",
        },
    )


def render_owner_nginx_map(
    owner_cookie_token: str,
    *,
    owner_cookie_name: str = OWNER_COOKIE_NAME,
    owner_login_username: str = OWNER_LOGIN_USERNAME,
    owner_cookie_max_age_seconds: int = OWNER_COOKIE_MAX_AGE_SECONDS,
) -> str:
    template = _load_text(OWNER_NGINX_MAP_TEMPLATE_PATH)
    return _render_text(
        template,
        {
            "owner_cookie_name": owner_cookie_name,
            "owner_cookie_token": _escape_nginx_regex_token(owner_cookie_token),
            "owner_login_username": _escape_nginx_value(owner_login_username),
            "owner_cookie_max_age": str(owner_cookie_max_age_seconds),
        },
        escape_html=False,
    )


def render_owner_nginx_loader() -> str:
    return _load_text(OWNER_NGINX_LOADER_TEMPLATE_PATH)


def render_owner_nginx_locations(
    owner_cookie_token: str,
    *,
    owner_cookie_name: str = OWNER_COOKIE_NAME,
    owner_cookie_max_age_seconds: int = OWNER_COOKIE_MAX_AGE_SECONDS,
    owner_site_url: str = OWNER_SITE_URL,
    owner_login_path: str = "/__maintenance_owner/login",
    owner_logout_path: str = "/__maintenance_owner/logout",
    owner_auth_realm: str = OWNER_AUTH_REALM,
) -> str:
    template = _load_text(OWNER_NGINX_LOCATIONS_TEMPLATE_PATH)
    return _render_text(
        template,
        {
            "owner_cookie_name": owner_cookie_name,
            "owner_cookie_token": _escape_nginx_value(owner_cookie_token),
            "owner_cookie_max_age": str(owner_cookie_max_age_seconds),
            "owner_site_url": owner_site_url,
            "owner_login_path": owner_login_path,
            "owner_logout_path": owner_logout_path,
            "owner_auth_realm": owner_auth_realm,
        },
        escape_html=False,
    )


def apply_owner_bypass_to_site_config(current_config: str) -> str:
    exact_check = f"if (-f {OWNER_MAINTENANCE_FLAG_PATH})"
    transformed_check = f"if (-f {OWNER_GATE_VARIABLE})"
    exact_matches = current_config.count(exact_check)
    gate_file_matches = current_config.count(OWNER_GATE_VARIABLE)
    include_matches = current_config.count(OWNER_SITE_INCLUDE_LINE)

    if exact_matches == 0 and gate_file_matches >= 1 and include_matches == 1:
        return current_config

    if exact_matches != 4:
        raise ValueError("Expected exactly four maintenance flag checks in the site config.")

    if include_matches > 1:
        raise ValueError("Expected at most one owner bypass include in the site config.")

    transformed = current_config.replace(exact_check, transformed_check)
    if OWNER_SITE_INCLUDE_LINE in transformed:
        if transformed.count(OWNER_SITE_INCLUDE_LINE) != 1:
            raise ValueError("Expected exactly one owner bypass include in the site config.")
        return transformed

    lines = transformed.splitlines()
    server_blocks: list[tuple[int, int]] = []
    index = 0
    while index < len(lines):
        stripped = lines[index].strip()
        if not re.match(r"^server\s*\{", stripped):
            index += 1
            continue

        server_start = index
        depth = lines[index].count("{") - lines[index].count("}")
        index += 1
        while index < len(lines) and depth > 0:
            depth += lines[index].count("{") - lines[index].count("}")
            index += 1

        if depth != 0:
            raise ValueError("Could not find a balanced server block in the site config.")

        server_blocks.append((server_start, index))

    if not server_blocks:
        raise ValueError("Could not find a server block in the site config.")

    https_block_range: tuple[int, int] | None = None
    for server_start, server_end in server_blocks:
        block = lines[server_start:server_end]
        if any("listen 443" in line and "ssl" in line for line in block):
            https_block_range = (server_start, server_end)
            break

    if https_block_range is None:
        raise ValueError("Could not find HTTPS server block for owner bypass include.")

    server_start, server_end = https_block_range
    https_block = lines[server_start:server_end]
    if any(OWNER_SITE_INCLUDE_LINE in line for line in https_block):
        return "\n".join(lines)

    insert_at = None
    for offset, line in enumerate(https_block):
        if line.strip().startswith("location "):
            insert_at = server_start + offset
            break

    if insert_at is None:
        raise ValueError("Could not find insertion point for owner bypass include.")

    lines.insert(insert_at, f"    {OWNER_SITE_INCLUDE_LINE}")
    return "\n".join(lines)


def build_owner_bypass_preview(
    owner_cookie_token: str | None = None,
    output_dir: str | Path | None = None,
) -> dict[str, Path]:
    token = owner_cookie_token or generate_owner_cookie_token()
    target_dir = Path(output_dir) if output_dir is not None else Path(tempfile.mkdtemp(prefix="mpfc-owner-bypass-"))
    target_dir.mkdir(parents=True, exist_ok=True)

    outputs = {
        "owner-access.html": render_owner_access_html(),
        "owner-logout.html": render_owner_logout_html(),
        "nginx-owner-map.conf": render_owner_nginx_map(token),
        "nginx-owner-loader.conf": render_owner_nginx_loader(),
        "nginx-owner-locations.conf": render_owner_nginx_locations(token),
    }
    written: dict[str, Path] = {}
    for filename, content in outputs.items():
        path = target_dir / filename
        path.write_text(content, encoding="utf-8")
        written[filename] = path
    return written
