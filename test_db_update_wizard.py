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
        app.managed_processes = {}
        app.record_history = mock.Mock()
        app._append_product_log = mock.Mock()
        return app

    @mock.patch.object(wizard.WizardApp, "_start_managed_process")
    @mock.patch.object(wizard, "python_command", return_value=["python", "main_api.py"])
    def test_start_local_api_enabled_passes_true_env_and_logs_state(self, python_command, start_process):
        app = self._make_app(True)

        wizard.WizardApp.start_local_api(app)

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
    @mock.patch.object(wizard, "python_command", return_value=["python", "main_api.py"])
    def test_start_local_api_disabled_passes_false_env_and_logs_state(self, python_command, start_process):
        app = self._make_app(False)

        wizard.WizardApp.start_local_api(app)

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
    @mock.patch.object(wizard, "python_command", return_value=["python", "main_api.py"])
    def test_start_local_api_restarts_running_process_before_launch(self, python_command, start_process):
        app = self._make_app(True)
        running_proc = mock.Mock()
        running_proc.poll.return_value = None
        app.managed_processes["api"] = running_proc

        wizard.WizardApp.start_local_api(app)

        running_proc.terminate.assert_called_once()
        running_proc.wait.assert_called_once_with(timeout=5)
        start_process.assert_called_once()
        self.assertNotIn("api", app.managed_processes)

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
