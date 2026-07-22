from __future__ import annotations

import dataclasses
import re
import shlex
import tempfile
import time
from pathlib import Path
from typing import Callable

try:
    import paramiko
except Exception:  # pragma: no cover - optional dependency
    paramiko = None


DEFAULT_CHECK_PATHS = (
    "/opt/furniture-maintenance",
    "/var/www/furniture-maintenance",
)

PRIVILEGED_NGINX_COMMAND = "sudo -S -p '' /usr/sbin/nginx -T 2>&1"
NGINX_SERVER_NAME_TARGETS = ("mpfc.com.ua", "www.mpfc.com.ua", "45.94.157.42")
NGINX_ROUTE_TARGETS = (
    "/",
    "/admin/",
    "/api/",
    "/api/docs",
    "/docs",
    "/openapi.json",
    "/.well-known/acme-challenge/",
)


@dataclasses.dataclass(slots=True)
class CommandResult:
    command: str
    exit_code: int
    stdout: str
    stderr: str


@dataclasses.dataclass(slots=True)
class AuditResult:
    success: bool
    status: str
    summary: str
    report: str
    server_names: list[str]
    listen_lines: list[str]
    location_lines: list[str]
    maintenance_lines: list[str]
    listening_ports: list[str]
    path_results: list[tuple[str, bool, bool | None]]
    command_results: list[CommandResult]


@dataclasses.dataclass(slots=True)
class NginxConfigSection:
    path: str
    lines: list[str]


@dataclasses.dataclass(slots=True)
class NginxServerBlock:
    path: str
    lines: list[str]


def _open_paramiko_client(
    server_host: str,
    server_port: str,
    server_user: str,
    ssh_key_path: str,
    server_password: str,
):
    if paramiko is None:
        return None, "Для SSH-аудиту потрібна бібліотека paramiko."

    key_path = ssh_key_path.strip()
    password = server_password.strip()
    if not key_path and not password:
        return None, "Потрібен або SSH key, або SSH password для підключення до сервера."

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
    except Exception as exc:  # pragma: no cover - remote dependent
        return None, str(exc)


def _collect_channel_output(channel, timeout_seconds: float = 120.0) -> tuple[str, str, int]:
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
            raise TimeoutError(f"Audit command exceeded {int(timeout_seconds)} seconds.")
        time.sleep(0.1)

    exit_status = channel.recv_exit_status()
    while channel.recv_ready():
        stdout_chunks.append(channel.recv(4096).decode("utf-8", errors="replace"))
    while channel.recv_stderr_ready():
        stderr_chunks.append(channel.recv_stderr(4096).decode("utf-8", errors="replace"))
    return "".join(stdout_chunks).strip(), "".join(stderr_chunks).strip(), exit_status


def _run_ssh_command(client, command: str, timeout_seconds: float = 120.0) -> CommandResult:
    stdin, stdout, stderr = client.exec_command(command, timeout=timeout_seconds)
    stdout_text, stderr_text, exit_status = _collect_channel_output(stdout.channel, timeout_seconds=timeout_seconds)
    stderr_extra = stderr.read().decode("utf-8", errors="replace").strip()
    if stderr_extra and stderr_text:
        stderr_text = "\n".join(part for part in [stderr_text, stderr_extra] if part)
    elif stderr_extra:
        stderr_text = stderr_extra
    return CommandResult(command=command, exit_code=exit_status, stdout=stdout_text, stderr=stderr_text)


def _extract_lines(pattern: str, text: str) -> list[str]:
    regex = re.compile(pattern, re.IGNORECASE)
    lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if regex.search(line):
            lines.append(line)
    return _unique_lines(lines)


def _unique_lines(lines: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for line in lines:
        if line in seen:
            continue
        seen.add(line)
        ordered.append(line)
    return ordered


def _extract_server_names(config_text: str) -> list[str]:
    names: list[str] = []
    for line in config_text.splitlines():
        stripped = line.strip()
        match = re.search(r"server_name\s+([^;]+);", stripped)
        if match:
            names.extend(part.strip() for part in match.group(1).split() if part.strip())
    return _unique_lines(names)


def _extract_listen_lines(config_text: str) -> list[str]:
    lines: list[str] = []
    for line in config_text.splitlines():
        stripped = line.strip()
        match = re.search(r"listen\s+[^;]+;", stripped)
        if match:
            lines.append(match.group(0).strip())
    return _unique_lines(lines)


def _extract_location_lines(config_text: str) -> list[str]:
    targets = list(NGINX_ROUTE_TARGETS)
    lines: list[str] = []
    for line in config_text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("location "):
            continue
        if any(target in stripped for target in targets):
            lines.append(stripped)
    return _unique_lines(lines)


def _extract_maintenance_lines(config_text: str) -> list[str]:
    lines: list[str] = []
    for line in config_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if any(keyword in stripped.lower() for keyword in ("maintenance", "maintenance_flag", "flag")) or stripped.startswith("map "):
            lines.append(stripped)
    return _unique_lines(lines)


def _extract_listening_ports(ss_text: str) -> list[str]:
    ports: list[str] = []
    for match in re.finditer(r":(80|443)\b", ss_text):
        ports.append(match.group(1))
    return _unique_lines(ports)


def _extract_config_sections(config_text: str) -> list[NginxConfigSection]:
    sections: list[NginxConfigSection] = []
    current_path = "not found"
    current_lines: list[str] = []
    marker_re = re.compile(r"^# configuration file (?P<path>.+?):\s*$")

    for raw_line in config_text.splitlines():
        stripped = raw_line.strip()
        marker = marker_re.match(stripped)
        if marker:
            if current_lines:
                sections.append(NginxConfigSection(path=current_path, lines=current_lines))
            current_path = marker.group("path").strip()
            current_lines = []
            continue
        current_lines.append(raw_line)

    if current_lines:
        sections.append(NginxConfigSection(path=current_path, lines=current_lines))
    return sections


def _extract_server_blocks(sections: list[NginxConfigSection]) -> list[NginxServerBlock]:
    blocks: list[NginxServerBlock] = []
    for section in sections:
        lines = section.lines
        index = 0
        while index < len(lines):
            line = lines[index]
            if not re.search(r"^\s*server\s*\{", line):
                index += 1
                continue

            depth = line.count("{") - line.count("}")
            block_lines = [line]
            index += 1
            while index < len(lines) and depth > 0:
                line = lines[index]
                block_lines.append(line)
                depth += line.count("{") - line.count("}")
                index += 1
            blocks.append(NginxServerBlock(path=section.path, lines=block_lines))
    return blocks


def _block_line_values(block_lines: list[str], pattern: str) -> list[str]:
    values: list[str] = []
    regex = re.compile(pattern, re.IGNORECASE)
    for raw_line in block_lines:
        stripped = raw_line.strip()
        match = regex.search(stripped)
        if match:
            value = match.group(0).strip().rstrip(";")
            parts = value.split(None, 1)
            values.append(parts[1] if len(parts) > 1 else value)
    return _unique_lines(values)


def _extract_block_summary(block: NginxServerBlock) -> dict[str, list[str]]:
    return {
        "server_name": _block_line_values(block.lines, r"server_name\s+[^;]+;"),
        "listen": _block_line_values(block.lines, r"listen\s+[^;]+;"),
        "root": _block_line_values(block.lines, r"root\s+[^;]+;"),
        "alias": _block_line_values(block.lines, r"alias\s+[^;]+;"),
        "index": _block_line_values(block.lines, r"index\s+[^;]+;"),
        "return": _block_line_values(block.lines, r"return\s+[^;]+;"),
        "try_files": _block_line_values(block.lines, r"try_files\s+[^;]+;"),
        "proxy_pass": _block_line_values(block.lines, r"proxy_pass\s+[^;]+;"),
        "proxy_set_header": _block_line_values(block.lines, r"proxy_set_header\s+[^;]+;"),
        "ssl_certificate": _block_line_values(block.lines, r"ssl_certificate\s+[^;]+;"),
        "ssl_certificate_key": _block_line_values(block.lines, r"ssl_certificate_key\s+[^;]+;"),
        "include": _block_line_values(block.lines, r"include\s+[^;]+;"),
        "error_page": _block_line_values(block.lines, r"error_page\s+[^;]+;"),
        "locations": _extract_block_routes(block),
    }


def _extract_block_routes(block: NginxServerBlock) -> list[str]:
    routes: list[str] = []
    for raw_line in block.lines:
        stripped = raw_line.strip()
        route_match = re.match(r"location\s+(?:=|~\*?|^~)?\s*([^\s{]+)\s*\{?", stripped)
        if route_match:
            route = route_match.group(1).strip()
            if route in NGINX_ROUTE_TARGETS or any(route.startswith(prefix) for prefix in ("/",)):
                routes.append(route)
    return _unique_lines(routes)


def _path_summary(value: str | None) -> str:
    return value if value else "not found"


def _first_or_not_found(values: list[str]) -> str:
    return values[0] if values else "not found"


def _match_server_block(block_summary: dict[str, list[str]]) -> bool:
    server_names = " ".join(block_summary.get("server_name", [])).lower()
    routes = {route.lower() for route in block_summary.get("locations", [])}
    return any(target.lower() in server_names for target in NGINX_SERVER_NAME_TARGETS) or any(
        route in routes for route in NGINX_ROUTE_TARGETS
    )


def _build_config_details(config_text: str) -> tuple[list[str], list[str]]:
    sections = _extract_config_sections(config_text)
    server_blocks = _extract_server_blocks(sections)
    relevant_blocks: list[tuple[NginxServerBlock, dict[str, list[str]]]] = []
    active_config_paths: list[str] = []

    for block in server_blocks:
        summary = _extract_block_summary(block)
        if _match_server_block(summary):
            relevant_blocks.append((block, summary))
            if block.path and block.path not in active_config_paths:
                active_config_paths.append(block.path)

    route_targets = {target: [] for target in NGINX_ROUTE_TARGETS}
    for block, summary in relevant_blocks:
        for route in route_targets:
            if route in summary.get("locations", []):
                route_targets[route].append((block, summary))

    public_frontend = "not found"
    admin_frontend = "not found"
    api_upstream = "not found"
    ssl_certificate = "not found"
    ssl_certificate_key = "not found"
    acme_location = "not found"

    for route, matches in route_targets.items():
        if not matches:
            continue
        block, summary = matches[0]
        if route == "/":
            public_frontend = _path_summary(_first_or_not_found(summary.get("root") or summary.get("alias")))
        elif route == "/admin/":
            admin_frontend = _path_summary(_first_or_not_found(summary.get("alias") or summary.get("root")))
        elif route == "/api/":
            api_upstream = _path_summary(_first_or_not_found(summary.get("proxy_pass")))
        elif route == "/.well-known/acme-challenge/":
            acme_location = f"found in {block.path}"
        elif route in {"/api/docs", "/docs", "/openapi.json"} and api_upstream == "not found":
            api_upstream = _path_summary(_first_or_not_found(summary.get("proxy_pass")))
        if summary.get("ssl_certificate") and ssl_certificate == "not found":
            ssl_certificate = _path_summary(_first_or_not_found(summary.get("ssl_certificate")))
        if summary.get("ssl_certificate_key") and ssl_certificate_key == "not found":
            ssl_certificate_key = _path_summary(_first_or_not_found(summary.get("ssl_certificate_key")))

    if ssl_certificate == "not found" or ssl_certificate_key == "not found":
        for _block, summary in relevant_blocks:
            if summary.get("ssl_certificate") and ssl_certificate == "not found":
                ssl_certificate = _path_summary(_first_or_not_found(summary.get("ssl_certificate")))
            if summary.get("ssl_certificate_key") and ssl_certificate_key == "not found":
                ssl_certificate_key = _path_summary(_first_or_not_found(summary.get("ssl_certificate_key")))
            if ssl_certificate != "not found" and ssl_certificate_key != "not found":
                break

    if not active_config_paths:
        active_config_paths = ["not found"]

    short_summary_lines = [
        f"Active config: {', '.join(active_config_paths)}",
        f"Public site: root/alias: {public_frontend}",
        f"Admin: root/alias: {admin_frontend}",
        f"API: proxy_pass: {api_upstream}",
        f"SSL: certificate: {ssl_certificate}",
        f"SSL: private key path: {ssl_certificate_key}",
        f"ACME: location {acme_location if acme_location != 'not found' else 'not found'}",
    ]

    detail_lines: list[str] = []
    if relevant_blocks:
        detail_lines.append("relevant server blocks:")
        for block, summary in relevant_blocks:
            detail_lines.extend(
                [
                    f"- file: {block.path}",
                    f"  server_name: {', '.join(summary.get('server_name', [])) if summary.get('server_name') else 'not found'}",
                    f"  listen: {', '.join(summary.get('listen', [])) if summary.get('listen') else 'not found'}",
                    f"  root: {', '.join(summary.get('root', [])) if summary.get('root') else 'not found'}",
                    f"  alias: {', '.join(summary.get('alias', [])) if summary.get('alias') else 'not found'}",
                    f"  index: {', '.join(summary.get('index', [])) if summary.get('index') else 'not found'}",
                    f"  return: {', '.join(summary.get('return', [])) if summary.get('return') else 'not found'}",
                    f"  try_files: {', '.join(summary.get('try_files', [])) if summary.get('try_files') else 'not found'}",
                    f"  proxy_pass: {', '.join(summary.get('proxy_pass', [])) if summary.get('proxy_pass') else 'not found'}",
                    f"  proxy_set_header: {', '.join(summary.get('proxy_set_header', [])) if summary.get('proxy_set_header') else 'not found'}",
                    f"  ssl_certificate: {', '.join(summary.get('ssl_certificate', [])) if summary.get('ssl_certificate') else 'not found'}",
                    f"  ssl_certificate_key: {', '.join(summary.get('ssl_certificate_key', [])) if summary.get('ssl_certificate_key') else 'not found'}",
                    f"  include: {', '.join(summary.get('include', [])) if summary.get('include') else 'not found'}",
                    f"  error_page: {', '.join(summary.get('error_page', [])) if summary.get('error_page') else 'not found'}",
                    f"  locations: {', '.join(summary.get('locations', [])) if summary.get('locations') else 'not found'}",
                ]
            )
    else:
        detail_lines.append("relevant server blocks: not found")

    detail_lines.extend(
        [
            "routes:",
            *[
                _format_route_detail(route, matches)
                for route, matches in route_targets.items()
            ],
        ]
    )
    return short_summary_lines, detail_lines


def _format_route_detail(route: str, matches: list[tuple[NginxServerBlock, dict[str, list[str]]]]) -> str:
    if not matches:
        return f"- {route}: not found"
    block, summary = matches[0]
    parts = [f"file: {block.path}"]
    for key in ("root", "alias", "proxy_pass", "try_files", "return", "ssl_certificate", "ssl_certificate_key"):
        if summary.get(key):
            parts.append(f"{key}: {_first_or_not_found(summary[key])}")
    return f"- {route}: " + "; ".join(parts)


def _combined_output(result: CommandResult | None) -> str:
    if result is None:
        return ""
    parts = [result.stdout.strip(), result.stderr.strip()]
    return "\n".join(part for part in parts if part).strip()


def _clean_excerpt(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return "no output"
    lowered = [line.lower() for line in lines]
    for index, line in enumerate(lowered):
        if "sudo: a password is required" in line:
            return "sudo: a password is required"
        if "not in the sudoers file" in line:
            return "user is not in the sudoers file"
        if "permission denied" in line and "sudo" in line:
            return lines[index]
        if "nginx:" in line and "[emerg]" in line:
            return lines[index]
        if "command not found" in line:
            return lines[index]
    return lines[-1]


def _contains_directive(pattern: str, config_text: str) -> bool:
    return bool(re.search(pattern, config_text, re.IGNORECASE | re.MULTILINE))


def _probe_config_commands(command_runner: Callable[[str], CommandResult]) -> tuple[list[CommandResult], CommandResult | None, str]:
    attempts: list[CommandResult] = []
    reason = "config unavailable"
    for command in ("sudo -n nginx -T 2>&1", "nginx -T 2>&1"):
        try:
            result = command_runner(command)
        except Exception as exc:  # pragma: no cover - command runner dependent
            result = CommandResult(command=command, exit_code=1, stdout="", stderr=str(exc))
        attempts.append(result)
        if result.exit_code == 0:
            return attempts, result, ""
        reason = _clean_excerpt(_combined_output(result))
    return attempts, None, reason


def _run_ssh_command_with_input(
    client,
    command: str,
    input_text: str,
    timeout_seconds: float = 120.0,
) -> CommandResult:
    stdin, stdout, stderr = client.exec_command(command, get_pty=True, timeout=timeout_seconds)
    if input_text:
        stdin.write(input_text + "\n")
        stdin.flush()
    try:
        stdin.close()
    except Exception:
        pass
    stdout_text, stderr_text, exit_status = _collect_channel_output(stdout.channel, timeout_seconds=timeout_seconds)
    stderr_extra = stderr.read().decode("utf-8", errors="replace").strip()
    if stderr_extra and stderr_text:
        stderr_text = "\n".join(part for part in [stderr_text, stderr_extra] if part)
    elif stderr_extra:
        stderr_text = stderr_extra
    return CommandResult(command=command, exit_code=exit_status, stdout=stdout_text, stderr=stderr_text)


def _privileged_config_failure_reason(output_text: str) -> str:
    lowered = output_text.lower()
    if "password is required" in lowered or "sorry, try again" in lowered or "incorrect password" in lowered:
        return "Неправильний sudo-пароль або немає sudo-доступу."
    if "not in the sudoers file" in lowered:
        return "Користувач не має sudo-доступу."
    if "permission denied" in lowered:
        return "Немає дозволу читати nginx-конфіг."
    if "command not found" in lowered:
        return "Не знайдено команду nginx."
    return _clean_excerpt(output_text)


def _extract_path_result(result: CommandResult) -> tuple[str, bool, bool | None]:
    path = result.command.split("test -e ", 1)[-1].split("&&", 1)[0].strip()
    exists = "YES" in result.stdout.upper() or result.exit_code == 0 and "NO" not in result.stdout.upper()
    writable: bool | None = None
    if "WRITABLE" in result.stdout.upper():
        writable = True
    elif "NOT_WRITABLE" in result.stdout.upper():
        writable = False
    return path, exists, writable


def _summarize_path(path_result: tuple[str, bool, bool | None]) -> str:
    path, exists, writable = path_result
    if not exists:
        return f"- {path}: missing"
    if writable is None:
        return f"- {path}: exists"
    return f"- {path}: exists, writable={str(writable).lower()}"


def _format_report(
    command_results: list[CommandResult],
    config_attempts: list[CommandResult],
    config_result: CommandResult | None,
    config_reason: str,
    title: str = "read-only server audit for production nginx",
    *,
    server_names: list[str],
    listen_lines: list[str],
    location_lines: list[str],
    maintenance_lines: list[str],
    listening_ports: list[str],
    path_results: list[tuple[str, bool, bool | None]],
) -> tuple[str, str]:
    result_by_command = {item.command: item for item in command_results}
    nginx_status = result_by_command.get("systemctl status nginx --no-pager -l")
    nginx_active = result_by_command.get("systemctl is-active nginx")
    ss_result = result_by_command.get("ss -ltn")

    ssh_ok = command_results[0].exit_code == 0 if command_results else False
    config_ok = config_result is not None and config_result.exit_code == 0
    config_text = _combined_output(config_result)
    parser_issue = False
    if config_ok:
        parser_issue = (
            (_contains_directive(r"^\s*server_name\s+", config_text) and not server_names)
            or (_contains_directive(r"^\s*listen\s+", config_text) and not listen_lines)
            or (_contains_directive(r"^\s*location\s+", config_text) and not location_lines)
        )

    status = "ok"
    if not ssh_ok:
        status = "error"
    elif nginx_active and nginx_active.exit_code != 0:
        status = "error"
    elif not config_ok or parser_issue:
        status = "partial"

    if config_ok:
        config_line = "config: available via fallback" if config_attempts and config_attempts[0].exit_code != 0 else "config: available"
    else:
        config_line = f"config: unavailable - {config_reason}"

    summary_lines = [
        f"SSH: {'OK' if ssh_ok else 'error'}",
        f"nginx: {nginx_active.stdout.strip() if nginx_active and nginx_active.stdout.strip() else ('n/a' if not nginx_active else 'unknown')}",
        config_line,
        f"server_name: {', '.join(server_names) if server_names else ('unavailable' if not config_ok else 'not found')}",
        f"listen: {', '.join(listening_ports) if listening_ports else ('unavailable' if not config_ok else 'not found')}",
        f"locations: {', '.join(location_lines) if location_lines else ('unavailable' if not config_ok else 'not found')}",
        f"redirect http->https: {'yes' if config_ok and any('return 301 https://' in line or 'rewrite ' in line and 'https://' in line for line in config_text.splitlines()) else ('unavailable' if not config_ok else 'not found')}",
    ]

    if parser_issue:
        summary_lines.append("parser: config received, but expected directives were not extracted")

    if maintenance_lines:
        summary_lines.append(f"maintenance-related: {len(maintenance_lines)} line(s)")
    else:
        summary_lines.append("maintenance-related: not found")

    if path_results:
        summary_lines.extend(_summarize_path(item) for item in path_results)

    detail_summary_lines: list[str] = []
    detail_report_lines: list[str] = []
    if config_ok:
        detail_summary_lines, detail_report_lines = _build_config_details(config_text)
        summary_lines.extend(detail_summary_lines)

    config_report_lines: list[str] = ["config probe:"]
    for item in config_attempts:
        config_report_lines.append(f"- {item.command}: exit {item.exit_code}; {_clean_excerpt(_combined_output(item))}")
    if config_ok and config_attempts and config_attempts[0].exit_code != 0:
        config_report_lines.append("- fallback used: nginx -T 2>&1")
    if not config_ok:
        config_report_lines.append(f"- result: unavailable; {config_reason}")
    if parser_issue:
        config_report_lines.append("- parser: config text was received, but directives were not extracted")

    report_lines = [
        title,
        "",
        *config_report_lines,
        "",
        *summary_lines,
        "",
        "Systemctl status nginx:",
        *(nginx_status.stdout.splitlines() if nginx_status and nginx_status.stdout else ["n/a"]),
        "",
        "ss -ltn:",
        *(ss_result.stdout.splitlines() if ss_result and ss_result.stdout else ["n/a"]),
        "",
        "server_name lines:",
        *(server_names if server_names else ["not found"]),
        "",
        "listen lines:",
        *(listen_lines if listen_lines else ["not found"]),
        "",
        "location lines:",
        *(location_lines if location_lines else ["not found"]),
        "",
        "nginx config details:",
        *(detail_summary_lines if detail_summary_lines else ["not found"]),
        *(detail_report_lines if detail_report_lines else ["not found"]),
        "",
        "maintenance-related lines:",
        *(maintenance_lines if maintenance_lines else ["not found"]),
        "",
        "path checks:",
        *(_summarize_path(item) for item in path_results),
    ]

    return status, "\n".join(report_lines).strip() + "\n"


def audit_server(
    server_host: str,
    server_port: str,
    server_user: str,
    ssh_key_path: str,
    server_password: str,
    *,
    command_runner: Callable[[str], CommandResult] | None = None,
) -> AuditResult:
    client = None
    if command_runner is None:
        client, error = _open_paramiko_client(server_host, server_port, server_user, ssh_key_path, server_password)
        if client is None:
            summary = error or "Не вдалося виконати read-only аудит сервера."
            report = f"read-only server audit for production nginx\n\nSSH: error\n{summary}\n"
            return AuditResult(
                success=False,
                status="error",
                summary=summary,
                report=report,
                server_names=[],
                listen_lines=[],
                location_lines=[],
                maintenance_lines=[],
                listening_ports=[],
                path_results=[],
                command_results=[],
            )

        def command_runner_local(command: str) -> CommandResult:
            return _run_ssh_command(client, command)

        command_runner = command_runner_local

    commands = [
        "id",
        "groups",
        "systemctl is-active nginx",
        "systemctl status nginx --no-pager -l",
        "ss -ltn",
    ]

    for path in DEFAULT_CHECK_PATHS:
        commands.append(f"test -e {shlex.quote(path)} && echo EXISTS || echo MISSING")
        commands.append(f"test -w {shlex.quote(path)} && echo WRITABLE || echo NOT_WRITABLE")

    command_results: list[CommandResult] = []
    try:
        for command in commands:
            try:
                result = command_runner(command)
            except Exception as exc:  # pragma: no cover - command runner dependent
                result = CommandResult(command=command, exit_code=1, stdout="", stderr=str(exc))
            command_results.append(result)
        config_attempts, config_result, config_reason = _probe_config_commands(command_runner)
        command_results.extend(config_attempts)
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass

    result_by_command = {item.command: item for item in command_results}
    config_text = _combined_output(config_result)
    server_names = _extract_server_names(config_text)
    listen_lines = _extract_listen_lines(config_text)
    location_lines = _extract_location_lines(config_text)
    maintenance_lines = _extract_maintenance_lines(config_text)
    listening_ports = _extract_listening_ports(result_by_command.get("ss -ltn").stdout if result_by_command.get("ss -ltn") else "")
    config_ok = config_result is not None and config_result.exit_code == 0
    parser_issue = False
    if config_ok:
        parser_issue = (
            (_contains_directive(r"^\s*server_name\s+", config_text) and not server_names)
            or (_contains_directive(r"^\s*listen\s+", config_text) and not listen_lines)
            or (_contains_directive(r"^\s*location\s+", config_text) and not location_lines)
        )

    path_results: list[tuple[str, bool, bool | None]] = []
    for path in DEFAULT_CHECK_PATHS:
        exists_result = result_by_command.get(f"test -e {shlex.quote(path)} && echo EXISTS || echo MISSING")
        writable_result = result_by_command.get(f"test -w {shlex.quote(path)} && echo WRITABLE || echo NOT_WRITABLE")
        exists = bool(exists_result and "EXISTS" in exists_result.stdout.upper())
        writable: bool | None = None
        if writable_result:
            if "WRITABLE" in writable_result.stdout.upper():
                writable = True
            elif "NOT_WRITABLE" in writable_result.stdout.upper():
                writable = False
        path_results.append((path, exists, writable))

    status, report = _format_report(
        command_results,
        config_attempts,
        config_result,
        config_reason,
        server_names=server_names,
        listen_lines=listen_lines,
        location_lines=location_lines,
        maintenance_lines=maintenance_lines,
        listening_ports=listening_ports,
        path_results=path_results,
    )
    success = status == "ok"
    nginx_active = result_by_command.get("systemctl is-active nginx")
    if not command_results or command_results[0].exit_code != 0:
        summary = "Аудит частковий: SSH недоступний."
    elif nginx_active and nginx_active.exit_code != 0:
        summary = "Аудит частковий: nginx не працює."
    elif not config_ok:
        summary = f"Аудит частковий: {config_reason}."
    elif parser_issue:
        summary = "Аудит частковий: конфіг отримано, але parser не знайшов очікувані директиви."
    elif config_attempts and config_attempts[0].exit_code != 0:
        summary = "Аудит успішний: конфіг прочитано через fallback без sudo."
    else:
        summary = "Аудит успішний."
    return AuditResult(
        success=success,
        status=status,
        summary=summary,
        report=report,
        server_names=server_names,
        listen_lines=listen_lines,
        location_lines=location_lines,
        maintenance_lines=maintenance_lines,
        listening_ports=listening_ports,
        path_results=path_results,
        command_results=command_results,
    )


def audit_server_privileged(
    server_host: str,
    server_port: str,
    server_user: str,
    ssh_key_path: str,
    server_password: str,
    sudo_password: str,
) -> AuditResult:
    client = None
    try:
        client, error = _open_paramiko_client(server_host, server_port, server_user, ssh_key_path, server_password)
        if client is None:
            summary = error or "Не вдалося виконати privileged read-only аудит сервера."
            report = "privileged read-only server audit for production nginx\n\nSSH: error\n" + summary + "\n"
            return AuditResult(
                success=False,
                status="error",
                summary=summary,
                report=report,
                server_names=[],
                listen_lines=[],
                location_lines=[],
                maintenance_lines=[],
                listening_ports=[],
                path_results=[],
                command_results=[],
            )

        password = sudo_password.strip()
        if not password:
            summary = "Потрібен sudo-пароль для privileged read-only перевірки."
            report = "privileged read-only server audit for production nginx\n\n" + summary + "\n"
            return AuditResult(
                success=False,
                status="error",
                summary=summary,
                report=report,
                server_names=[],
                listen_lines=[],
                location_lines=[],
                maintenance_lines=[],
                listening_ports=[],
                path_results=[],
                command_results=[],
            )

        command_results: list[CommandResult] = []
        for command in [
            "id",
            "groups",
            "systemctl is-active nginx",
            "systemctl status nginx --no-pager -l",
            "ss -ltn",
        ]:
            try:
                result = _run_ssh_command(client, command)
            except Exception as exc:  # pragma: no cover - remote dependent
                result = CommandResult(command=command, exit_code=1, stdout="", stderr=str(exc))
            command_results.append(result)

        try:
            config_result = _run_ssh_command_with_input(client, PRIVILEGED_NGINX_COMMAND, password)
        except Exception as exc:  # pragma: no cover - remote dependent
            config_result = CommandResult(command=PRIVILEGED_NGINX_COMMAND, exit_code=1, stdout="", stderr=str(exc))
        command_results.append(config_result)

        result_by_command = {item.command: item for item in command_results}
        config_text = _combined_output(config_result)
        server_names = _extract_server_names(config_text)
        listen_lines = _extract_listen_lines(config_text)
        location_lines = _extract_location_lines(config_text)
        maintenance_lines = _extract_maintenance_lines(config_text)
        listening_ports = _extract_listening_ports(result_by_command.get("ss -ltn").stdout if result_by_command.get("ss -ltn") else "")

        config_ok = config_result.exit_code == 0
        parser_issue = False
        if config_ok:
            parser_issue = (
                (_contains_directive(r"^\s*server_name\s+", config_text) and not server_names)
                or (_contains_directive(r"^\s*listen\s+", config_text) and not listen_lines)
                or (_contains_directive(r"^\s*location\s+", config_text) and not location_lines)
            )

        path_results: list[tuple[str, bool, bool | None]] = []
        for path in DEFAULT_CHECK_PATHS:
            exists_result = result_by_command.get(f"test -e {shlex.quote(path)} && echo EXISTS || echo MISSING")
            writable_result = result_by_command.get(f"test -w {shlex.quote(path)} && echo WRITABLE || echo NOT_WRITABLE")
            exists = bool(exists_result and "EXISTS" in exists_result.stdout.upper())
            writable: bool | None = None
            if writable_result:
                if "WRITABLE" in writable_result.stdout.upper():
                    writable = True
                elif "NOT_WRITABLE" in writable_result.stdout.upper():
                    writable = False
            path_results.append((path, exists, writable))

        config_reason = ""
        if not config_ok:
            config_reason = _privileged_config_failure_reason(_combined_output(config_result))
        elif parser_issue:
            config_reason = "parser could not extract nginx directives"

        status, report = _format_report(
            command_results,
            [config_result],
            config_result,
            config_reason,
            title="privileged read-only server audit for production nginx",
            server_names=server_names,
            listen_lines=listen_lines,
            location_lines=location_lines,
            maintenance_lines=maintenance_lines,
            listening_ports=listening_ports,
            path_results=path_results,
        )
        success = status == "ok"
        summary = "Привілейована перевірка успішна." if success else f"Привілейована перевірка: {config_reason or 'помилка читання nginx-конфігурації'}"
        return AuditResult(
            success=success,
            status=status if status in {"ok", "error"} else "error",
            summary=summary,
            report=report,
            server_names=server_names,
            listen_lines=listen_lines,
            location_lines=location_lines,
            maintenance_lines=maintenance_lines,
            listening_ports=listening_ports,
            path_results=path_results,
            command_results=command_results,
        )
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass
