from __future__ import annotations

import dataclasses
import hashlib
import html
import shutil
import shlex
import tempfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from scripts.maintenance_preview import HERO_IMAGE_PATH, load_template
from scripts.maintenance_server_audit import (
    CommandResult,
    _collect_channel_output,
    _open_paramiko_client,
    _run_ssh_command,
    _run_ssh_command_with_input,
)

REMOTE_STAGING_DIR = "/opt/furniture-maintenance"
REMOTE_WEBROOT = "/var/www/furniture-maintenance"
REMOTE_HERO_SRC = "/maintenance/maintenance-hero.png"
PRODUCTION_SITE_URL = "https://mpfc.com.ua"
PRODUCTION_PUBLIC_URL = f"{PRODUCTION_SITE_URL}/"
PRODUCTION_ADMIN_URL = f"{PRODUCTION_SITE_URL}/admin/"
PRODUCTION_OPENAPI_URL = f"{PRODUCTION_SITE_URL}/openapi.json"
PRODUCTION_IMAGE_URL = f"{PRODUCTION_SITE_URL}/maintenance/maintenance-hero.png"
STATUS_COMMAND = "sudo -S -p '' /usr/local/sbin/mpfc-maintenance status"
ENABLE_COMMAND = "sudo -S -p '' /usr/local/sbin/mpfc-maintenance enable"
DISABLE_COMMAND = "sudo -S -p '' /usr/local/sbin/mpfc-maintenance disable"
STATUS_TIMEOUT_SECONDS = 30.0
ENABLE_TIMEOUT_SECONDS = 45.0
DISABLE_TIMEOUT_SECONDS = 45.0
PUBLISH_TIMEOUT_SECONDS = 60.0


@dataclasses.dataclass(slots=True)
class MaintenanceControlResult:
    action: str
    success: bool
    enabled: bool | None
    status_label: str
    stage: str = "unknown"
    exit_code: int | None = None
    safe_stdout: str = ""
    safe_stderr: str = ""
    nginx_status: str = "unknown"
    public_http: int | None = None
    admin_http: int | None = None
    openapi_http: int | None = None
    image_http: int | None = None
    message: str = ""
    raw_output: str = ""
    local_html_sha256: str | None = None
    local_image_sha256: str | None = None
    remote_html_sha256: str | None = None
    remote_image_sha256: str | None = None
    local_html_path: str | None = None
    local_image_path: str | None = None
    remote_html_path: str | None = None
    remote_image_path: str | None = None
    sha256_match: bool | None = None


def _render_server_html(message: str, eta: str) -> str:
    template = load_template()
    replacements = {
        "title": "Технічні роботи — MP Furniture Calculator",
        "hero_src": REMOTE_HERO_SRC,
        "maintenance_message": message,
        "eta": eta,
        "button": "Оновити сторінку",
    }
    for key, value in replacements.items():
        template = template.replace(f"{{{{{key}}}}}", html.escape(value))
    return template


def build_server_package(message: str, eta: str) -> tuple[Path, Path, Path]:
    temp_dir = Path(tempfile.mkdtemp(prefix="mpfc-maintenance-server-"))
    html_path = temp_dir / "index.html"
    image_path = temp_dir / "maintenance-hero.png"
    html_path.write_text(_render_server_html(message, eta), encoding="utf-8")
    shutil.copy2(HERO_IMAGE_PATH, image_path)
    return temp_dir, html_path, image_path


def _parse_status_output(raw_output: str) -> MaintenanceControlResult:
    enabled: bool | None = None
    nginx_status = "unknown"
    public_http: int | None = None
    admin_http: int | None = None
    openapi_http: int | None = None
    image_http: int | None = None
    error_lines: list[str] = []

    for raw_line in raw_output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line == "MAINTENANCE_ENABLED":
            enabled = True
            continue
        if line == "MAINTENANCE_DISABLED":
            enabled = False
            continue
        if line.startswith("NGINX_STATUS="):
            nginx_status = line.split("=", 1)[1].strip() or "unknown"
            continue
        if line.startswith("PUBLIC_HTTP="):
            try:
                public_http = int(line.split("=", 1)[1].strip())
            except ValueError:
                public_http = None
            continue
        if line.startswith("ADMIN_HTTP="):
            try:
                admin_http = int(line.split("=", 1)[1].strip())
            except ValueError:
                admin_http = None
            continue
        if line.startswith("OPENAPI_HTTP="):
            try:
                openapi_http = int(line.split("=", 1)[1].strip())
            except ValueError:
                openapi_http = None
            continue
        if line.startswith("IMAGE_HTTP="):
            try:
                image_http = int(line.split("=", 1)[1].strip())
            except ValueError:
                image_http = None
            continue
        if line.startswith("ERROR:"):
            error_lines.append(line.split(":", 1)[1].strip() or line)

    complete = (
        enabled is not None
        and nginx_status != "unknown"
        and public_http is not None
        and admin_http is not None
        and openapi_http is not None
        and image_http is not None
        and not error_lines
    )
    if not complete:
        missing: list[str] = []
        if enabled is None:
            missing.append("maintenance state")
        if nginx_status == "unknown":
            missing.append("NGINX_STATUS")
        if public_http is None:
            missing.append("PUBLIC_HTTP")
        if admin_http is None:
            missing.append("ADMIN_HTTP")
        if openapi_http is None:
            missing.append("OPENAPI_HTTP")
        if image_http is None:
            missing.append("IMAGE_HTTP")
        message = "Не вдалося визначити статус технічних робіт."
        if error_lines:
            message = error_lines[-1]
        elif missing:
            message = "Відсутні дані: " + ", ".join(missing)
    else:
        message = "Технічні роботи увімкнені." if enabled else "Технічні роботи вимкнені."

    return MaintenanceControlResult(
        action="status",
        success=complete,
        enabled=enabled,
        status_label="enabled" if enabled else "disabled" if enabled is False else "unknown",
        nginx_status=nginx_status,
        public_http=public_http,
        admin_http=admin_http,
        openapi_http=openapi_http,
        image_http=image_http,
        message=message,
        raw_output=raw_output,
    )


def _command_to_result(action: str, result: CommandResult) -> MaintenanceControlResult:
    parsed = _parse_status_output(result.stdout)
    error_text = (result.stderr or "").strip()
    if result.exit_code != 0 and not error_text:
        error_text = result.stdout.strip() or f"Command exited with code {result.exit_code}"
    if error_text and not parsed.success:
        parsed.message = error_text
    parsed.action = action
    parsed.raw_output = result.stdout
    return parsed


def _run_status_command(client, sudo_password: str) -> CommandResult:
    return _run_ssh_command_with_input(client, STATUS_COMMAND, sudo_password, timeout_seconds=STATUS_TIMEOUT_SECONDS)


def _run_enable_command(client, sudo_password: str) -> CommandResult:
    return _run_ssh_command_with_input(client, ENABLE_COMMAND, sudo_password, timeout_seconds=ENABLE_TIMEOUT_SECONDS)


def _run_disable_command(client, sudo_password: str) -> CommandResult:
    return _run_ssh_command_with_input(client, DISABLE_COMMAND, sudo_password, timeout_seconds=DISABLE_TIMEOUT_SECONDS)


def _install_remote_file(client, sudo_password: str, source_path: str, target_path: str) -> CommandResult:
    install_command = f"sudo -S -p '' install -m 0644 {shlex.quote(source_path)} {shlex.quote(target_path)}"
    return _run_ssh_command_with_input(client, install_command, sudo_password, timeout_seconds=PUBLISH_TIMEOUT_SECONDS)


def _verify_remote_file(client, remote_path: str) -> CommandResult:
    return _run_ssh_command(client, f"test -f {shlex.quote(remote_path)} && echo EXISTS || echo MISSING")


def _verify_placeholders_absent(client, sudo_password: str, remote_html_path: str) -> CommandResult:
    command = (
        "sudo -S -p '' grep -nF -e '{{title}}' -e '{{hero_src}}' -e '{{maintenance_message}}' "
        "-e '{{eta}}' -e '{{button}}' "
        f"{shlex.quote(remote_html_path)}"
    )
    return _run_ssh_command_with_input(client, command, sudo_password, timeout_seconds=PUBLISH_TIMEOUT_SECONDS)


def _remote_sha256(client, remote_path: str) -> str | None:
    result = _run_ssh_command(client, f"sha256sum {shlex.quote(remote_path)}", timeout_seconds=PUBLISH_TIMEOUT_SECONDS)
    if result.exit_code != 0 or not result.stdout.strip():
        return None
    return result.stdout.split()[0]


def _sanitize_output(stdout: str, stderr: str) -> tuple[str, str]:
    safe_stdout = "\n".join(line.strip() for line in stdout.splitlines() if line.strip())
    safe_stderr = "\n".join(line.strip() for line in stderr.splitlines() if line.strip())
    return safe_stdout, safe_stderr


def _probe_http_status(url: str, timeout_seconds: float = 5.0) -> int | None:
    try:
        with urlopen(url, timeout=timeout_seconds) as response:
            status = getattr(response, "status", None)
            if status is None:
                status = response.getcode()
            return int(status) if status is not None else None
    except HTTPError as exc:
        return int(exc.code)
    except (URLError, TimeoutError, ValueError, OSError):
        return None


def _probe_public_http_statuses() -> tuple[int | None, int | None, int | None, int | None]:
    return (
        _probe_http_status(PRODUCTION_PUBLIC_URL),
        _probe_http_status(PRODUCTION_ADMIN_URL),
        _probe_http_status(PRODUCTION_OPENAPI_URL),
        _probe_http_status(PRODUCTION_IMAGE_URL),
    )


def _status_from_http_statuses(
    public_http: int | None,
    admin_http: int | None,
    openapi_http: int | None,
    image_http: int | None,
) -> tuple[bool | None, str]:
    if public_http == 200 and admin_http == 200 and openapi_http == 200 and image_http == 200:
        return False, "Технічні роботи вимкнені."
    if public_http == 503 and admin_http == 503 and openapi_http == 503 and image_http == 200:
        return True, "Технічні роботи увімкнені."
    return None, "Неможливо визначити стан технічних робіт."


def _looks_like_checksum_mismatch(result: CommandResult) -> bool:
    combined = "\n".join(part for part in [result.stdout, result.stderr] if part).lower()
    return "checksum differs" in combined


def _publish_failure(
    *,
    stage: str,
    message: str,
    exit_code: int | None = None,
    stdout: str = "",
    stderr: str = "",
    local_html_sha256: str | None = None,
    local_image_sha256: str | None = None,
    remote_html_sha256: str | None = None,
    remote_image_sha256: str | None = None,
    local_html_path: str | None = None,
    local_image_path: str | None = None,
    remote_html_path: str | None = None,
    remote_image_path: str | None = None,
) -> MaintenanceControlResult:
    safe_stdout, safe_stderr = _sanitize_output(stdout, stderr)
    return MaintenanceControlResult(
        action="publish",
        success=False,
        enabled=None,
        status_label="error",
        stage=stage,
        exit_code=exit_code,
        safe_stdout=safe_stdout,
        safe_stderr=safe_stderr,
        nginx_status="unknown",
        public_http=None,
        admin_http=None,
        openapi_http=None,
        image_http=None,
        message=message,
        raw_output="\n".join(part for part in [safe_stdout, safe_stderr] if part),
        local_html_sha256=local_html_sha256,
        local_image_sha256=local_image_sha256,
        remote_html_sha256=remote_html_sha256,
        remote_image_sha256=remote_image_sha256,
        local_html_path=local_html_path,
        local_image_path=local_image_path,
        remote_html_path=remote_html_path,
        remote_image_path=remote_image_path,
        sha256_match=False if remote_html_sha256 is not None or remote_image_sha256 is not None else None,
    )


def publish_maintenance_package(
    client,
    sudo_password: str,
    message: str,
    eta: str,
    *,
    remote_staging_dir: str = REMOTE_STAGING_DIR,
    remote_webroot: str = REMOTE_WEBROOT,
) -> MaintenanceControlResult:
    try:
        temp_dir, html_path, image_path = build_server_package(message, eta)
    except Exception as exc:
        return _publish_failure(
            stage="render",
            message="Не вдалося створити maintenance-сторінку.",
            stderr=str(exc),
        )

    remote_html_path = f"{remote_staging_dir.rstrip('/')}/index.html"
    remote_image_path = f"{remote_staging_dir.rstrip('/')}/maintenance-hero.png"
    remote_html_hash: str | None = None
    remote_image_hash: str | None = None
    try:
        try:
            local_html_hash = hashlib.sha256(html_path.read_bytes()).hexdigest()
            local_image_hash = hashlib.sha256(image_path.read_bytes()).hexdigest()
        except Exception as exc:
            return _publish_failure(
                stage="local_validation",
                message="Не вдалося перевірити локальні файли.",
                stderr=str(exc),
                local_html_path=str(html_path),
                local_image_path=str(image_path),
            )

        try:
            sftp = client.open_sftp()
        except Exception as exc:
            return _publish_failure(
                stage="scp_upload",
                message="Не вдалося завантажити файли через SCP.",
                stderr=str(exc),
                local_html_sha256=local_html_hash,
                local_image_sha256=local_image_hash,
                local_html_path=str(html_path),
                local_image_path=str(image_path),
                remote_html_path=remote_html_path,
                remote_image_path=remote_image_path,
            )

        try:
            try:
                sftp.put(str(html_path), remote_html_path)
                sftp.put(str(image_path), remote_image_path)
            except Exception as exc:
                return _publish_failure(
                    stage="scp_upload",
                    message="Не вдалося завантажити файли через SCP.",
                    stderr=str(exc),
                    local_html_sha256=local_html_hash,
                    local_image_sha256=local_image_hash,
                    local_html_path=str(html_path),
                    local_image_path=str(image_path),
                    remote_html_path=remote_html_path,
                    remote_image_path=remote_image_path,
                )
        finally:
            try:
                sftp.close()
            except Exception:
                pass

        install_html = _install_remote_file(client, sudo_password, remote_html_path, f"{remote_webroot.rstrip('/')}/index.html")
        if install_html.exit_code != 0:
            return _publish_failure(
                stage="sudo_install",
                message="Не вдалося встановити файли у /var/www.",
                exit_code=install_html.exit_code,
                stdout=install_html.stdout,
                stderr=install_html.stderr,
                local_html_sha256=local_html_hash,
                local_image_sha256=local_image_hash,
                local_html_path=str(html_path),
                local_image_path=str(image_path),
                remote_html_path=remote_html_path,
                remote_image_path=remote_image_path,
            )

        install_image = _install_remote_file(client, sudo_password, remote_image_path, f"{remote_webroot.rstrip('/')}/maintenance-hero.png")
        if install_image.exit_code != 0:
            return _publish_failure(
                stage="sudo_install",
                message="Не вдалося встановити файли у /var/www.",
                exit_code=install_image.exit_code,
                stdout=install_image.stdout,
                stderr=install_image.stderr,
                local_html_sha256=local_html_hash,
                local_image_sha256=local_image_hash,
                local_html_path=str(html_path),
                local_image_path=str(image_path),
                remote_html_path=remote_html_path,
                remote_image_path=remote_image_path,
            )

        verify_html = _verify_remote_file(client, f"{remote_webroot.rstrip('/')}/index.html")
        if verify_html.exit_code != 0 or verify_html.stdout.strip() != "EXISTS":
            return _publish_failure(
                stage="remote_validation",
                message="Не вдалося підтвердити розміщення файлів.",
                exit_code=verify_html.exit_code,
                stdout=verify_html.stdout,
                stderr=verify_html.stderr,
                local_html_sha256=local_html_hash,
                local_image_sha256=local_image_hash,
                local_html_path=str(html_path),
                local_image_path=str(image_path),
                remote_html_path=remote_html_path,
                remote_image_path=remote_image_path,
            )

        verify_image = _verify_remote_file(client, f"{remote_webroot.rstrip('/')}/maintenance-hero.png")
        if verify_image.exit_code != 0 or verify_image.stdout.strip() != "EXISTS":
            return _publish_failure(
                stage="remote_validation",
                message="Не вдалося підтвердити розміщення файлів.",
                exit_code=verify_image.exit_code,
                stdout=verify_image.stdout,
                stderr=verify_image.stderr,
                local_html_sha256=local_html_hash,
                local_image_sha256=local_image_hash,
                local_html_path=str(html_path),
                local_image_path=str(image_path),
                remote_html_path=remote_html_path,
                remote_image_path=remote_image_path,
            )

        placeholders = _verify_placeholders_absent(client, sudo_password, f"{remote_webroot.rstrip('/')}/index.html")
        if placeholders.exit_code == 0:
            return _publish_failure(
                stage="remote_validation",
                message="На сервері залишилися placeholders.",
                exit_code=placeholders.exit_code,
                stdout=placeholders.stdout,
                stderr=placeholders.stderr,
                local_html_sha256=local_html_hash,
                local_image_sha256=local_image_hash,
                local_html_path=str(html_path),
                local_image_path=str(image_path),
                remote_html_path=remote_html_path,
                remote_image_path=remote_image_path,
            )

        if placeholders.exit_code >= 2:
            return _publish_failure(
                stage="remote_validation",
                message="РќРµ РІРґР°Р»РѕСЃСЏ РїРµСЂРµРІС–СЂРёС‚Рё СЃРµСЂРІРµСЂРЅРёР№ HTML РЅР° placeholders.",
                exit_code=placeholders.exit_code,
                stdout=placeholders.stdout,
                stderr=placeholders.stderr,
                local_html_sha256=local_html_hash,
                local_image_sha256=local_image_hash,
                local_html_path=str(html_path),
                local_image_path=str(image_path),
                remote_html_path=remote_html_path,
                remote_image_path=remote_image_path,
            )

        remote_html_hash = _remote_sha256(client, f"{remote_webroot.rstrip('/')}/index.html")
        remote_image_hash = _remote_sha256(client, f"{remote_webroot.rstrip('/')}/maintenance-hero.png")
        if remote_html_hash != local_html_hash or remote_image_hash != local_image_hash:
            return _publish_failure(
                stage="sha256_validation",
                message="Контрольні суми локального та серверного файла не збігаються.",
                local_html_sha256=local_html_hash,
                local_image_sha256=local_image_hash,
                remote_html_sha256=remote_html_hash,
                remote_image_sha256=remote_image_hash,
                local_html_path=str(html_path),
                local_image_path=str(image_path),
                remote_html_path=remote_html_path,
                remote_image_path=remote_image_path,
            )

        safe_stdout, safe_stderr = _sanitize_output(
            "\n".join(
                part
                for part in [
                    install_html.stdout,
                    install_image.stdout,
                    verify_html.stdout,
                    verify_image.stdout,
                    placeholders.stdout,
                    remote_html_hash or "",
                    remote_image_hash or "",
                ]
                if part
            ),
            "\n".join(
                part
                for part in [
                    install_html.stderr,
                    install_image.stderr,
                    verify_html.stderr,
                    verify_image.stderr,
                    placeholders.stderr,
                ]
                if part
            ),
        )
        return MaintenanceControlResult(
            action="publish",
            success=True,
            enabled=None,
            status_label="published",
            stage="cleanup",
            exit_code=0,
            safe_stdout=safe_stdout,
            safe_stderr=safe_stderr,
            nginx_status="unknown",
            public_http=None,
            admin_http=None,
            openapi_http=None,
            image_http=None,
            message="Сторінку технічних робіт підготовлено.",
            raw_output="\n".join(part for part in [safe_stdout, safe_stderr] if part),
            local_html_sha256=local_html_hash,
            local_image_sha256=local_image_hash,
            remote_html_sha256=remote_html_hash,
            remote_image_sha256=remote_image_hash,
            local_html_path=str(html_path),
            local_image_path=str(image_path),
            remote_html_path=f"{remote_webroot.rstrip('/')}/index.html",
            remote_image_path=f"{remote_webroot.rstrip('/')}/maintenance-hero.png",
            sha256_match=True,
        )
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def run_status(
    server_host: str,
    server_port: str,
    server_user: str,
    ssh_key_path: str,
    server_password: str,
    sudo_password: str,
) -> MaintenanceControlResult:
    client = None
    try:
        client, error = _open_paramiko_client(server_host, server_port, server_user, ssh_key_path, server_password)
        if client is None:
            return MaintenanceControlResult(
                action="status",
                success=False,
                enabled=None,
                status_label="error",
                nginx_status="unknown",
                public_http=None,
                admin_http=None,
                openapi_http=None,
                image_http=None,
                message=error or "Не вдалося перевірити статус технічних робіт.",
                raw_output="",
            )
        result = _run_status_command(client, sudo_password)
        parsed_status = _command_to_result("status", result)
        if parsed_status.success or not _looks_like_checksum_mismatch(result):
            return parsed_status

        nginx_result = _run_ssh_command(client, "systemctl is-active nginx", timeout_seconds=STATUS_TIMEOUT_SECONDS)
        public_http, admin_http, openapi_http, image_http = _probe_public_http_statuses()
        enabled_state, fallback_message = _status_from_http_statuses(public_http, admin_http, openapi_http, image_http)
        if enabled_state is None:
            parsed_status.stage = "checksum_validation"
            parsed_status.message = fallback_message
            parsed_status.safe_stdout = parsed_status.safe_stdout or result.stdout.strip()
            parsed_status.safe_stderr = parsed_status.safe_stderr or result.stderr.strip()
            parsed_status.nginx_status = nginx_result.stdout.strip() or parsed_status.nginx_status
            return parsed_status

        fallback_stdout = "\n".join(
            part
            for part in [
                result.stdout.strip(),
                nginx_result.stdout.strip(),
                f"PUBLIC_HTTP={public_http}" if public_http is not None else "",
                f"ADMIN_HTTP={admin_http}" if admin_http is not None else "",
                f"OPENAPI_HTTP={openapi_http}" if openapi_http is not None else "",
                f"IMAGE_HTTP={image_http}" if image_http is not None else "",
            ]
            if part
        ).strip()
        fallback_stderr = "\n".join(part for part in [result.stderr.strip(), nginx_result.stderr.strip()] if part).strip()
        safe_stdout, safe_stderr = _sanitize_output(fallback_stdout, fallback_stderr)
        return MaintenanceControlResult(
            action="status",
            success=True,
            enabled=enabled_state,
            status_label="enabled" if enabled_state else "disabled",
            stage="checksum_validation",
            exit_code=0,
            safe_stdout=safe_stdout,
            safe_stderr=safe_stderr,
            nginx_status=nginx_result.stdout.strip() or "unknown",
            public_http=public_http,
            admin_http=admin_http,
            openapi_http=openapi_http,
            image_http=image_http,
            message=fallback_message,
            raw_output=fallback_stdout,
        )
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass


def run_enable(
    server_host: str,
    server_port: str,
    server_user: str,
    ssh_key_path: str,
    server_password: str,
    sudo_password: str,
    message: str,
    eta: str,
) -> MaintenanceControlResult:
    client = None
    try:
        client, error = _open_paramiko_client(server_host, server_port, server_user, ssh_key_path, server_password)
        if client is None:
            return MaintenanceControlResult(
                action="enable",
                success=False,
                enabled=None,
                status_label="error",
                nginx_status="unknown",
                public_http=None,
                admin_http=None,
                openapi_http=None,
                image_http=None,
                message=error or "Не вдалося увімкнути технічні роботи.",
                raw_output="",
            )
        publish_result = publish_maintenance_package(client, sudo_password, message, eta)
        if not publish_result.success:
            return publish_result
        enable_result = _run_enable_command(client, sudo_password)
        status_result = _run_status_command(client, sudo_password)
        parsed_status = _command_to_result("status", status_result)
        parsed_status.action = "enable"
        parsed_status.raw_output = "\n".join(part for part in [enable_result.stdout, enable_result.stderr, status_result.stdout] if part).strip()
        parsed_status.success = enable_result.exit_code == 0 and status_result.exit_code == 0 and parsed_status.success
        parsed_status.message = "MAINTENANCE_ENABLE_OK" if parsed_status.success else (enable_result.stderr.strip() or enable_result.stdout.strip() or parsed_status.message)
        parsed_status.status_label = "enabled" if parsed_status.enabled else parsed_status.status_label
        parsed_status.stage = publish_result.stage
        parsed_status.exit_code = publish_result.exit_code
        parsed_status.safe_stdout = publish_result.safe_stdout
        parsed_status.safe_stderr = publish_result.safe_stderr
        parsed_status.local_html_sha256 = publish_result.local_html_sha256
        parsed_status.local_image_sha256 = publish_result.local_image_sha256
        parsed_status.remote_html_sha256 = publish_result.remote_html_sha256
        parsed_status.remote_image_sha256 = publish_result.remote_image_sha256
        parsed_status.local_html_path = publish_result.local_html_path
        parsed_status.local_image_path = publish_result.local_image_path
        parsed_status.remote_html_path = publish_result.remote_html_path
        parsed_status.remote_image_path = publish_result.remote_image_path
        parsed_status.sha256_match = publish_result.sha256_match
        return parsed_status
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass


def run_disable(
    server_host: str,
    server_port: str,
    server_user: str,
    ssh_key_path: str,
    server_password: str,
    sudo_password: str,
) -> MaintenanceControlResult:
    client = None
    try:
        client, error = _open_paramiko_client(server_host, server_port, server_user, ssh_key_path, server_password)
        if client is None:
            return MaintenanceControlResult(
                action="disable",
                success=False,
                enabled=None,
                status_label="error",
                nginx_status="unknown",
                public_http=None,
                admin_http=None,
                openapi_http=None,
                image_http=None,
                message=error or "Не вдалося вимкнути технічні роботи.",
                raw_output="",
            )
        disable_result = _run_disable_command(client, sudo_password)
        status_result = _run_status_command(client, sudo_password)
        parsed_status = _command_to_result("status", status_result)
        parsed_status.action = "disable"
        parsed_status.raw_output = "\n".join(part for part in [disable_result.stdout, disable_result.stderr, status_result.stdout] if part).strip()
        parsed_status.success = disable_result.exit_code == 0 and status_result.exit_code == 0 and parsed_status.success
        parsed_status.message = "MAINTENANCE_DISABLE_OK" if parsed_status.success else (disable_result.stderr.strip() or disable_result.stdout.strip() or parsed_status.message)
        parsed_status.status_label = "disabled" if parsed_status.enabled is False else parsed_status.status_label
        return parsed_status
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass
