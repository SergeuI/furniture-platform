from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import product_center_launcher
from scripts import db_update_wizard


class ProductCenterRuntimeTests(unittest.TestCase):
    def test_launcher_prefers_repo_venv_python(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            root = Path(tmpdir)
            python_path = root / ".venv" / "Scripts" / "python.exe"
            python_path.parent.mkdir(parents=True, exist_ok=True)
            python_path.write_text("", encoding="utf-8")

            self.assertEqual(product_center_launcher._repo_python(root), python_path)

    def test_launcher_raises_when_repo_venv_python_missing(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            root = Path(tmpdir)

            with self.assertRaises(FileNotFoundError):
                product_center_launcher._repo_python(root)

    def test_product_center_runtime_resolves_repo_venv_python(self) -> None:
        expected = db_update_wizard.PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
        self.assertEqual(db_update_wizard.PYTHON, expected)

    def test_product_center_runtime_raises_when_repo_venv_python_missing(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            root = Path(tmpdir)

            with self.assertRaises(FileNotFoundError):
                db_update_wizard.resolve_repo_python(root)

    def test_start_local_api_skips_duplicate_launch_when_health_is_up(self) -> None:
        class DummyVar:
            def __init__(self, value: str = "") -> None:
                self.value = value

            def get(self) -> str:
                return self.value

            def set(self, value: str) -> None:
                self.value = value

        dummy = db_update_wizard.WizardApp.__new__(db_update_wizard.WizardApp)
        dummy.managed_processes = {}
        dummy.allow_local_registration_test_mode = DummyVar("false")
        dummy.allow_local_registration = DummyVar("false")
        dummy.main_db = DummyVar("D:\\PY\\furniture_platform.db")
        dummy.legacy_db = DummyVar("D:\\PY\\mebli_calculator.db")
        dummy.launch_status_var = DummyVar()
        dummy.logs: list[str] = []
        dummy.service_status_calls: list[tuple[str, str]] = []
        dummy.component_status_calls: list[tuple[str, str]] = []
        dummy.action_state_calls: list[tuple[str, str]] = []
        dummy.refresh_managed_processes = lambda: None
        dummy.refresh_product_status_async = lambda: None
        dummy._set_service_status = lambda key, status: dummy.service_status_calls.append((key, status))
        dummy._set_component_launch_status = lambda key, status: dummy.component_status_calls.append((key, status))
        dummy._set_action_button_state = lambda key, state: dummy.action_state_calls.append((key, state))
        dummy._set_launch_status = lambda text: dummy.launch_status_var.set(text)
        dummy._append_product_log = lambda text: dummy.logs.append(text)
        dummy.record_history = lambda *args, **kwargs: None

        with patch.object(db_update_wizard.WizardApp, "_service_responds", return_value=True), patch.object(
            db_update_wizard.WizardApp, "_start_managed_process"
        ) as start_mock:
            db_update_wizard.WizardApp.start_local_api(dummy)

        start_mock.assert_not_called()
        self.assertEqual(dummy.launch_status_var.get(), "Локальний API уже запущено.")
        self.assertIn(("api", "online"), dummy.service_status_calls)
        self.assertIn(("api", "online"), dummy.component_status_calls)
        self.assertIn(("api", "success"), dummy.action_state_calls)
        self.assertTrue(any("duplicate launch skipped" in line for line in dummy.logs))

    def test_refresh_product_status_marks_api_online_without_process_handle(self) -> None:
        class DummyVar:
            def __init__(self, value: str = "") -> None:
                self.value = value

            def get(self) -> str:
                return self.value

            def set(self, value: str) -> None:
                self.value = value

        dummy = db_update_wizard.WizardApp.__new__(db_update_wizard.WizardApp)
        dummy.managed_processes = {}
        dummy.service_status_calls: list[tuple[str, str]] = []
        dummy.component_status_calls: list[tuple[str, str]] = []
        dummy.action_state_calls: list[tuple[str, str]] = []
        dummy.logs: list[str] = []
        dummy.launch_status_var = DummyVar()
        dummy._bot_runtime_status = lambda running: "offline"
        dummy._set_service_status = lambda key, status: dummy.service_status_calls.append((key, status))
        dummy._set_component_launch_status = lambda key, status: dummy.component_status_calls.append((key, status))
        dummy._set_action_button_state = lambda key, state: dummy.action_state_calls.append((key, state))
        dummy._append_product_log = lambda text: dummy.logs.append(text)

        def fake_service_responds(url: str, timeout: float = 1.5) -> bool:
            return url == db_update_wizard.LOCAL_API_HEALTH_URL

        dummy._service_responds = fake_service_responds

        db_update_wizard.WizardApp.refresh_product_status(dummy)

        self.assertIn(("api", "online"), dummy.service_status_calls)
        self.assertIn(("api", "success"), dummy.action_state_calls)
        self.assertIn(("api", "online"), dummy.component_status_calls)

    def test_start_full_local_stack_counts_healthy_api_as_ready(self) -> None:
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
        dummy.managed_processes = {"bot": SimpleNamespace(poll=lambda: None), "api": None}
        dummy.launch_status_var = DummyVar()
        dummy.action_state_calls: list[tuple[str, str]] = []
        dummy.logs: list[str] = []
        dummy.after = lambda _delay, callback: callback()
        dummy._begin_activity = lambda: None
        dummy._end_activity = lambda: None
        dummy._append_product_log = lambda text: dummy.logs.append(text)
        dummy.record_history = lambda *args, **kwargs: None
        dummy._set_launch_status = lambda text: dummy.launch_status_var.set(text)
        dummy._set_action_button_state = lambda key, state: dummy.action_state_calls.append((key, state))
        dummy.start_all_local_services = lambda: None
        dummy.open_all_local_pages = lambda: None
        dummy.refresh_managed_processes = lambda: None
        dummy.refresh_product_status = lambda: None
        dummy._service_responds = lambda url, timeout=1.5: True

        with patch.object(db_update_wizard.threading, "Thread", ImmediateThread), patch.object(
            db_update_wizard.threading,
            "Event",
            side_effect=lambda: SimpleNamespace(wait=lambda *_args, **_kwargs: None),
        ):
            db_update_wizard.WizardApp.start_full_local_stack(dummy)

        self.assertIn(("start-full-stack", "success"), dummy.action_state_calls)
        self.assertTrue(dummy.launch_status_var.get())


if __name__ == "__main__":
    unittest.main()
