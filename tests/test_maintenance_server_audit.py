from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

import scripts.maintenance_server_audit as maintenance_audit
from scripts import db_update_wizard
from scripts.maintenance_server_audit import (
    DEFAULT_CHECK_PATHS,
    PRIVILEGED_NGINX_COMMAND,
    CommandResult,
    audit_server,
    audit_server_privileged,
)


class MaintenanceServerAuditTests(unittest.TestCase):
    def _base_outputs(self, config_text: str) -> dict[str, tuple[int, str, str]]:
        outputs: dict[str, tuple[int, str, str]] = {
            "id": (0, "uid=1000(mpc) gid=1000(mpc)", ""),
            "groups": (0, "mpc sudo", ""),
            "systemctl is-active nginx": (0, "active", ""),
            "systemctl status nginx --no-pager -l": (0, "nginx service status", ""),
            "ss -ltn": (0, "LISTEN 0 128 0.0.0.0:80 0.0.0.0:* LISTEN 0 128 0.0.0.0:443 0.0.0.0:*", ""),
            "sudo -n nginx -T 2>&1": (1, "", "sudo: a password is required"),
            "nginx -T 2>&1": (0, config_text, ""),
        }
        for path in DEFAULT_CHECK_PATHS:
            outputs[f"test -e {path} && echo EXISTS || echo MISSING"] = (0, "EXISTS", "")
            outputs[f"test -w {path} && echo WRITABLE || echo NOT_WRITABLE"] = (0, "WRITABLE", "")
        return outputs

    def _runner_from_outputs(self, outputs: dict[str, tuple[int, str, str]]):
        def runner(command: str) -> CommandResult:
            exit_code, stdout, stderr = outputs[command]
            return CommandResult(command=command, exit_code=exit_code, stdout=stdout, stderr=stderr)

        return runner

    def test_audit_server_uses_sudo_then_fallback_and_extracts_config(self) -> None:
        config_text = """
        server {
            server_name example.com furniture.example.com;
            listen 80;
            listen 443 ssl;
            location / { try_files $uri $uri/ /index.html; }
            location /admin/ { proxy_pass http://127.0.0.1:5173; }
            location /api/ { proxy_pass http://127.0.0.1:8000; }
            location /.well-known/acme-challenge/ { root /var/www/acme; }
            return 301 https://$host$request_uri;
        }
        """.strip()
        result = audit_server(
            "example.com",
            "22",
            "deploy",
            "~/.ssh/id_ed25519",
            "",
            command_runner=self._runner_from_outputs(self._base_outputs(config_text)),
        )

        self.assertTrue(result.success)
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.server_names, ["example.com", "furniture.example.com"])
        self.assertTrue(any("listen 443 ssl;" in line for line in result.listen_lines))
        self.assertTrue(any("location /admin/" in line for line in result.location_lines))
        self.assertEqual(result.listening_ports, ["80", "443"])
        self.assertIn("Аудит успішний", result.summary)
        self.assertIn("fallback used: nginx -T 2>&1", result.report)
        self.assertIn("sudo: a password is required", result.report)
        self.assertIn("server_name lines:", result.report)
        self.assertIn("location /api/", result.report)
        self.assertIn("redirect http->https: yes", result.report)
        self.assertEqual(len([item for item in result.command_results if item.command == "sudo -n nginx -T 2>&1"]), 1)
        self.assertEqual(len([item for item in result.command_results if item.command == "nginx -T 2>&1"]), 1)

    def test_audit_server_reports_partial_reason_when_config_unavailable(self) -> None:
        outputs: dict[str, tuple[int, str, str]] = {
            "id": (0, "uid=1000(mpc) gid=1000(mpc)", ""),
            "groups": (0, "mpc sudo", ""),
            "systemctl is-active nginx": (0, "active", ""),
            "systemctl status nginx --no-pager -l": (0, "nginx service status", ""),
            "ss -ltn": (0, "LISTEN 0 128 0.0.0.0:80 0.0.0.0:* LISTEN 0 128 0.0.0.0:443 0.0.0.0:*", ""),
            "sudo -n nginx -T 2>&1": (1, "", "sudo: a password is required"),
            "nginx -T 2>&1": (1, "", "nginx: [emerg] open() \"/etc/nginx/nginx.conf\" failed (13: Permission denied)"),
        }
        for path in DEFAULT_CHECK_PATHS:
            outputs[f"test -e {path} && echo EXISTS || echo MISSING"] = (0, "EXISTS", "")
            outputs[f"test -w {path} && echo WRITABLE || echo NOT_WRITABLE"] = (0, "WRITABLE", "")

        result = audit_server("example.com", "22", "deploy", "~/.ssh/id_ed25519", "", command_runner=self._runner_from_outputs(outputs))

        self.assertFalse(result.success)
        self.assertEqual(result.status, "partial")
        self.assertIn("Аудит частковий", result.summary)
        self.assertIn("sudo: a password is required", result.report)
        self.assertIn("permission denied", result.report.lower())
        self.assertIn("result: unavailable", result.report)
        self.assertIn("server_name: unavailable", result.report)
        self.assertIn("listen: 80, 443", result.report)
        self.assertIn("locations: unavailable", result.report)

    def test_privileged_audit_sends_password_via_stdin_and_uses_fixed_command(self) -> None:
        class FakeStdin:
            def __init__(self) -> None:
                self.written = ""
                self.closed = False

            def write(self, text: str) -> None:
                self.written += text

            def flush(self) -> None:
                pass

            def close(self) -> None:
                self.closed = True

        class FakeStream:
            def __init__(self, channel: SimpleNamespace, stderr_text: str = "") -> None:
                self.channel = channel
                self._stderr_text = stderr_text

            def read(self) -> bytes:
                return self._stderr_text.encode("utf-8")

        class FakeClient:
            def __init__(self, outputs: dict[str, tuple[int, str, str]]) -> None:
                self.outputs = outputs
                self.calls: list[tuple[str, bool, float | None]] = []
                self.stdin_by_command: dict[str, FakeStdin] = {}
                self.closed = False

            def exec_command(self, command: str, get_pty: bool = False, timeout: float | None = None):
                self.calls.append((command, get_pty, timeout))
                exit_code, stdout_text, stderr_text = self.outputs[command]
                channel = SimpleNamespace(stdout_text=stdout_text, stderr_text=stderr_text, exit_status=exit_code)
                stdin = FakeStdin()
                self.stdin_by_command[command] = stdin
                return stdin, FakeStream(channel), FakeStream(channel, stderr_text)

            def close(self) -> None:
                self.closed = True

        config_text = """
        server {
            server_name example.com furniture.example.com;
            listen 80;
            listen 443 ssl;
            location / { try_files $uri $uri/ /index.html; }
            location /admin/ { proxy_pass http://127.0.0.1:5173; }
            location /api/ { proxy_pass http://127.0.0.1:8000; }
            location /.well-known/acme-challenge/ { root /var/www/acme; }
            return 301 https://$host$request_uri;
        }
        """.strip()
        outputs: dict[str, tuple[int, str, str]] = {
            "id": (0, "uid=1000(mpc) gid=1000(mpc)", ""),
            "groups": (0, "mpc sudo", ""),
            "systemctl is-active nginx": (0, "active", ""),
            "systemctl status nginx --no-pager -l": (0, "nginx service status", ""),
            "ss -ltn": (0, "LISTEN 0 128 0.0.0.0:80 0.0.0.0:* LISTEN 0 128 0.0.0.0:443 0.0.0.0:*", ""),
            PRIVILEGED_NGINX_COMMAND: (0, config_text, ""),
        }
        for path in DEFAULT_CHECK_PATHS:
            outputs[f"test -e {path} && echo EXISTS || echo MISSING"] = (0, "EXISTS", "")
            outputs[f"test -w {path} && echo WRITABLE || echo NOT_WRITABLE"] = (0, "WRITABLE", "")

        fake_client = FakeClient(outputs)

        with patch.object(maintenance_audit, "_open_paramiko_client", return_value=(fake_client, None)), patch.object(
            maintenance_audit,
            "_collect_channel_output",
            side_effect=lambda channel, timeout_seconds=120.0: (channel.stdout_text, channel.stderr_text, channel.exit_status),
        ):
            result = audit_server_privileged(
                "example.com",
                "22",
                "deploy",
                "~/.ssh/id_ed25519",
                "",
                "sudo-secret",
            )

        self.assertTrue(result.success)
        self.assertEqual(result.status, "ok")
        self.assertEqual(fake_client.calls[-1][0], PRIVILEGED_NGINX_COMMAND)
        self.assertTrue(fake_client.calls[-1][1])
        self.assertEqual(fake_client.stdin_by_command[PRIVILEGED_NGINX_COMMAND].written, "sudo-secret\n")
        self.assertTrue(fake_client.stdin_by_command[PRIVILEGED_NGINX_COMMAND].closed)
        self.assertIn("privileged read-only server audit for production nginx", result.report)
        self.assertNotIn("sudo-secret", result.report)
        self.assertTrue(any("listen 443 ssl;" in line for line in result.listen_lines))
        self.assertIn("Привілейована перевірка успішна.", result.summary)

    def test_collect_channel_output_times_out_and_closes_channel(self) -> None:
        class FakeChannel:
            def __init__(self) -> None:
                self.closed = False
                self.shutdown_called = False

            def recv_ready(self) -> bool:
                return False

            def recv_stderr_ready(self) -> bool:
                return False

            def exit_status_ready(self) -> bool:
                return False

            def recv(self, _size: int) -> bytes:
                return b""

            def recv_stderr(self, _size: int) -> bytes:
                return b""

            def shutdown(self) -> None:
                self.shutdown_called = True

            def close(self) -> None:
                self.closed = True

        channel = FakeChannel()
        with patch.object(maintenance_audit.time, "monotonic", side_effect=[0.0, 2.0]), patch.object(
            maintenance_audit.time, "sleep"
        ) as sleep_mock:
            with self.assertRaises(TimeoutError):
                maintenance_audit._collect_channel_output(channel, timeout_seconds=1.0, poll_interval=0.01)

        self.assertTrue(channel.shutdown_called or channel.closed)
        sleep_mock.assert_not_called()

    def test_privileged_audit_reports_full_nginx_config_paths_and_routes(self) -> None:
        class FakeStdin:
            def __init__(self) -> None:
                self.written = ""
                self.closed = False

            def write(self, text: str) -> None:
                self.written += text

            def flush(self) -> None:
                pass

            def close(self) -> None:
                self.closed = True

        class FakeStream:
            def __init__(self, channel: SimpleNamespace, stderr_text: str = "") -> None:
                self.channel = channel
                self._stderr_text = stderr_text

            def read(self) -> bytes:
                return self._stderr_text.encode("utf-8")

        class FakeClient:
            def __init__(self, outputs: dict[str, tuple[int, str, str]]) -> None:
                self.outputs = outputs
                self.calls: list[tuple[str, bool, float | None]] = []
                self.stdin_by_command: dict[str, FakeStdin] = {}

            def exec_command(self, command: str, get_pty: bool = False, timeout: float | None = None):
                self.calls.append((command, get_pty, timeout))
                exit_code, stdout_text, stderr_text = self.outputs[command]
                channel = SimpleNamespace(stdout_text=stdout_text, stderr_text=stderr_text, exit_status=exit_code)
                stdin = FakeStdin()
                self.stdin_by_command[command] = stdin
                return stdin, FakeStream(channel), FakeStream(channel, stderr_text)

            def close(self) -> None:
                pass

        config_text = """
        # configuration file /etc/nginx/nginx.conf:
        worker_processes auto;
        events {}
        http {
            include /etc/nginx/sites-enabled/*;
        }
        # configuration file /etc/nginx/sites-enabled/furniture:
        server {
            listen 80;
            server_name mpfc.com.ua www.mpfc.com.ua 45.94.157.42;
            location /.well-known/acme-challenge/ { root /var/www/acme; }
            return 301 https://$host$request_uri;
        }
        # configuration file /etc/nginx/sites-enabled/furniture-ssl.conf:
        server {
            listen 443 ssl http2;
            server_name mpfc.com.ua www.mpfc.com.ua 45.94.157.42;
            root /var/www/mpfc/public;
            index index.html;
            ssl_certificate /etc/letsencrypt/live/mpfc.com.ua/fullchain.pem;
            ssl_certificate_key /etc/letsencrypt/live/mpfc.com.ua/privkey.pem;
            include /etc/nginx/snippets/ssl-params.conf;
            error_page 404 /index.html;
            location / {
                try_files $uri $uri/ /index.html;
            }
            location /admin/ {
                alias /var/www/mpfc/admin/;
                index index.html;
                proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            }
            location /api/ {
                proxy_pass http://127.0.0.1:8000;
                proxy_set_header Host $host;
                proxy_set_header X-Real-IP $remote_addr;
            }
            location /api/docs {
                proxy_pass http://127.0.0.1:8000;
            }
            location /openapi.json {
                proxy_pass http://127.0.0.1:8000;
            }
        }
        """.strip()

        outputs: dict[str, tuple[int, str, str]] = {
            "id": (0, "uid=1000(mpc) gid=1000(mpc)", ""),
            "groups": (0, "mpc sudo", ""),
            "systemctl is-active nginx": (0, "active", ""),
            "systemctl status nginx --no-pager -l": (0, "nginx service status", ""),
            "ss -ltn": (0, "LISTEN 0 128 0.0.0.0:80 0.0.0.0:* LISTEN 0 128 0.0.0.0:443 0.0.0.0:*", ""),
            PRIVILEGED_NGINX_COMMAND: (0, config_text, ""),
        }
        for path in DEFAULT_CHECK_PATHS:
            outputs[f"test -e {path} && echo EXISTS || echo MISSING"] = (0, "EXISTS", "")
            outputs[f"test -w {path} && echo WRITABLE || echo NOT_WRITABLE"] = (0, "WRITABLE", "")

        fake_client = FakeClient(outputs)

        with patch.object(maintenance_audit, "_open_paramiko_client", return_value=(fake_client, None)), patch.object(
            maintenance_audit,
            "_collect_channel_output",
            side_effect=lambda channel, timeout_seconds=120.0: (channel.stdout_text, channel.stderr_text, channel.exit_status),
        ):
            result = audit_server_privileged(
                "example.com",
                "22",
                "deploy",
                "~/.ssh/id_ed25519",
                "",
                "sudo-secret",
            )

        self.assertTrue(result.success)
        self.assertEqual(result.status, "ok")
        self.assertIn("Active config: /etc/nginx/sites-enabled/furniture, /etc/nginx/sites-enabled/furniture-ssl.conf", result.report)
        self.assertIn("Public site: root/alias: /var/www/mpfc/public", result.report)
        self.assertIn("Admin: root/alias: /var/www/mpfc/admin/", result.report)
        self.assertIn("API: proxy_pass: http://127.0.0.1:8000", result.report)
        self.assertIn("SSL: certificate: /etc/letsencrypt/live/mpfc.com.ua/fullchain.pem", result.report)
        self.assertIn("SSL: private key path: /etc/letsencrypt/live/mpfc.com.ua/privkey.pem", result.report)
        self.assertIn("ACME: location found in /etc/nginx/sites-enabled/furniture", result.report)
        self.assertIn("file: /etc/nginx/sites-enabled/furniture", result.report)
        self.assertIn("file: /etc/nginx/sites-enabled/furniture-ssl.conf", result.report)
        self.assertIn("- /openapi.json: file: /etc/nginx/sites-enabled/furniture-ssl.conf", result.report)
        self.assertIn("- /docs: not found", result.report)
        self.assertIn("proxy_set_header: X-Forwarded-For $proxy_add_x_forwarded_for", result.report)
        self.assertIn("ssl_certificate_key: /etc/letsencrypt/live/mpfc.com.ua/privkey.pem", result.report)
        self.assertNotIn("sudo-secret", result.report)
        self.assertNotIn("password", result.report.lower())
        self.assertTrue(all("reload" not in command for command, *_ in fake_client.calls))
        self.assertTrue(all("restart" not in command for command, *_ in fake_client.calls))
        self.assertTrue(all("write" not in command.lower() for command, *_ in fake_client.calls))

    def test_privileged_audit_reports_owner_aware_structure(self) -> None:
        class FakeStdin:
            def __init__(self) -> None:
                self.written = ""
                self.closed = False

            def write(self, text: str) -> None:
                self.written += text

            def flush(self) -> None:
                pass

            def close(self) -> None:
                self.closed = True

        class FakeStream:
            def __init__(self, channel: SimpleNamespace, stderr_text: str = "") -> None:
                self.channel = channel
                self._stderr_text = stderr_text

            def read(self) -> bytes:
                return self._stderr_text.encode("utf-8")

        class FakeClient:
            def __init__(self, outputs: dict[str, tuple[int, str, str]]) -> None:
                self.outputs = outputs
                self.calls: list[tuple[str, bool, float | None]] = []

            def exec_command(self, command: str, get_pty: bool = False, timeout: float | None = None):
                self.calls.append((command, get_pty, timeout))
                exit_code, stdout_text, stderr_text = self.outputs[command]
                channel = SimpleNamespace(stdout_text=stdout_text, stderr_text=stderr_text, exit_status=exit_code)
                stdin = FakeStdin()
                return stdin, FakeStream(channel), FakeStream(channel, stderr_text)

            def close(self) -> None:
                pass

        config_text = """
        # configuration file /etc/nginx/sites-enabled/furniture-owner.conf:
        map $http_cookie $mpfc_maintenance_gate_file {
            default /opt/furniture-maintenance/maintenance.flag;
            "~(?:^|;\\s*)mpfc_maintenance_owner=CaseSensitiveToken(?:;|$)" "";
        }

        map $remote_user $mpfc_maintenance_owner_set_cookie {
            default "";
            "mpfc-owner" "mpfc_maintenance_owner=CaseSensitiveToken; Path=/; Max-Age=7200; Secure; HttpOnly; SameSite=Strict";
        }

        server {
            listen 443 ssl http2;
            server_name mpfc.com.ua www.mpfc.com.ua 45.94.157.42;
            root /var/www/mpfc/public;
            include /etc/nginx/secure/mpfc-maintenance-owner-map.conf;
            location / {
                if (-f $mpfc_maintenance_gate_file) { return 503; }
            }
            location /admin/ {
                if (-f $mpfc_maintenance_gate_file) { return 503; }
            }
            location /api/ {
                if (-f $mpfc_maintenance_gate_file) { return 503; }
            }
            location = /openapi.json {
                if (-f $mpfc_maintenance_gate_file) { return 503; }
            }
            include /etc/nginx/secure/mpfc-maintenance-owner-locations.conf;
        }
        location = /__maintenance_owner/login {
            auth_basic "MP Furniture Owner Access";
            add_header Set-Cookie $mpfc_maintenance_owner_set_cookie always;
        }
        location = /__maintenance_owner/logout {
            add_header Set-Cookie "mpfc_maintenance_owner=; Path=/; Max-Age=0; Secure; HttpOnly; SameSite=Strict" always;
        }
        """.strip()

        outputs: dict[str, tuple[int, str, str]] = {
            "id": (0, "uid=1000(mpc) gid=1000(mpc)", ""),
            "groups": (0, "mpc sudo", ""),
            "systemctl is-active nginx": (0, "active", ""),
            "systemctl status nginx --no-pager -l": (0, "nginx service status", ""),
            "ss -ltn": (0, "LISTEN 0 128 0.0.0.0:80 0.0.0.0:* LISTEN 0 128 0.0.0.0:443 0.0.0.0:*", ""),
            PRIVILEGED_NGINX_COMMAND: (0, config_text, ""),
        }
        for path in DEFAULT_CHECK_PATHS:
            outputs[f"test -e {path} && echo EXISTS || echo MISSING"] = (0, "EXISTS", "")
            outputs[f"test -w {path} && echo WRITABLE || echo NOT_WRITABLE"] = (0, "WRITABLE", "")

        fake_client = FakeClient(outputs)

        with patch.object(maintenance_audit, "_open_paramiko_client", return_value=(fake_client, None)), patch.object(
            maintenance_audit,
            "_collect_channel_output",
            side_effect=lambda channel, timeout_seconds=120.0: (channel.stdout_text, channel.stderr_text, channel.exit_status),
        ):
            result = audit_server_privileged(
                "example.com",
                "22",
                "deploy",
                "~/.ssh/id_ed25519",
                "",
                "sudo-secret",
            )

        self.assertTrue(result.success)
        self.assertIn("owner-aware gate checks: 4", result.report)
        self.assertIn("owner cookie map blocks: 1", result.report)
        self.assertIn("owner-aware include lines: 1", result.report)
        self.assertIn("owner login locations: 1", result.report)
        self.assertIn("owner logout locations: 1", result.report)
        self.assertIn("owner login auth_basic: 1", result.report)
        self.assertIn("owner login set-cookie variable: 1", result.report)
        self.assertIn("owner login direct set-cookie: 0", result.report)
        self.assertIn("owner logout clear cookie: 1", result.report)
        self.assertIn("owner login wiring: secure", result.report)
        self.assertIn("legacy maintenance.flag checks: 0", result.report)
        self.assertIn("owner-aware lines:", result.report)
        self.assertIn("if (-f $mpfc_maintenance_gate_file)", result.report)
        self.assertIn("include /etc/nginx/secure/mpfc-maintenance-owner-locations.conf;", result.report)
        self.assertIn("map $remote_user $mpfc_maintenance_owner_set_cookie", result.report)
        self.assertIn("add_header Set-Cookie $mpfc_maintenance_owner_set_cookie always;", result.report)
        self.assertNotIn("CaseSensitiveToken", result.report)

    def test_privileged_audit_flags_legacy_owner_cookie_wiring(self) -> None:
        class FakeStdin:
            def __init__(self) -> None:
                self.written = ""
                self.closed = False

            def write(self, text: str) -> None:
                self.written += text

            def flush(self) -> None:
                pass

            def close(self) -> None:
                self.closed = True

        class FakeStream:
            def __init__(self, channel: SimpleNamespace, stderr_text: str = "") -> None:
                self.channel = channel
                self._stderr_text = stderr_text

            def read(self) -> bytes:
                return self._stderr_text.encode("utf-8")

        class FakeClient:
            def __init__(self, outputs: dict[str, tuple[int, str, str]]) -> None:
                self.outputs = outputs
                self.calls: list[tuple[str, bool, float | None]] = []

            def exec_command(self, command: str, get_pty: bool = False, timeout: float | None = None):
                self.calls.append((command, get_pty, timeout))
                exit_code, stdout_text, stderr_text = self.outputs[command]
                channel = SimpleNamespace(stdout_text=stdout_text, stderr_text=stderr_text, exit_status=exit_code)
                stdin = FakeStdin()
                return stdin, FakeStream(channel), FakeStream(channel, stderr_text)

            def close(self) -> None:
                pass

        config_text = """
        # configuration file /etc/nginx/sites-enabled/furniture-owner.conf:
        server {
            listen 443 ssl http2;
            server_name mpfc.com.ua www.mpfc.com.ua 45.94.157.42;
            root /var/www/mpfc/public;
            location / {
                if (-f $mpfc_maintenance_gate_file) { return 503; }
            }
            location = /__maintenance_owner/login {
                auth_basic "MP Furniture Owner Access";
                add_header Set-Cookie "mpfc_maintenance_owner=legacy-token; Path=/; Max-Age=7200; Secure; HttpOnly; SameSite=Strict" always;
            }
            location = /__maintenance_owner/logout {
                add_header Set-Cookie "mpfc_maintenance_owner=; Path=/; Max-Age=0; Secure; HttpOnly; SameSite=Strict" always;
            }
        }
        """.strip()

        outputs: dict[str, tuple[int, str, str]] = {
            "id": (0, "uid=1000(mpc) gid=1000(mpc)", ""),
            "groups": (0, "mpc sudo", ""),
            "systemctl is-active nginx": (0, "active", ""),
            "systemctl status nginx --no-pager -l": (0, "nginx service status", ""),
            "ss -ltn": (0, "LISTEN 0 128 0.0.0.0:80 0.0.0.0:* LISTEN 0 128 0.0.0.0:443 0.0.0.0:*", ""),
            PRIVILEGED_NGINX_COMMAND: (0, config_text, ""),
        }
        for path in DEFAULT_CHECK_PATHS:
            outputs[f"test -e {path} && echo EXISTS || echo MISSING"] = (0, "EXISTS", "")
            outputs[f"test -w {path} && echo WRITABLE || echo NOT_WRITABLE"] = (0, "WRITABLE", "")

        fake_client = FakeClient(outputs)

        with patch.object(maintenance_audit, "_open_paramiko_client", return_value=(fake_client, None)), patch.object(
            maintenance_audit,
            "_collect_channel_output",
            side_effect=lambda channel, timeout_seconds=120.0: (channel.stdout_text, channel.stderr_text, channel.exit_status),
        ):
            result = audit_server_privileged(
                "example.com",
                "22",
                "deploy",
                "~/.ssh/id_ed25519",
                "",
                "sudo-secret",
            )

        self.assertTrue(result.success)
        self.assertIn("owner login wiring: legacy insecure", result.report)
        self.assertIn("owner login direct set-cookie: 1", result.report)
        self.assertIn("owner login set-cookie variable: 0", result.report)
        self.assertIn('add_header Set-Cookie "mpfc_maintenance_owner=<redacted>; Path=/; Max-Age=7200; Secure; HttpOnly; SameSite=Strict" always;', result.report)

    def test_privileged_audit_uses_sixty_second_privileged_timeout(self) -> None:
        class FakeStdin:
            def __init__(self) -> None:
                self.written = ""
                self.closed = False

            def write(self, text: str) -> None:
                self.written += text

            def flush(self) -> None:
                pass

            def close(self) -> None:
                self.closed = True

        class FakeStream:
            def __init__(self, channel: SimpleNamespace, stderr_text: str = "") -> None:
                self.channel = channel
                self._stderr_text = stderr_text

            def read(self) -> bytes:
                return self._stderr_text.encode("utf-8")

        class FakeClient:
            def __init__(self, outputs: dict[str, tuple[int, str, str]]) -> None:
                self.outputs = outputs
                self.calls: list[tuple[str, bool, float | None]] = []

            def exec_command(self, command: str, get_pty: bool = False, timeout: float | None = None):
                self.calls.append((command, get_pty, timeout))
                exit_code, stdout_text, stderr_text = self.outputs[command]
                channel = SimpleNamespace(stdout_text=stdout_text, stderr_text=stderr_text, exit_status=exit_code)
                stdin = FakeStdin()
                return stdin, FakeStream(channel), FakeStream(channel, stderr_text)

            def close(self) -> None:
                pass

        outputs: dict[str, tuple[int, str, str]] = {
            "id": (0, "uid=1000(mpc) gid=1000(mpc)", ""),
            "groups": (0, "mpc sudo", ""),
            "systemctl is-active nginx": (0, "active", ""),
            "systemctl status nginx --no-pager -l": (0, "nginx service status", ""),
            "ss -ltn": (0, "LISTEN 0 128 0.0.0.0:80 0.0.0.0:* LISTEN 0 128 0.0.0.0:443 0.0.0.0:*", ""),
            PRIVILEGED_NGINX_COMMAND: (0, "nginx config", ""),
        }
        for path in DEFAULT_CHECK_PATHS:
            outputs[f"test -e {path} && echo EXISTS || echo MISSING"] = (0, "EXISTS", "")
            outputs[f"test -w {path} && echo WRITABLE || echo NOT_WRITABLE"] = (0, "WRITABLE", "")

        fake_client = FakeClient(outputs)

        with patch.object(maintenance_audit, "_open_paramiko_client", return_value=(fake_client, None)), patch.object(
            maintenance_audit,
            "_collect_channel_output",
            side_effect=lambda channel, timeout_seconds=120.0: (channel.stdout_text, channel.stderr_text, channel.exit_status),
        ):
            result = audit_server_privileged(
                "example.com",
                "22",
                "deploy",
                "~/.ssh/id_ed25519",
                "",
                "sudo-secret",
            )

        self.assertTrue(result.success)
        self.assertEqual(fake_client.calls[-1][2], 60.0)

    def test_privileged_audit_reports_sudo_denied_without_leaking_password(self) -> None:
        class FakeStdin:
            def __init__(self) -> None:
                self.written = ""
                self.closed = False

            def write(self, text: str) -> None:
                self.written += text

            def flush(self) -> None:
                pass

            def close(self) -> None:
                self.closed = True

        class FakeStream:
            def __init__(self, channel: SimpleNamespace, stderr_text: str = "") -> None:
                self.channel = channel
                self._stderr_text = stderr_text

            def read(self) -> bytes:
                return self._stderr_text.encode("utf-8")

        class FakeClient:
            def __init__(self) -> None:
                self.calls: list[tuple[str, bool, float | None]] = []

            def exec_command(self, command: str, get_pty: bool = False, timeout: float | None = None):
                self.calls.append((command, get_pty, timeout))
                if command == PRIVILEGED_NGINX_COMMAND:
                    channel = SimpleNamespace(stdout_text="", stderr_text="sudo: a password is required", exit_status=1)
                else:
                    channel = SimpleNamespace(stdout_text="ok", stderr_text="", exit_status=0)
                return FakeStdin(), FakeStream(channel), FakeStream(channel, channel.stderr_text)

            def close(self) -> None:
                pass

        fake_client = FakeClient()

        with patch.object(maintenance_audit, "_open_paramiko_client", return_value=(fake_client, None)), patch.object(
            maintenance_audit,
            "_collect_channel_output",
            side_effect=lambda channel, timeout_seconds=120.0: (channel.stdout_text, channel.stderr_text, channel.exit_status),
        ):
            result = audit_server_privileged(
                "example.com",
                "22",
                "deploy",
                "~/.ssh/id_ed25519",
                "",
                "wrong-secret",
            )

        self.assertFalse(result.success)
        self.assertEqual(result.status, "error")
        self.assertIn("Неправильний sudo-пароль", result.summary)
        self.assertNotIn("wrong-secret", result.summary)
        self.assertNotIn("wrong-secret", result.report)
        self.assertIn("sudo: a password is required", result.report)
        self.assertEqual(fake_client.calls[-1][0], PRIVILEGED_NGINX_COMMAND)

    def test_privileged_button_uses_prompt_and_records_only_action_status(self) -> None:
        class DummyVar:
            def __init__(self, value: str = "") -> None:
                self.value = value

            def get(self) -> str:
                return self.value

            def set(self, value: str) -> None:
                self.value = value

        class ImmediateThread:
            def __init__(self, target, daemon: bool = False) -> None:
                self.target = target

            def start(self) -> None:
                self.target()

        dummy = db_update_wizard.WizardApp.__new__(db_update_wizard.WizardApp)
        dummy._maintenance_server_audit_running = False
        dummy._maintenance_server_audit_report = ""
        dummy.server_host = DummyVar("example.com")
        dummy.server_port = DummyVar("22")
        dummy.server_user = DummyVar("deploy")
        dummy.ssh_key_path = DummyVar("~/.ssh/id_ed25519")
        dummy.server_password = DummyVar("")
        dummy.maintenance_server_audit_status = DummyVar("Перевірку ще не виконано.")
        dummy.maintenance_server_audit_summary = DummyVar("")
        dummy.logged_messages: list[str] = []
        dummy.history_calls: list[tuple[tuple, dict]] = []

        dummy._begin_activity = lambda: None
        dummy._end_activity = lambda: None
        dummy._append_product_log = lambda text: dummy.logged_messages.append(text)
        dummy.after = lambda _delay, callback: callback()
        dummy._prompt_sudo_password = lambda: "sudo-secret"
        dummy.record_history = lambda *args, **kwargs: dummy.history_calls.append((args, kwargs))

        fake_result = SimpleNamespace(
            success=True,
            status="ok",
            summary="Привілейована перевірка успішна.",
            report="REPORT",
        )

        with patch.object(db_update_wizard, "audit_privileged_maintenance_server", return_value=fake_result), patch.object(
            db_update_wizard.threading, "Thread", ImmediateThread
        ), patch.object(db_update_wizard.messagebox, "showwarning") as warn_mock, patch.object(
            db_update_wizard.messagebox, "showerror"
        ) as error_mock:
            db_update_wizard.WizardApp.run_maintenance_server_audit_privileged(dummy)

        self.assertEqual(dummy.maintenance_server_audit_status.get(), "Готово: ok")
        self.assertEqual(dummy.maintenance_server_audit_summary.get(), "Привілейована перевірка успішна.")
        self.assertEqual(dummy._maintenance_server_audit_report, "REPORT")
        self.assertEqual(dummy.logged_messages, ["[Аудит сервера] Привілейована перевірка успішна."])
        self.assertEqual(dummy.history_calls, [(("maintenance.server_audit_privileged",), {"status": "ok"})])
        warn_mock.assert_not_called()
        error_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
