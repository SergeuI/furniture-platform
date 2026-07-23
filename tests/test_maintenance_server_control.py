from __future__ import annotations

import unittest
import hashlib
import shutil
from types import SimpleNamespace
from unittest.mock import patch

import scripts.db_update_wizard as wizard
import scripts.maintenance_server_control as control
from scripts.maintenance_server_audit import CommandResult


class FakeSFTP:
    def __init__(self) -> None:
        self.put_calls: list[tuple[str, str]] = []
        self.closed = False

    def put(self, localpath: str, remotepath: str) -> None:
        self.put_calls.append((localpath, remotepath))

    def close(self) -> None:
        self.closed = True


class FakeClient:
    def __init__(self) -> None:
        self.sftp = FakeSFTP()
        self.closed = False

    def open_sftp(self) -> FakeSFTP:
        return self.sftp

    def exec_command(self, command: str, get_pty: bool = False, timeout: float | None = None):
        if "test -f" in command:
            channel = SimpleNamespace(stdout_text="EXISTS", stderr_text="", exit_status=0)
        else:
            channel = SimpleNamespace(stdout_text="", stderr_text="", exit_status=0)
        stdin = SimpleNamespace(write=lambda *_: None, flush=lambda: None, close=lambda: None)
        stdout = SimpleNamespace(channel=channel)
        stderr = SimpleNamespace(read=lambda: b"")
        return stdin, stdout, stderr

    def close(self) -> None:
        self.closed = True


class VarStub:
    def __init__(self, value: str = "") -> None:
        self.value = value

    def set(self, value: object) -> None:
        self.value = str(value)

    def get(self) -> str:
        return self.value


class ControlUiStub:
    def __init__(self) -> None:
        self._maintenance_server_control_running = True
        self._maintenance_server_control_last_result = None
        self._maintenance_server_control_details_window = None
        self.maintenance_server_control_status = VarStub()
        self.maintenance_preview_status = VarStub()
        self.logs: list[str] = []
        self.history_calls: list[tuple[str, dict[str, object]]] = []

    def _end_activity(self) -> None:
        pass

    def _append_product_log(self, text: str) -> None:
        self.logs.append(text)

    def record_history(self, action: str, **kwargs: object) -> None:
        self.history_calls.append((action, kwargs))


class MaintenanceServerControlTests(unittest.TestCase):
    def test_build_server_package_renders_html_and_image(self) -> None:
        temp_dir, html_path, image_path = control.build_server_package(
            "Ми оновлюємо платформу. Ваші проєкти та дані збережені.",
            "Найближчим часом",
        )
        try:
            html_text = html_path.read_text(encoding="utf-8")
            self.assertTrue(html_path.exists())
            self.assertTrue(image_path.exists())
            self.assertGreater(image_path.stat().st_size, 0)
            self.assertIn("Ми оновлюємо платформу. Ваші проєкти та дані збережені.", html_text)
            self.assertIn("Найближчим часом", html_text)
            self.assertIn("/maintenance/maintenance-hero.png", html_text)
            self.assertNotIn("{{maintenance_message}}", html_text)
            self.assertNotIn("{{eta}}", html_text)
        finally:
            self.assertTrue(temp_dir.exists())

    def test_run_status_parses_complete_and_incomplete_output(self) -> None:
        complete_output = "\n".join(
            [
                "MAINTENANCE_ENABLED",
                "NGINX_STATUS=active",
                "PUBLIC_HTTP=503",
                "ADMIN_HTTP=503",
                "OPENAPI_HTTP=503",
                "IMAGE_HTTP=200",
            ]
        )
        incomplete_output = "\n".join(["NGINX_STATUS=active", "PUBLIC_HTTP=503"])

        with patch.object(control, "_open_paramiko_client", return_value=(FakeClient(), None)), patch.object(
            control,
            "_run_ssh_command_with_input",
            return_value=CommandResult(command=control.STATUS_COMMAND, exit_code=0, stdout=complete_output, stderr=""),
        ):
            result = control.run_status("host", "22", "user", "key", "server-pass", "sudo-pass")

        self.assertTrue(result.success)
        self.assertTrue(result.enabled)
        self.assertEqual(result.nginx_status, "active")
        self.assertEqual(result.public_http, 503)
        self.assertEqual(result.admin_http, 503)
        self.assertEqual(result.openapi_http, 503)
        self.assertEqual(result.image_http, 200)
        self.assertEqual(result.message, "Технічні роботи увімкнені.")

        fake_client = FakeClient()
        with patch.object(control, "_open_paramiko_client", return_value=(fake_client, None)), patch.object(
            control,
            "_run_ssh_command_with_input",
            return_value=CommandResult(command=control.STATUS_COMMAND, exit_code=0, stdout=incomplete_output, stderr=""),
        ):
            partial_result = control.run_status("host", "22", "user", "key", "server-pass", "sudo-pass")

        self.assertFalse(partial_result.success)
        self.assertIsNone(partial_result.enabled)
        self.assertIn("Відсутні дані", partial_result.message)

    def test_run_status_falls_back_on_checksum_mismatch(self) -> None:
        checksum_error = CommandResult(
            command=control.STATUS_COMMAND,
            exit_code=1,
            stdout="",
            stderr="ERROR: nginx config checksum differs",
        )

        with patch.object(control, "_open_paramiko_client", return_value=(FakeClient(), None)), patch.object(
            control,
            "_run_ssh_command_with_input",
            return_value=checksum_error,
        ), patch.object(
            control,
            "_run_ssh_command",
            return_value=CommandResult(command="systemctl is-active nginx", exit_code=0, stdout="active", stderr=""),
        ), patch.object(
            control,
            "_probe_public_http_statuses",
            return_value=(200, 200, 200, 200),
        ):
            result = control.run_status("host", "22", "user", "key", "server-pass", "sudo-pass")

        self.assertTrue(result.success)
        self.assertEqual(result.stage, "checksum_validation")
        self.assertFalse(result.enabled)
        self.assertEqual(result.status_label, "disabled")
        self.assertEqual(result.nginx_status, "active")
        self.assertEqual(result.public_http, 200)
        self.assertEqual(result.admin_http, 200)
        self.assertEqual(result.openapi_http, 200)
        self.assertEqual(result.image_http, 200)
        self.assertEqual(result.message, "Технічні роботи вимкнені.")
        self.assertNotIn("unknown", result.raw_output.lower())

    def test_maintenance_helpers_use_explicit_timeouts(self) -> None:
        fake_client = object()
        with patch.object(control, "_run_ssh_command_with_input", return_value=CommandResult(command="cmd", exit_code=0, stdout="", stderr="")) as input_mock, patch.object(
            control, "_run_ssh_command", return_value=CommandResult(command="cmd", exit_code=0, stdout="hash", stderr="")
        ) as ssh_mock:
            control._run_status_command(fake_client, "sudo-pass")
            control._run_enable_command(fake_client, "sudo-pass")
            control._run_disable_command(fake_client, "sudo-pass")
            control._install_remote_file(fake_client, "sudo-pass", "/tmp/src", "/tmp/dst")
            control._verify_placeholders_absent(fake_client, "sudo-pass", "/var/www/index.html")
            control._remote_sha256(fake_client, "/var/www/index.html")

        self.assertEqual(input_mock.call_args_list[0].kwargs["timeout_seconds"], control.STATUS_TIMEOUT_SECONDS)
        self.assertEqual(input_mock.call_args_list[1].kwargs["timeout_seconds"], control.ENABLE_TIMEOUT_SECONDS)
        self.assertEqual(input_mock.call_args_list[2].kwargs["timeout_seconds"], control.DISABLE_TIMEOUT_SECONDS)
        self.assertEqual(input_mock.call_args_list[3].kwargs["timeout_seconds"], control.PUBLISH_TIMEOUT_SECONDS)
        self.assertEqual(input_mock.call_args_list[4].kwargs["timeout_seconds"], control.PUBLISH_TIMEOUT_SECONDS)
        self.assertEqual(ssh_mock.call_args.kwargs["timeout_seconds"], control.PUBLISH_TIMEOUT_SECONDS)
        self.assertIn("grep -nF", input_mock.call_args_list[4].args[1])
        self.assertIn("{{title}}", input_mock.call_args_list[4].args[1])

    def test_publish_package_uses_staging_and_verifies_target_files(self) -> None:
        fake_client = FakeClient()
        temp_dir, html_path, image_path = control.build_server_package(
            "Ми оновлюємо платформу. Ваші проєкти та дані збережені.",
            "Найближчим часом",
        )
        local_html_hash = hashlib.sha256(html_path.read_bytes()).hexdigest()
        local_image_hash = hashlib.sha256(image_path.read_bytes()).hexdigest()
        shutil.rmtree(temp_dir, ignore_errors=True)
        remote_html = f"{control.REMOTE_WEBROOT}/index.html"
        remote_image = f"{control.REMOTE_WEBROOT}/maintenance-hero.png"

        with patch.object(control, "_install_remote_file", side_effect=[
            CommandResult(command="install-html", exit_code=0, stdout="ok", stderr=""),
            CommandResult(command="install-image", exit_code=0, stdout="ok", stderr=""),
        ]) as install_mock, patch.object(control, "_verify_remote_file", return_value=CommandResult(command="test", exit_code=0, stdout="EXISTS", stderr="")), patch.object(
            control, "_verify_placeholders_absent", return_value=CommandResult(command="grep", exit_code=1, stdout="", stderr="")), patch.object(
            control, "_remote_sha256", side_effect=[local_html_hash, local_image_hash]
        ):
            result = control.publish_maintenance_package(
                fake_client,
                "sudo-pass",
                "Ми оновлюємо платформу. Ваші проєкти та дані збережені.",
                "Найближчим часом",
            )

        self.assertTrue(result.success)
        self.assertTrue(result.sha256_match)
        self.assertEqual(fake_client.sftp.put_calls[0][1], f"{control.REMOTE_STAGING_DIR}/index.html")
        self.assertEqual(fake_client.sftp.put_calls[1][1], f"{control.REMOTE_STAGING_DIR}/maintenance-hero.png")
        self.assertEqual(result.remote_html_path, remote_html)
        self.assertEqual(result.remote_image_path, remote_image)
        self.assertEqual(install_mock.call_args_list[0].args[2], f"{control.REMOTE_STAGING_DIR}/index.html")
        self.assertEqual(install_mock.call_args_list[1].args[2], f"{control.REMOTE_STAGING_DIR}/maintenance-hero.png")
        self.assertNotIn("sudo-pass", result.raw_output)

    def test_enable_and_disable_orchestrate_command_flow(self) -> None:
        fake_client = FakeClient()
        publish_result = control.MaintenanceControlResult(
            action="publish",
            success=True,
            enabled=None,
            status_label="published",
            nginx_status="unknown",
            public_http=None,
            admin_http=None,
            openapi_http=None,
            image_http=None,
            message="Сторінку технічних робіт підготовлено.",
            raw_output="",
            local_html_path="C:/tmp/index.html",
            local_image_path="C:/tmp/maintenance-hero.png",
            remote_html_path="/var/www/furniture-maintenance/index.html",
            remote_image_path="/var/www/furniture-maintenance/maintenance-hero.png",
            sha256_match=True,
        )
        enable_status = control.CommandResult(
            command=control.STATUS_COMMAND,
            exit_code=0,
            stdout="\n".join(
                [
                    "MAINTENANCE_ENABLED",
                    "NGINX_STATUS=active",
                    "PUBLIC_HTTP=503",
                    "ADMIN_HTTP=503",
                    "OPENAPI_HTTP=503",
                    "IMAGE_HTTP=200",
                ]
            ),
            stderr="",
        )
        disable_status = control.CommandResult(
            command=control.STATUS_COMMAND,
            exit_code=0,
            stdout="\n".join(
                [
                    "MAINTENANCE_DISABLED",
                    "NGINX_STATUS=active",
                    "PUBLIC_HTTP=200",
                    "ADMIN_HTTP=200",
                    "OPENAPI_HTTP=200",
                    "IMAGE_HTTP=200",
                ]
            ),
            stderr="",
        )
        enable_command = CommandResult(command=control.ENABLE_COMMAND, exit_code=0, stdout="MAINTENANCE_ENABLE_OK", stderr="")
        disable_command = CommandResult(command=control.DISABLE_COMMAND, exit_code=0, stdout="MAINTENANCE_DISABLE_OK", stderr="")

        with patch.object(control, "_open_paramiko_client", return_value=(fake_client, None)), patch.object(
            control, "publish_maintenance_package", return_value=publish_result
        ) as publish_mock, patch.object(control, "_run_enable_command", return_value=enable_command) as enable_mock, patch.object(
            control, "_run_status_command", return_value=enable_status
        ) as status_mock:
            enable_result = control.run_enable(
                "host",
                "22",
                "user",
                "key",
                "server-pass",
                "sudo-pass",
                "Ми оновлюємо платформу. Ваші проєкти та дані збережені.",
                "Найближчим часом",
            )

        self.assertTrue(enable_result.success)
        self.assertTrue(enable_result.enabled)
        self.assertEqual(enable_result.action, "enable")
        self.assertEqual(enable_result.message, "MAINTENANCE_ENABLE_OK")
        publish_mock.assert_called_once()
        enable_mock.assert_called_once()
        status_mock.assert_called_once()

        with patch.object(control, "_open_paramiko_client", return_value=(fake_client, None)), patch.object(
            control, "_run_disable_command", return_value=disable_command
        ) as disable_mock, patch.object(control, "_run_status_command", return_value=disable_status) as disable_status_mock:
            disable_result = control.run_disable("host", "22", "user", "key", "server-pass", "sudo-pass")

        self.assertTrue(disable_result.success)
        self.assertFalse(disable_result.enabled)
        self.assertEqual(disable_result.action, "disable")
        self.assertEqual(disable_result.message, "MAINTENANCE_DISABLE_OK")
        disable_mock.assert_called_once()
        disable_status_mock.assert_called_once()

    def test_publish_package_reports_scp_upload_failure_stage(self) -> None:
        fake_client = FakeClient()
        with patch.object(fake_client, "open_sftp", side_effect=PermissionError("permission denied")):
            result = control.publish_maintenance_package(
                fake_client,
                "sudo-pass",
                "Ми оновлюємо платформу. Ваші проєкти та дані збережені.",
                "Найближчим часом",
            )

        self.assertFalse(result.success)
        self.assertEqual(result.stage, "scp_upload")
        self.assertIn("SCP", result.message)
        self.assertIn("permission denied", result.safe_stderr)
        self.assertNotIn("sudo-pass", result.raw_output)

    def test_publish_package_reports_sudo_install_failure_stage(self) -> None:
        fake_client = FakeClient()
        with patch.object(
            control,
            "_install_remote_file",
            side_effect=[
                CommandResult(command="install-html", exit_code=1, stdout="", stderr="install failed"),
            ],
        ):
            result = control.publish_maintenance_package(
                fake_client,
                "sudo-pass",
                "Ми оновлюємо платформу. Ваші проєкти та дані збережені.",
                "Найближчим часом",
            )

        self.assertFalse(result.success)
        self.assertEqual(result.stage, "sudo_install")
        self.assertIn("встановити файли", result.message)
        self.assertEqual(result.exit_code, 1)
        self.assertIn("install failed", result.safe_stderr)

    def test_publish_package_reports_sha_mismatch_stage(self) -> None:
        fake_client = FakeClient()
        temp_dir, html_path, image_path = control.build_server_package(
            "Ми оновлюємо платформу. Ваші проєкти та дані збережені.",
            "Найближчим часом",
        )
        local_html_hash = hashlib.sha256(html_path.read_bytes()).hexdigest()
        local_image_hash = hashlib.sha256(image_path.read_bytes()).hexdigest()
        shutil.rmtree(temp_dir, ignore_errors=True)

        with patch.object(
            control,
            "_install_remote_file",
            side_effect=[
                CommandResult(command="install-html", exit_code=0, stdout="ok", stderr=""),
                CommandResult(command="install-image", exit_code=0, stdout="ok", stderr=""),
            ],
        ), patch.object(
            control,
            "_verify_remote_file",
            return_value=CommandResult(command="test", exit_code=0, stdout="EXISTS", stderr=""),
        ), patch.object(
            control,
            "_verify_placeholders_absent",
            return_value=CommandResult(command="grep", exit_code=1, stdout="", stderr=""),
        ), patch.object(
            control,
            "_remote_sha256",
            side_effect=[local_html_hash, "deadbeef"],
        ):
            result = control.publish_maintenance_package(
                fake_client,
                "sudo-pass",
                "Ми оновлюємо платформу. Ваші проєкти та дані збережені.",
                "Найближчим часом",
            )

        self.assertFalse(result.success)
        self.assertEqual(result.stage, "sha256_validation")
        self.assertIn("Контрольні суми", result.message)
        self.assertEqual(result.local_html_sha256, local_html_hash)
        self.assertEqual(result.local_image_sha256, local_image_hash)
        self.assertEqual(result.remote_html_sha256, local_html_hash)
        self.assertEqual(result.remote_image_sha256, "deadbeef")

    def test_publish_package_reports_placeholder_failure_stage(self) -> None:
        fake_client = FakeClient()
        with patch.object(
            control,
            "_install_remote_file",
            side_effect=[
                CommandResult(command="install-html", exit_code=0, stdout="ok", stderr=""),
                CommandResult(command="install-image", exit_code=0, stdout="ok", stderr=""),
            ],
        ), patch.object(
            control,
            "_verify_remote_file",
            return_value=CommandResult(command="test", exit_code=0, stdout="EXISTS", stderr=""),
        ), patch.object(
            control,
            "_verify_placeholders_absent",
            return_value=CommandResult(command="grep", exit_code=0, stdout="placeholders remain", stderr="grep failed"),
        ), patch.object(
            control,
            "_remote_sha256",
            side_effect=["hash-a", "hash-b"],
        ):
            result = control.publish_maintenance_package(
                fake_client,
                "sudo-pass",
                "Ми оновлюємо платформу. Ваші проєкти та дані збережені.",
                "Найближчим часом",
            )

        self.assertFalse(result.success)
        self.assertEqual(result.stage, "remote_validation")
        self.assertIn("placeholders", result.message)
        self.assertIn("placeholders remain", result.safe_stdout)

    def test_publish_package_continues_when_placeholders_are_absent(self) -> None:
        fake_client = FakeClient()
        temp_dir, html_path, image_path = control.build_server_package(
            "РњРё РѕРЅРѕРІР»СЋС”РјРѕ РїР»Р°С‚С„РѕСЂРјСѓ. Р’Р°С€С– РїСЂРѕС”РєС‚Рё С‚Р° РґР°РЅС– Р·Р±РµСЂРµР¶РµРЅС–.",
            "РќР°Р№Р±Р»РёР¶С‡РёРј С‡Р°СЃРѕРј",
        )
        local_html_hash = hashlib.sha256(html_path.read_bytes()).hexdigest()
        local_image_hash = hashlib.sha256(image_path.read_bytes()).hexdigest()
        shutil.rmtree(temp_dir, ignore_errors=True)
        with patch.object(
            control,
            "_install_remote_file",
            side_effect=[
                CommandResult(command="install-html", exit_code=0, stdout="ok", stderr=""),
                CommandResult(command="install-image", exit_code=0, stdout="ok", stderr=""),
            ],
        ), patch.object(
            control,
            "_verify_remote_file",
            return_value=CommandResult(command="test", exit_code=0, stdout="EXISTS", stderr=""),
        ), patch.object(
            control,
            "_verify_placeholders_absent",
            return_value=CommandResult(command="grep", exit_code=1, stdout="", stderr=""),
        ), patch.object(
            control,
            "_remote_sha256",
            side_effect=[local_html_hash, local_image_hash],
        ):
            result = control.publish_maintenance_package(
                fake_client,
                "sudo-pass",
                "РњРё РѕРЅРѕРІР»СЋС”РјРѕ РїР»Р°С‚С„РѕСЂРјСѓ. Р’Р°С€С– РїСЂРѕС”РєС‚Рё С‚Р° РґР°РЅС– Р·Р±РµСЂРµР¶РµРЅС–.",
                "РќР°Р№Р±Р»РёР¶С‡РёРј С‡Р°СЃРѕРј",
            )

        self.assertTrue(result.success)
        self.assertEqual(result.stage, "cleanup")
        self.assertEqual(result.remote_html_sha256, local_html_hash)
        self.assertEqual(result.remote_image_sha256, local_image_hash)

    def test_publish_package_reports_placeholder_grep_error_stage(self) -> None:
        fake_client = FakeClient()
        with patch.object(
            control,
            "_install_remote_file",
            side_effect=[
                CommandResult(command="install-html", exit_code=0, stdout="ok", stderr=""),
                CommandResult(command="install-image", exit_code=0, stdout="ok", stderr=""),
            ],
        ), patch.object(
            control,
            "_verify_remote_file",
            return_value=CommandResult(command="test", exit_code=0, stdout="EXISTS", stderr=""),
        ), patch.object(
            control,
            "_verify_placeholders_absent",
            return_value=CommandResult(command="grep", exit_code=2, stdout="", stderr="grep: Invalid content of {}"),
        ), patch.object(
            control,
            "_remote_sha256",
            side_effect=["hash-a", "hash-b"],
        ):
            result = control.publish_maintenance_package(
                fake_client,
                "sudo-pass",
                "РњРё РѕРЅРѕРІР»СЋС”РјРѕ РїР»Р°С‚С„РѕСЂРјСѓ. Р’Р°С€С– РїСЂРѕС”РєС‚Рё С‚Р° РґР°РЅС– Р·Р±РµСЂРµР¶РµРЅС–.",
                "РќР°Р№Р±Р»РёР¶С‡РёРј С‡Р°СЃРѕРј",
            )

        self.assertFalse(result.success)
        self.assertEqual(result.stage, "remote_validation")
        self.assertIn("placeholders", result.message.lower())
        self.assertIn("grep: Invalid content of {}", result.safe_stderr)

    def test_publish_package_tolerates_stderr_when_exit_code_is_zero(self) -> None:
        fake_client = FakeClient()
        temp_dir, html_path, image_path = control.build_server_package(
            "Ми оновлюємо платформу. Ваші проєкти та дані збережені.",
            "Найближчим часом",
        )
        local_html_hash = hashlib.sha256(html_path.read_bytes()).hexdigest()
        local_image_hash = hashlib.sha256(image_path.read_bytes()).hexdigest()
        shutil.rmtree(temp_dir, ignore_errors=True)
        with patch.object(
            control,
            "_install_remote_file",
            side_effect=[
                CommandResult(command="install-html", exit_code=0, stdout="ok", stderr="warning one"),
                CommandResult(command="install-image", exit_code=0, stdout="ok", stderr="warning two"),
            ],
        ), patch.object(
            control,
            "_verify_remote_file",
            return_value=CommandResult(command="test", exit_code=0, stdout="EXISTS", stderr="notice"),
        ), patch.object(
            control,
            "_verify_placeholders_absent",
            return_value=CommandResult(command="grep", exit_code=1, stdout="", stderr="still ok"),
        ), patch.object(
            control,
            "_remote_sha256",
            side_effect=[local_html_hash, local_image_hash],
        ):
            result = control.publish_maintenance_package(
                fake_client,
                "sudo-pass",
                "Ми оновлюємо платформу. Ваші проєкти та дані збережені.",
                "Найближчим часом",
            )

        self.assertTrue(result.success)
        self.assertEqual(result.stage, "cleanup")
        self.assertIn("warning one", result.safe_stderr)
        self.assertIn("warning two", result.safe_stderr)
        self.assertNotIn("sudo-pass", result.safe_stdout)

    def test_publish_package_does_not_leak_password_in_outputs(self) -> None:
        fake_client = FakeClient()
        temp_dir, html_path, image_path = control.build_server_package(
            "Ми оновлюємо платформу. Ваші проєкти та дані збережені.",
            "Найближчим часом",
        )
        local_html_hash = hashlib.sha256(html_path.read_bytes()).hexdigest()
        local_image_hash = hashlib.sha256(image_path.read_bytes()).hexdigest()
        shutil.rmtree(temp_dir, ignore_errors=True)
        with patch.object(
            control,
            "_install_remote_file",
            side_effect=[
                CommandResult(command="install-html", exit_code=0, stdout="ok", stderr=""),
                CommandResult(command="install-image", exit_code=0, stdout="ok", stderr=""),
            ],
        ), patch.object(
            control,
            "_verify_remote_file",
            return_value=CommandResult(command="test", exit_code=0, stdout="EXISTS", stderr=""),
        ), patch.object(
            control,
            "_verify_placeholders_absent",
            return_value=CommandResult(command="grep", exit_code=1, stdout="", stderr=""),
        ), patch.object(
            control,
            "_remote_sha256",
            side_effect=[local_html_hash, local_image_hash],
        ):
            result = control.publish_maintenance_package(
                fake_client,
                "super-secret-password",
                "Ми оновлюємо платформу. Ваші проєкти та дані збережені.",
                "Найближчим часом",
            )

        for field in (
            result.message,
            result.raw_output,
            result.safe_stdout,
            result.safe_stderr,
        ):
            self.assertNotIn("super-secret-password", field)

    def test_finish_maintenance_server_control_records_publish_stage(self) -> None:
        stub = ControlUiStub()
        result = SimpleNamespace(
            action="publish",
            success=False,
            enabled=None,
            status_label="error",
            stage="scp_upload",
            exit_code=1,
            safe_stdout="uploading",
            safe_stderr="permission denied",
            nginx_status="unknown",
            public_http=None,
            admin_http=None,
            openapi_http=None,
            image_http=None,
            message="Не вдалося завантажити файли через SCP.",
            raw_output="uploading\npermission denied",
            local_html_sha256="hash-a",
            local_image_sha256="hash-b",
            remote_html_sha256=None,
            remote_image_sha256=None,
            local_html_path="C:/tmp/index.html",
            local_image_path="C:/tmp/maintenance-hero.png",
            remote_html_path="/var/www/furniture-maintenance/index.html",
            remote_image_path="/var/www/furniture-maintenance/maintenance-hero.png",
            sha256_match=None,
        )

        with patch.object(wizard.messagebox, "showwarning"), patch.object(wizard.messagebox, "showerror"):
            wizard.WizardApp._finish_maintenance_server_control(stub, result=result)

        self.assertFalse(stub._maintenance_server_control_running)
        self.assertIs(stub._maintenance_server_control_last_result, result)
        self.assertIn("stage=scp_upload", stub.maintenance_server_control_status.get())
        self.assertIn("exit=1", stub.maintenance_server_control_status.get())
        self.assertTrue(any("maintenance.publish" in log for log in stub.logs))
        self.assertTrue(stub.history_calls)
        action, payload = stub.history_calls[0]
        self.assertEqual(action, "maintenance.publish")
        self.assertEqual(payload["status"], "error")
        self.assertIn("scp_upload", str(payload["details"]))

    def test_run_enable_stops_after_publish_failure(self) -> None:
        fake_client = FakeClient()
        publish_result = control.MaintenanceControlResult(
            action="publish",
            success=False,
            enabled=None,
            status_label="error",
            stage="scp_upload",
            exit_code=1,
            safe_stdout="",
            safe_stderr="permission denied",
            nginx_status="unknown",
            public_http=None,
            admin_http=None,
            openapi_http=None,
            image_http=None,
            message="Не вдалося завантажити файли через SCP.",
            raw_output="permission denied",
            local_html_path="C:/tmp/index.html",
            local_image_path="C:/tmp/maintenance-hero.png",
            remote_html_path="/var/www/furniture-maintenance/index.html",
            remote_image_path="/var/www/furniture-maintenance/maintenance-hero.png",
            sha256_match=None,
        )

        with patch.object(control, "_open_paramiko_client", return_value=(fake_client, None)), patch.object(
            control, "publish_maintenance_package", return_value=publish_result
        ), patch.object(control, "_run_enable_command") as enable_mock, patch.object(
            control, "_run_status_command"
        ) as status_mock:
            result = control.run_enable(
                "host",
                "22",
                "user",
                "key",
                "server-pass",
                "sudo-pass",
                "Ми оновлюємо платформу. Ваші проєкти та дані збережені.",
                "Найближчим часом",
            )

        self.assertIs(result, publish_result)
        enable_mock.assert_not_called()
        status_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
