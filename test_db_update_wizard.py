import unittest
from unittest import mock

import scripts.db_update_wizard as wizard


class DummyVar:
    def __init__(self, value):
        self._value = value

    def get(self):
        return self._value

    def set(self, value):
        self._value = value


class DbUpdateWizardTests(unittest.TestCase):
    def _make_app(self, test_mode):
        app = object.__new__(wizard.WizardApp)
        app.main_db = DummyVar("D:/PY/furniture_platform.db")
        app.legacy_db = DummyVar("D:/PY/furniture_platform.db")
        app.allow_local_registration = DummyVar(False)
        app.allow_local_registration_test_mode = DummyVar(test_mode)
        app.launch_status_var = DummyVar("")
        app._service_health_refresh_inflight = False
        app._service_health_state = {"api": False, "app": False, "admin": False}
        app.service_status_vars = {}
        app.service_status_labels = {}
        app.component_launch_vars = {}
        app.component_launch_labels = {}
        app.component_launch_markers = {}
        app.managed_processes = {}
        app.record_history = mock.Mock()
        app._append_product_log = mock.Mock()
        return app

    @mock.patch.object(wizard.WizardApp, "_start_managed_process")
    @mock.patch.object(wizard.WizardApp, "_service_responds", return_value=False)
    @mock.patch.object(wizard, "python_command", return_value=["python", "main_api.py"])
    def test_start_local_api_enabled_passes_true_env_and_logs_state(self, python_command, service_responds, start_process):
        app = self._make_app(True)

        wizard.WizardApp.start_local_api(app)

        service_responds.assert_called_once_with(wizard.LOCAL_API_HEALTH_URL)
        start_process.assert_called_once()
        call_kwargs = start_process.call_args.kwargs
        self.assertEqual(call_kwargs["env"]["FURNITURE_REGISTRATION_LOCAL_TEST_MODE"], "true")
        self.assertEqual(call_kwargs["env"]["FURNITURE_ALLOW_LOCAL_PUBLIC_REGISTRATION"], "0")
        app.record_history.assert_called_once_with(
            "registration.test_mode",
            details="Local phone verification test mode: enabled",
            status="ok",
        )
        app._append_product_log.assert_called_once_with("Local phone verification test mode: enabled")

    @mock.patch.object(wizard.WizardApp, "_start_managed_process")
    @mock.patch.object(wizard.WizardApp, "_service_responds", return_value=False)
    @mock.patch.object(wizard, "python_command", return_value=["python", "main_api.py"])
    def test_start_local_api_disabled_passes_false_env_and_logs_state(self, python_command, service_responds, start_process):
        app = self._make_app(False)

        wizard.WizardApp.start_local_api(app)

        service_responds.assert_called_once_with(wizard.LOCAL_API_HEALTH_URL)
        start_process.assert_called_once()
        call_kwargs = start_process.call_args.kwargs
        self.assertEqual(call_kwargs["env"]["FURNITURE_REGISTRATION_LOCAL_TEST_MODE"], "false")
        app.record_history.assert_called_once_with(
            "registration.test_mode",
            details="Local phone verification test mode: disabled",
            status="ok",
        )
        app._append_product_log.assert_called_once_with("Local phone verification test mode: disabled")

    @mock.patch.object(wizard.WizardApp, "_start_managed_process")
    @mock.patch.object(wizard.WizardApp, "_service_responds", return_value=False)
    @mock.patch.object(wizard, "python_command", return_value=["python", "main_api.py"])
    def test_start_local_api_restarts_running_process_before_launch(self, python_command, service_responds, start_process):
        app = self._make_app(True)
        running_proc = mock.Mock()
        running_proc.poll.return_value = None
        app.managed_processes["api"] = running_proc

        wizard.WizardApp.start_local_api(app)

        service_responds.assert_called_once_with(wizard.LOCAL_API_HEALTH_URL)
        running_proc.terminate.assert_called_once()
        running_proc.wait.assert_called_once_with(timeout=5)
        start_process.assert_called_once()
        self.assertNotIn("api", app.managed_processes)

    @mock.patch.object(wizard, "discover_windows_listener_rows")
    @mock.patch.object(wizard, "discover_windows_process_rows")
    def test_discover_verified_stop_targets_includes_frontend_listeners_without_path(
        self,
        discover_process_rows,
        discover_listener_rows,
    ):
        app = self._make_app(True)
        discover_process_rows.return_value = [
            {
                "PID": 111,
                "ParentPID": None,
                "Name": "node",
                "ExecutablePath": "",
                "CreationDate": "",
                "CommandLine": "",
            },
            {
                "PID": 222,
                "ParentPID": None,
                "Name": "node",
                "ExecutablePath": "",
                "CreationDate": "",
                "CommandLine": "",
            },
        ]
        discover_listener_rows.return_value = [
            {"LocalPort": 5175, "OwningProcess": 111},
            {"LocalPort": 5173, "OwningProcess": 222},
        ]

        targets = wizard.WizardApp._discover_verified_stop_targets(app, include_history=False)

        self.assertEqual(targets["frontend-app"], {111})
        self.assertEqual(targets["frontend-admin"], {222})

    @mock.patch.object(wizard.WizardApp, "_start_managed_process")
    @mock.patch.object(wizard.WizardApp, "_service_responds", return_value=True)
    def test_start_app_frontend_skips_duplicate_launch_when_service_is_online(
        self,
        service_responds,
        start_process,
    ):
        app = self._make_app(True)
        app.refresh_managed_processes = mock.Mock()

        wizard.WizardApp.start_app_frontend(app)

        service_responds.assert_called_once_with(wizard.LOCAL_APP_URL)
        start_process.assert_not_called()
        app.refresh_managed_processes.assert_called_once()
        app._append_product_log.assert_called_once()

    @mock.patch.object(wizard.WizardApp, "_start_managed_process")
    @mock.patch.object(wizard.WizardApp, "_service_responds", return_value=True)
    def test_start_admin_frontend_skips_duplicate_launch_when_service_is_online(
        self,
        service_responds,
        start_process,
    ):
        app = self._make_app(True)
        app.refresh_managed_processes = mock.Mock()

        wizard.WizardApp.start_admin_frontend(app)

        service_responds.assert_called_once_with(wizard.LOCAL_ADMIN_URL)
        start_process.assert_not_called()
        app.refresh_managed_processes.assert_called_once()
        app._append_product_log.assert_called_once()

    @mock.patch.object(wizard, "safe_subprocess_kwargs", return_value={})
    @mock.patch.object(wizard.subprocess, "Popen")
    def test_start_managed_process_passes_env_to_popen(self, popen, safe_kwargs):
        app = object.__new__(wizard.WizardApp)
        app.managed_processes = {}
        app.action_buttons = {}
        app._set_action_button_state = mock.Mock()
        app._set_component_launch_status = mock.Mock()
        app._append_product_log = mock.Mock()
        app.record_history = mock.Mock()
        app.refresh_managed_processes = mock.Mock()
        app.refresh_product_status_async = mock.Mock()

        process = mock.Mock()
        process.pid = 12345
        process.poll.return_value = None
        process.returncode = None
        popen.return_value = process

        app._start_managed_process(
            "api",
            "Локальний API",
            ["python", "main_api.py"],
            env={"FURNITURE_REGISTRATION_LOCAL_TEST_MODE": "true"},
        )

        self.assertEqual(popen.call_args.kwargs["env"]["FURNITURE_REGISTRATION_LOCAL_TEST_MODE"], "true")
        self.assertIn("api", app.managed_processes)


if __name__ == "__main__":
    unittest.main()
