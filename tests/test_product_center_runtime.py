from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import product_center_launcher
from sqlalchemy import create_engine
from scripts import db_update_wizard
from scripts import upgrade_fittings_foundation_schema


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

    def test_launcher_relaunches_as_admin_when_not_elevated(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            root = Path(tmpdir)
            script = root / "product_center.pyw"
            python_path = root / ".venv" / "Scripts" / "pythonw.exe"
            script.write_text("print('ok')", encoding="utf-8")
            python_path.parent.mkdir(parents=True, exist_ok=True)
            python_path.write_text("", encoding="utf-8")

            with patch.object(product_center_launcher, "project_root", return_value=root), patch.object(
                product_center_launcher, "_repo_python", return_value=python_path
            ), patch.object(product_center_launcher, "_is_windows_admin", return_value=False), patch.object(
                product_center_launcher, "_shell_runas", return_value=33
            ) as shell_runas, patch.object(product_center_launcher.subprocess, "Popen") as popen:
                exit_code = product_center_launcher.launch()

        self.assertEqual(exit_code, 0)
        shell_runas.assert_called_once()
        popen.assert_not_called()

    def test_launcher_starts_directly_when_already_elevated(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            root = Path(tmpdir)
            script = root / "product_center.pyw"
            python_path = root / ".venv" / "Scripts" / "pythonw.exe"
            script.write_text("print('ok')", encoding="utf-8")
            python_path.parent.mkdir(parents=True, exist_ok=True)
            python_path.write_text("", encoding="utf-8")

            process = SimpleNamespace()
            with patch.object(product_center_launcher, "project_root", return_value=root), patch.object(
                product_center_launcher, "_repo_python", return_value=python_path
            ), patch.object(product_center_launcher, "_is_windows_admin", return_value=True), patch.object(
                product_center_launcher.subprocess, "Popen", return_value=process
            ) as popen:
                exit_code = product_center_launcher.launch()

        self.assertEqual(exit_code, 0)
        popen.assert_called_once()

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
        self.assertIn("API", dummy.launch_status_var.get())
        self.assertIn(("api", "online"), dummy.service_status_calls)
        self.assertIn(("api", "online"), dummy.component_status_calls)
        self.assertIn(("api", "success"), dummy.action_state_calls)
        self.assertTrue(any("duplicate launch skipped" in line for line in dummy.logs))

    def test_start_local_api_keeps_tracked_live_process_when_health_is_up(self) -> None:
        class DummyVar:
            def __init__(self, value: str = "") -> None:
                self.value = value

            def get(self) -> str:
                return self.value

            def set(self, value: str) -> None:
                self.value = value

        class LiveProc:
            def __init__(self) -> None:
                self.pid = 222
                self.terminated = False
                self.waited = False
                self.killed = False

            def poll(self) -> int | None:
                return None

            def terminate(self) -> None:
                self.terminated = True

            def wait(self, timeout: float = 5) -> None:
                self.waited = True

            def kill(self) -> None:
                self.killed = True

        live_proc = LiveProc()
        dummy = db_update_wizard.WizardApp.__new__(db_update_wizard.WizardApp)
        dummy.managed_processes = {"api": live_proc}
        dummy.allow_local_registration_test_mode = DummyVar("false")
        dummy.allow_local_registration = DummyVar("false")
        dummy.main_db = DummyVar("D:\\PY\\furniture_platform.db")
        dummy.legacy_db = DummyVar("D:\\PY\\mebli_calculator.db")
        dummy.logs: list[str] = []
        dummy.service_status_calls: list[tuple[str, str]] = []
        dummy.component_status_calls: list[tuple[str, str]] = []
        dummy.action_state_calls: list[tuple[str, str]] = []
        dummy.refresh_managed_processes = lambda: None
        dummy.refresh_product_status_async = lambda: None
        dummy._set_service_status = lambda key, status: dummy.service_status_calls.append((key, status))
        dummy._set_component_launch_status = lambda key, status: dummy.component_status_calls.append((key, status))
        dummy._set_action_button_state = lambda key, state: dummy.action_state_calls.append((key, state))
        dummy._set_launch_status = lambda text: None
        dummy._append_product_log = lambda text: dummy.logs.append(text)
        dummy.record_history = lambda *args, **kwargs: None

        with patch.object(db_update_wizard.WizardApp, "_service_responds", return_value=True), patch.object(
            db_update_wizard.WizardApp,
            "_start_managed_process",
        ) as start_mock:
            db_update_wizard.WizardApp.start_local_api(dummy)

        start_mock.assert_not_called()
        self.assertFalse(live_proc.terminated)
        self.assertFalse(live_proc.waited)
        self.assertFalse(live_proc.killed)
        self.assertIs(dummy.managed_processes["api"], live_proc)
        self.assertIn(("api", "online"), dummy.service_status_calls)
        self.assertIn(("api", "success"), dummy.action_state_calls)

    def test_start_local_api_skips_spawn_when_healthy_and_untracked(self) -> None:
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
        dummy.logs: list[str] = []
        dummy.service_status_calls: list[tuple[str, str]] = []
        dummy.component_status_calls: list[tuple[str, str]] = []
        dummy.action_state_calls: list[tuple[str, str]] = []
        dummy.refresh_managed_processes = lambda: None
        dummy.refresh_product_status_async = lambda: None
        dummy._set_service_status = lambda key, status: dummy.service_status_calls.append((key, status))
        dummy._set_component_launch_status = lambda key, status: dummy.component_status_calls.append((key, status))
        dummy._set_action_button_state = lambda key, state: dummy.action_state_calls.append((key, state))
        dummy._set_launch_status = lambda text: None
        dummy._append_product_log = lambda text: dummy.logs.append(text)
        dummy.record_history = lambda *args, **kwargs: None

        with patch.object(db_update_wizard.WizardApp, "_service_responds", return_value=True), patch.object(
            db_update_wizard.WizardApp,
            "_start_managed_process",
        ) as start_mock:
            db_update_wizard.WizardApp.start_local_api(dummy)

        start_mock.assert_not_called()
        self.assertIn(("api", "online"), dummy.service_status_calls)
        self.assertIn(("api", "success"), dummy.action_state_calls)
        self.assertTrue(any("duplicate launch skipped" in line for line in dummy.logs))

    def test_start_local_api_restarts_stale_managed_api_when_health_is_offline(self) -> None:
        class DummyVar:
            def __init__(self, value: str = "") -> None:
                self.value = value

            def get(self) -> str:
                return self.value

            def set(self, value: str) -> None:
                self.value = value

        class StaleProc:
            def __init__(self) -> None:
                self.pid = 333
                self.terminated = False

            def poll(self) -> int | None:
                return 1

            def terminate(self) -> None:
                self.terminated = True

        stale_proc = StaleProc()
        dummy = db_update_wizard.WizardApp.__new__(db_update_wizard.WizardApp)
        dummy.managed_processes = {"api": stale_proc}
        dummy.allow_local_registration_test_mode = DummyVar("false")
        dummy.allow_local_registration = DummyVar("false")
        dummy.main_db = DummyVar("D:\\PY\\furniture_platform.db")
        dummy.legacy_db = DummyVar("D:\\PY\\mebli_calculator.db")
        dummy.logs: list[str] = []
        dummy.record_history = lambda *args, **kwargs: None
        dummy._append_product_log = lambda text: dummy.logs.append(text)
        dummy.refresh_managed_processes = lambda: None
        dummy.refresh_product_status_async = lambda: None

        with patch.object(db_update_wizard.WizardApp, "_service_responds", return_value=False), patch.object(
            db_update_wizard.WizardApp,
            "_start_managed_process",
        ) as start_mock:
            db_update_wizard.WizardApp.start_local_api(dummy)

        start_mock.assert_called_once()
        self.assertFalse(stale_proc.terminated)

    def test_start_full_local_stack_keeps_healthy_api_alive_without_spawn(self) -> None:
        class DummyVar:
            def __init__(self, value: str = "") -> None:
                self.value = value

            def get(self) -> str:
                return self.value

            def set(self, value: str) -> None:
                self.value = value

        class LiveProc:
            def __init__(self, pid: int) -> None:
                self.pid = pid
                self.terminated = False

            def poll(self) -> int | None:
                return None

            def terminate(self) -> None:
                self.terminated = True

        class ImmediateThread:
            def __init__(self, target, daemon: bool = False) -> None:
                self.target = target

            def start(self) -> None:
                self.target()

        api_proc = LiveProc(21736)
        bot_proc = LiveProc(20896)
        dummy = db_update_wizard.WizardApp.__new__(db_update_wizard.WizardApp)
        dummy.managed_processes = {"api": api_proc, "bot": bot_proc}
        dummy.allow_local_registration_test_mode = DummyVar("false")
        dummy.allow_local_registration = DummyVar("false")
        dummy.main_db = DummyVar("D:\\PY\\furniture_platform.db")
        dummy.legacy_db = DummyVar("D:\\PY\\mebli_calculator.db")
        dummy.launch_status_var = DummyVar()
        dummy.logs: list[str] = []
        dummy.action_state_calls: list[tuple[str, str]] = []
        dummy.service_status_calls: list[tuple[str, str]] = []
        dummy.component_status_calls: list[tuple[str, str]] = []
        dummy.after = lambda _delay, callback: callback()
        dummy._begin_activity = lambda: None
        dummy._end_activity = lambda: None
        dummy._append_product_log = lambda text: dummy.logs.append(text)
        dummy.record_history = lambda *args, **kwargs: None
        dummy.refresh_managed_processes = lambda: None
        dummy.refresh_product_status = lambda: None
        dummy.open_all_local_pages = lambda: None
        dummy.start_local_bot = lambda: None
        dummy.start_app_frontend = lambda: None
        dummy.start_admin_frontend = lambda: None
        dummy._service_responds = lambda url, timeout=1.5: True

        with patch.object(db_update_wizard.threading, "Thread", ImmediateThread), patch.object(
            db_update_wizard.threading,
            "Event",
            side_effect=lambda: SimpleNamespace(wait=lambda *_args, **_kwargs: None),
        ), patch.object(
            db_update_wizard.WizardApp,
            "_set_launch_status",
            lambda self, text: dummy.launch_status_var.set(text),
        ), patch.object(
            db_update_wizard.WizardApp,
            "_set_action_button_state",
            lambda self, key, state: dummy.action_state_calls.append((key, state)),
        ), patch.object(
            db_update_wizard.WizardApp,
            "_set_service_status",
            lambda self, key, status: dummy.service_status_calls.append((key, status)),
        ), patch.object(
            db_update_wizard.WizardApp,
            "_set_component_launch_status",
            lambda self, key, status: dummy.component_status_calls.append((key, status)),
        ), patch.object(
            db_update_wizard.WizardApp,
            "refresh_product_status_async",
            lambda self: None,
        ), patch.object(db_update_wizard.WizardApp, "_start_managed_process") as start_mock:
            db_update_wizard.WizardApp.start_full_local_stack(dummy)

        start_mock.assert_not_called()
        self.assertFalse(api_proc.terminated)
        self.assertIn(("start-full-stack", "success"), dummy.action_state_calls)

    def test_api_startup_redirects_stdio_only_for_api(self) -> None:
        class DummyVar:
            def __init__(self, value: str = "") -> None:
                self.value = value

            def get(self) -> str:
                return self.value

            def set(self, value: str) -> None:
                self.value = value

        class DummyProc:
            pid = 12345

            def poll(self) -> int | None:
                return None

        captured: list[dict[str, object]] = []

        def fake_popen(*args, **kwargs):
            captured.append({"args": args, "kwargs": kwargs})
            return DummyProc()

        dummy = db_update_wizard.WizardApp.__new__(db_update_wizard.WizardApp)
        dummy.managed_processes = {}
        dummy.allow_local_registration_test_mode = DummyVar("false")
        dummy.allow_local_registration = DummyVar("false")
        dummy.main_db = DummyVar("D:\\PY\\furniture_platform.db")
        dummy.legacy_db = DummyVar("D:\\PY\\mebli_calculator.db")
        dummy.logs: list[str] = []
        dummy.refresh_managed_processes = lambda: None
        dummy.refresh_product_status = lambda: None
        dummy.refresh_product_status_async = lambda: None
        dummy._set_action_button_state = lambda key, state: None
        dummy._set_component_launch_status = lambda key, status: None
        dummy._append_product_log = lambda text: dummy.logs.append(text)
        dummy.record_history = lambda *args, **kwargs: None
        dummy._service_responds = lambda url, timeout=1.5: False

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            log_path = Path(tmpdir) / "product_center_api.log"
            with patch.object(db_update_wizard, "API_STARTUP_LOG_PATH", log_path), patch.object(
                db_update_wizard.subprocess, "Popen", side_effect=fake_popen
            ):
                db_update_wizard.WizardApp.start_local_api(dummy)
                db_update_wizard.WizardApp._start_managed_process(
                    dummy,
                    "bot",
                    "Локальний бот",
                    [str(db_update_wizard.PYTHON), str(db_update_wizard.PROJECT_ROOT / "main.py")],
                )

            self.assertTrue(log_path.exists())
            self.assertIn("Launch:", log_path.read_text(encoding="utf-8"))
            api_call = captured[0]["kwargs"]
            bot_call = captured[1]["kwargs"]
            self.assertNotEqual(api_call["stdout"], db_update_wizard.subprocess.DEVNULL)
            self.assertEqual(api_call["stdout"], api_call["stderr"])
            self.assertEqual(bot_call["stdout"], db_update_wizard.subprocess.DEVNULL)
            self.assertEqual(bot_call["stderr"], db_update_wizard.subprocess.DEVNULL)
            self.assertEqual(captured[0]["args"][0][1], str(db_update_wizard.PROJECT_ROOT / "main_api.py"))

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
        dummy._service_health_state = {"api": None, "app": None, "admin": None}
        dummy._service_health_refresh_inflight = False
        dummy.service_status_calls: list[tuple[str, str]] = []
        dummy.component_status_calls: list[tuple[str, str]] = []
        dummy.action_state_calls: list[tuple[str, str]] = []
        dummy.logs: list[str] = []
        dummy.launch_status_var = DummyVar()
        dummy._bot_runtime_status = lambda running: "offline"
        dummy.after = lambda _delay, callback: callback()
        dummy._set_service_status = lambda key, status: dummy.service_status_calls.append((key, status))
        dummy._set_component_launch_status = lambda key, status: dummy.component_status_calls.append((key, status))
        dummy._set_action_button_state = lambda key, state: dummy.action_state_calls.append((key, state))
        dummy._append_product_log = lambda text: dummy.logs.append(text)

        def fake_service_responds(url: str, timeout: float = 1.5) -> bool:
            return url == db_update_wizard.LOCAL_API_HEALTH_URL

        dummy._service_responds = fake_service_responds

        class ImmediateThread:
            def __init__(self, target, daemon: bool = False) -> None:
                self.target = target

            def start(self) -> None:
                self.target()

        with patch.object(db_update_wizard.threading, "Thread", ImmediateThread):
            db_update_wizard.WizardApp.refresh_product_status_async(dummy)

        self.assertIn(("api", "online"), dummy.service_status_calls)
        self.assertIn(("api", "success"), dummy.action_state_calls)
        self.assertIn(("api", "online"), dummy.component_status_calls)

    def test_managed_button_state_uses_cached_health_without_process_handle(self) -> None:
        dummy = db_update_wizard.WizardApp.__new__(db_update_wizard.WizardApp)
        dummy._service_health_state = {"api": True, "app": True, "admin": True}

        self.assertEqual(db_update_wizard.WizardApp._managed_button_state(dummy, "frontend-app", None), "success")
        self.assertEqual(db_update_wizard.WizardApp._managed_button_state(dummy, "frontend-admin", None), "success")
        self.assertEqual(db_update_wizard.WizardApp._managed_button_state(dummy, "api", None), "success")
        self.assertEqual(db_update_wizard.WizardApp._managed_button_state(dummy, "bot", None), "idle")

    def test_refresh_managed_processes_keeps_online_buttons_green_without_handles(self) -> None:
        class DummyListbox:
            def delete(self, *_args, **_kwargs) -> None:
                pass

            def insert(self, *_args, **_kwargs) -> None:
                pass

            def size(self) -> int:
                return 0

            def itemconfig(self, *_args, **_kwargs) -> None:
                pass

        dummy = db_update_wizard.WizardApp.__new__(db_update_wizard.WizardApp)
        dummy.managed_processes = {}
        dummy.action_buttons = {
            "api": [object()],
            "bot": [object()],
            "frontend-app": [object()],
            "frontend-admin": [object()],
        }
        dummy.process_list_colors_enabled = False
        dummy._service_health_state = {"api": True, "app": True, "admin": True}
        dummy._set_action_button_state_calls: list[tuple[str, str]] = []
        dummy.process_list = DummyListbox()
        dummy._set_action_button_state = lambda key, state: dummy._set_action_button_state_calls.append((key, state))
        dummy._set_component_launch_status = lambda *_args, **_kwargs: None
        dummy._process_list_colors = lambda status: ("#fff", "#000")

        db_update_wizard.WizardApp.refresh_managed_processes(dummy)

        self.assertIn(("api", "success"), dummy._set_action_button_state_calls)
        self.assertIn(("frontend-app", "success"), dummy._set_action_button_state_calls)
        self.assertIn(("frontend-admin", "success"), dummy._set_action_button_state_calls)
        self.assertIn(("bot", "idle"), dummy._set_action_button_state_calls)
        self.assertNotIn(("frontend-app", "idle"), dummy._set_action_button_state_calls)
        self.assertNotIn(("frontend-admin", "idle"), dummy._set_action_button_state_calls)

    def test_refresh_managed_processes_keeps_stale_online_buttons_green(self) -> None:
        class DummyListbox:
            def delete(self, *_args, **_kwargs) -> None:
                pass

            def insert(self, *_args, **_kwargs) -> None:
                pass

            def size(self) -> int:
                return 0

            def itemconfig(self, *_args, **_kwargs) -> None:
                pass

        stale_proc = SimpleNamespace(poll=lambda: 1, returncode=7, pid=4321)
        dummy = db_update_wizard.WizardApp.__new__(db_update_wizard.WizardApp)
        dummy.managed_processes = {"frontend-admin": stale_proc}
        dummy.action_buttons = {"frontend-admin": [object()]}
        dummy.process_list_colors_enabled = False
        dummy._service_health_state = {"api": False, "app": False, "admin": True}
        dummy._set_action_button_state_calls: list[tuple[str, str]] = []
        dummy.process_list = DummyListbox()
        dummy._set_action_button_state = lambda key, state: dummy._set_action_button_state_calls.append((key, state))
        dummy._set_component_launch_status = lambda *_args, **_kwargs: None
        dummy._process_list_colors = lambda status: ("#fff", "#000")

        db_update_wizard.WizardApp.refresh_managed_processes(dummy)

        self.assertIn(("frontend-admin", "success"), dummy._set_action_button_state_calls)
        self.assertNotIn(("frontend-admin", "idle"), dummy._set_action_button_state_calls)

    def test_managed_button_state_stays_idle_when_health_is_offline_and_no_process(self) -> None:
        dummy = db_update_wizard.WizardApp.__new__(db_update_wizard.WizardApp)
        dummy._service_health_state = {"api": None, "app": False, "admin": False}

        self.assertEqual(db_update_wizard.WizardApp._managed_button_state(dummy, "frontend-app", None), "idle")
        self.assertEqual(db_update_wizard.WizardApp._managed_button_state(dummy, "frontend-admin", None), "idle")

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
        dummy.service_status_calls: list[tuple[str, str]] = []
        dummy.component_status_calls: list[tuple[str, str]] = []
        dummy.logs: list[str] = []
        dummy.after = lambda _delay, callback: callback()
        dummy._begin_activity = lambda: None
        dummy._end_activity = lambda: None
        dummy._append_product_log = lambda text: dummy.logs.append(text)
        dummy.record_history = lambda *args, **kwargs: None
        dummy._set_launch_status = lambda text: dummy.launch_status_var.set(text)
        dummy._set_action_button_state = lambda key, state: dummy.action_state_calls.append((key, state))
        dummy._set_service_status = lambda key, status: dummy.service_status_calls.append((key, status))
        dummy._set_component_launch_status = lambda key, status: dummy.component_status_calls.append((key, status))
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

    def test_discovery_only_accepts_canonical_frontend_listener(self) -> None:
        dummy = db_update_wizard.WizardApp.__new__(db_update_wizard.WizardApp)

        canonical_row = {
            "PID": 20892,
            "ParentPID": 4332,
            "Name": "node.exe",
            "ExecutablePath": "C:\\Program Files\\nodejs\\node.exe",
            "CreationDate": "20260813070000.000000+000",
            "CommandLine": "D:\\PY\\frontend\\admin\\node_modules\\vite\\bin\\vite.js --host 127.0.0.1 --port 5173",
        }
        foreign_row = {
            "PID": 30001,
            "ParentPID": 4000,
            "Name": "node.exe",
            "ExecutablePath": "D:\\tmp\\node.exe",
            "CreationDate": "20260813070000.000000+000",
            "CommandLine": "D:\\tmp\\frontend\\admin\\node_modules\\vite\\bin\\vite.js --host 127.0.0.1 --port 5173",
        }
        rows_by_pid = {20892: canonical_row, 30001: foreign_row}

        def fake_process_rows() -> list[dict[str, object]]:
            return list(rows_by_pid.values())

        def fake_listener_rows() -> list[dict[str, object]]:
            return [
                {"LocalPort": 5173, "OwningProcess": 20892},
                {"LocalPort": 5173, "OwningProcess": 30001},
            ]

        with patch.object(db_update_wizard, "discover_windows_process_rows", side_effect=fake_process_rows), patch.object(
            db_update_wizard, "discover_windows_listener_rows", side_effect=fake_listener_rows
        ), patch.object(db_update_wizard, "recent_history_process_pids", return_value={}):
            targets = db_update_wizard.WizardApp._discover_verified_stop_targets(dummy)

        self.assertEqual(targets["frontend-admin"], {20892})
        self.assertNotIn(30001, targets["frontend-admin"])

    def test_discovery_reads_live_python_and_node_processes_without_cim(self) -> None:
        dummy = db_update_wizard.WizardApp.__new__(db_update_wizard.WizardApp)

        rows = [
            {
                "PID": 23408,
                "ParentPID": None,
                "Name": "python",
                "ExecutablePath": "C:\\Users\\stol4\\AppData\\Local\\Programs\\Python\\Python312\\python.exe",
                "CreationDate": "",
                "CommandLine": "",
            },
            {
                "PID": 1644,
                "ParentPID": None,
                "Name": "python",
                "ExecutablePath": "D:\\PY\\.venv\\Scripts\\python.exe",
                "CreationDate": "",
                "CommandLine": "",
            },
            {
                "PID": 15796,
                "ParentPID": None,
                "Name": "python",
                "ExecutablePath": "D:\\PY\\.venv\\Scripts\\python.exe",
                "CreationDate": "",
                "CommandLine": "",
            },
            {
                "PID": 22940,
                "ParentPID": None,
                "Name": "python",
                "ExecutablePath": "D:\\PY\\.venv\\Scripts\\python.exe",
                "CreationDate": "",
                "CommandLine": "",
            },
            {
                "PID": 8696,
                "ParentPID": None,
                "Name": "node",
                "ExecutablePath": "C:\\Program Files\\nodejs\\node.exe",
                "CreationDate": "",
                "CommandLine": "",
            },
            {
                "PID": 20892,
                "ParentPID": None,
                "Name": "node",
                "ExecutablePath": "C:\\Program Files\\nodejs\\node.exe",
                "CreationDate": "",
                "CommandLine": "",
            },
        ]
        listeners = [
            {"LocalPort": 8000, "OwningProcess": 23408},
            {"LocalPort": 5175, "OwningProcess": 8696},
            {"LocalPort": 5173, "OwningProcess": 20892},
        ]

        with patch.object(db_update_wizard, "discover_windows_process_rows", return_value=rows), patch.object(
            db_update_wizard, "discover_windows_listener_rows", return_value=list(listeners)
        ):
            targets = db_update_wizard.WizardApp._discover_verified_stop_targets(dummy, include_history=False)

        self.assertEqual(targets["api"], {23408})
        self.assertEqual(targets["bot"], {1644, 15796, 22940})
        self.assertEqual(targets["frontend-app"], {8696})
        self.assertEqual(targets["frontend-admin"], {20892})

    def test_stop_all_processes_stops_verified_bot_trees(self) -> None:
        class DummyVar:
            def __init__(self, value: str = "") -> None:
                self.value = value

            def get(self) -> str:
                return self.value

            def set(self, value: str) -> None:
                self.value = value

        class LiveProc:
            def __init__(self, pid: int) -> None:
                self.pid = pid
                self.polled = None

            def poll(self) -> int | None:
                return self.polled

        class ImmediateThread:
            def __init__(self, target, daemon: bool = False) -> None:
                self.target = target

            def start(self) -> None:
                self.target()

        api_proc = LiveProc(15796)
        bot_proc_1 = LiveProc(1644)
        bot_proc_2 = LiveProc(22940)
        dummy = db_update_wizard.WizardApp.__new__(db_update_wizard.WizardApp)
        dummy.managed_processes = {"api": api_proc, "bot": bot_proc_1, "bot-copy": bot_proc_2}
        dummy.launch_status_var = DummyVar()
        dummy.action_state_calls: list[tuple[str, str]] = []
        dummy.logs: list[str] = []
        dummy.history_calls: list[tuple[str, dict[str, object]]] = []
        dummy.refresh_managed_processes = lambda: None
        dummy.refresh_product_status = lambda: None
        dummy.after = lambda _delay, callback: callback()
        dummy._begin_activity = lambda: None
        dummy._end_activity = lambda: None
        dummy._set_launch_status = lambda text: dummy.launch_status_var.set(text)
        dummy._set_action_button_state = lambda key, state: dummy.action_state_calls.append((key, state))
        dummy._append_product_log = lambda text: dummy.logs.append(text)
        dummy.record_history = lambda action, **kwargs: dummy.history_calls.append((action, kwargs))
        dummy._wait_for_verified_targets_offline = lambda timeout_seconds=10.0: {}

        discovery_sequence = [
            {"api": {15796}, "bot": {1644, 22940}, "frontend-app": set(), "frontend-admin": set()},
            {},
        ]

        def fake_discovery(self, include_history: bool = True) -> dict[str, set[int]]:
            return discovery_sequence.pop(0) if discovery_sequence else {}

        stopped_pids: list[int] = []

        def fake_stop(self, pid: int) -> bool:
            stopped_pids.append(pid)
            return True

        with patch.object(db_update_wizard.WizardApp, "_discover_verified_stop_targets", fake_discovery), patch.object(
            db_update_wizard.WizardApp, "_stop_verified_process_tree", fake_stop
        ), patch.object(db_update_wizard, "recent_history_process_pids", return_value={}), patch.object(
            db_update_wizard.threading, "Thread", ImmediateThread
        ), patch.object(
            db_update_wizard.messagebox, "showinfo"
        ) as info_mock, patch.object(
            db_update_wizard.messagebox, "showwarning"
        ) as warn_mock:
            db_update_wizard.WizardApp.stop_all_processes(dummy)

        self.assertEqual(sorted(stopped_pids), [1644, 15796, 22940])
        self.assertEqual(dummy.launch_status_var.get(), "Продукт зупинено")
        info_mock.assert_called_once()
        warn_mock.assert_not_called()
        self.assertIn(("stop-all", "success"), dummy.action_state_calls)

    def test_log_verified_stop_summary_treats_empty_remaining_sets_as_success(self) -> None:
        class DummyVar:
            def __init__(self, value: str = "") -> None:
                self.value = value

            def get(self) -> str:
                return self.value

            def set(self, value: str) -> None:
                self.value = value

        dummy = db_update_wizard.WizardApp.__new__(db_update_wizard.WizardApp)
        dummy.launch_status_var = DummyVar()
        dummy.action_state_calls: list[tuple[str, str]] = []
        dummy.logs: list[str] = []
        dummy.history_calls: list[tuple[str, dict[str, object]]] = []
        dummy._set_launch_status = lambda text: dummy.launch_status_var.set(text)
        dummy._set_action_button_state = lambda key, state: dummy.action_state_calls.append((key, state))
        dummy._append_product_log = lambda text: dummy.logs.append(text)
        dummy.record_history = lambda action, **kwargs: dummy.history_calls.append((action, kwargs))

        with patch.object(db_update_wizard.messagebox, "showinfo") as info_mock, patch.object(
            db_update_wizard.messagebox, "showwarning"
        ) as warn_mock:
            db_update_wizard.WizardApp._log_verified_stop_summary(
                dummy,
                stopped={"api": {1234}},
                remaining={"api": set(), "bot": set(), "frontend-app": set(), "frontend-admin": set()},
            )

        self.assertEqual(dummy.launch_status_var.get(), "Продукт зупинено")
        info_mock.assert_called_once()
        warn_mock.assert_not_called()
        self.assertIn(("stop-all", "success"), dummy.action_state_calls)

    def test_restart_full_local_stack_stops_then_starts(self) -> None:
        class DummyVar:
            def __init__(self, value: str = "") -> None:
                self.value = value

            def get(self) -> str:
                return self.value

            def set(self, value: str) -> None:
                self.value = value

        class LiveProc:
            def __init__(self, pid: int) -> None:
                self.pid = pid

            def poll(self) -> int | None:
                return None

        dummy = db_update_wizard.WizardApp.__new__(db_update_wizard.WizardApp)
        dummy.managed_processes = {}
        dummy.launch_status_var = DummyVar()
        dummy.action_state_calls: list[tuple[str, str]] = []
        dummy.logs: list[str] = []
        dummy.history_calls: list[tuple[str, dict[str, object]]] = []
        dummy.refresh_managed_processes = lambda: None
        dummy.refresh_product_status = lambda: None
        dummy.open_all_local_pages = lambda: None
        dummy.after = lambda _delay, callback: callback()
        dummy._begin_activity = lambda: None
        dummy._end_activity = lambda: None
        dummy._set_launch_status = lambda text: dummy.launch_status_var.set(text)
        dummy._set_action_button_state = lambda key, state: dummy.action_state_calls.append((key, state))
        dummy._append_product_log = lambda text: dummy.logs.append(text)
        dummy.record_history = lambda action, **kwargs: dummy.history_calls.append((action, kwargs))
        dummy._wait_for_verified_targets_offline = lambda timeout_seconds=10.0: {}

        stopped_pids: list[int] = []

        def fake_discovery(self, include_history: bool = True) -> dict[str, set[int]]:
            return {"api": {101}, "bot": {202}, "frontend-app": {303}, "frontend-admin": {404}}

        def fake_stop(self, pid: int) -> bool:
            stopped_pids.append(pid)
            return True

        start_calls: list[str] = []

        def fake_start_all(self) -> None:
            start_calls.append("start")
            dummy.managed_processes["bot"] = LiveProc(999)

        with patch.object(db_update_wizard.WizardApp, "_discover_verified_stop_targets", fake_discovery), patch.object(
            db_update_wizard.WizardApp, "_stop_verified_process_tree", fake_stop
        ), patch.object(db_update_wizard.WizardApp, "_service_responds", return_value=True), patch.object(
            db_update_wizard.WizardApp, "start_all_local_services", fake_start_all
        ), patch.object(
            db_update_wizard.threading, "Thread"
        ) as thread_mock, patch.object(
            db_update_wizard.messagebox, "showwarning"
        ) as warn_mock, patch.object(
            db_update_wizard.messagebox, "showinfo"
        ) as info_mock:
            thread_mock.side_effect = lambda target, daemon=False: type(
                "ImmediateThread",
                (),
                {"start": lambda self: target()},
            )()
            db_update_wizard.WizardApp.restart_full_local_stack(dummy)

        self.assertEqual(sorted(stopped_pids), [101, 202, 303, 404])
        self.assertEqual(start_calls, ["start"])
        self.assertEqual(dummy.launch_status_var.get(), "Продукт перезапущено.")
        self.assertIn(("restart-full-stack", "starting"), dummy.action_state_calls)
        self.assertIn(("restart-full-stack", "success"), dummy.action_state_calls)
        self.assertTrue(any(action == "process.restart_full_stack" for action, _ in dummy.history_calls))
        warn_mock.assert_not_called()
        info_mock.assert_not_called()

    def test_restart_selected_process_skips_foreign_port_candidate(self) -> None:
        class DummyVar:
            def __init__(self, value: str = "") -> None:
                self.value = value

            def get(self) -> str:
                return self.value

            def set(self, value: str) -> None:
                self.value = value

        class DummyListbox:
            def curselection(self) -> tuple[int, ...]:
                return (0,)

            def get(self, index: int) -> str:
                return "frontend-admin: працює, PID 30001"

        dummy = db_update_wizard.WizardApp.__new__(db_update_wizard.WizardApp)
        dummy.managed_processes = {}
        dummy.process_list = DummyListbox()
        dummy.launch_status_var = DummyVar()
        dummy.refresh_managed_processes = lambda: None
        dummy.refresh_product_status_async = lambda: None
        dummy.after = lambda _delay, callback: callback()
        dummy._set_launch_status = lambda text: dummy.launch_status_var.set(text)

        with patch.object(db_update_wizard.WizardApp, "_discover_verified_stop_targets", return_value={"frontend-admin": set()}), patch.object(
            db_update_wizard.WizardApp,
            "_stop_verified_process_tree",
        ) as stop_mock, patch.object(db_update_wizard.messagebox, "showwarning") as warn_mock, patch.object(
            db_update_wizard.messagebox, "showinfo"
        ) as info_mock:
            db_update_wizard.WizardApp.restart_selected_process(dummy)

        stop_mock.assert_not_called()
        warn_mock.assert_called_once()
        info_mock.assert_not_called()

    def test_history_fallback_recovers_latest_component_pid(self) -> None:
        dummy = db_update_wizard.WizardApp.__new__(db_update_wizard.WizardApp)

        history_entries = [
            {
                "action": "process.start",
                "details": "Локальний API",
                "command": [str(db_update_wizard.PYTHON), str(db_update_wizard.PROJECT_ROOT / "main_api.py")],
                "extra": {"pid": 10101, "cwd": "D:\\PY"},
            },
            {
                "action": "process.start",
                "details": "Frontend admin",
                "command": ["C:\\Program Files\\nodejs\\npm.cmd", "run", "dev"],
                "extra": {"pid": 20202, "cwd": "D:\\PY\\frontend\\admin"},
            },
        ]

        api_row = {
            "PID": 10101,
            "ParentPID": 9000,
            "Name": "python.exe",
            "ExecutablePath": "D:\\PY\\.venv\\Scripts\\python.exe",
            "CreationDate": "20260813070000.000000+000",
            "CommandLine": f"{db_update_wizard.PYTHON} {db_update_wizard.PROJECT_ROOT / 'main_api.py'}",
        }
        admin_row = {
            "PID": 20202,
            "ParentPID": 9001,
            "Name": "node.exe",
            "ExecutablePath": "C:\\Program Files\\nodejs\\node.exe",
            "CreationDate": "20260813070000.000000+000",
            "CommandLine": "D:\\PY\\frontend\\admin\\node_modules\\vite\\bin\\vite.js --host 127.0.0.1 --port 5173",
        }

        dummy_rows = {"api": api_row, "frontend-admin": admin_row}

        with patch.object(db_update_wizard, "read_json_lines", return_value=history_entries), patch.object(
            db_update_wizard, "discover_windows_process_row", side_effect=lambda pid: next((row for row in dummy_rows.values() if row["PID"] == pid), None)
        ):
            pids = db_update_wizard.recent_history_process_pids()

        self.assertEqual(pids["api"], 10101)
        self.assertEqual(pids["frontend-admin"], 20202)

    def test_upgrade_fittings_table_exists_uses_driver_sql(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            db_path = Path(tmpdir) / "temp.sqlite3"
            engine = create_engine(f"sqlite:///{db_path.as_posix()}")
            with engine.connect() as connection:
                self.assertFalse(
                    upgrade_fittings_foundation_schema._table_exists(connection, "fittings"),
                    "Expected missing table to return False.",
                )
                connection.exec_driver_sql("CREATE TABLE fittings (id INTEGER PRIMARY KEY)")
                self.assertTrue(
                    upgrade_fittings_foundation_schema._table_exists(connection, "fittings"),
                    "Expected created table to return True.",
                )
            engine.dispose()

    def test_upgrade_fittings_helpers_work_on_sqlalchemy_temp_db(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            db_path = Path(tmpdir) / "temp.sqlite3"
            engine = create_engine(f"sqlite:///{db_path.as_posix()}")
            with engine.begin() as connection:
                connection.exec_driver_sql(
                    """
                    CREATE TABLE fittings (
                        id INTEGER PRIMARY KEY,
                        code TEXT NOT NULL,
                        name TEXT NOT NULL
                    )
                    """
                )
                connection.exec_driver_sql(
                    """
                    CREATE TABLE suppliers (
                        id INTEGER PRIMARY KEY,
                        code TEXT NOT NULL,
                        name TEXT NOT NULL,
                        is_active BOOLEAN NOT NULL DEFAULT 1
                    )
                    """
                )
                connection.exec_driver_sql(
                    "INSERT INTO fittings (id, code, name) VALUES (1, 'F-001', 'Test fitting')"
                )

                self.assertTrue(
                    upgrade_fittings_foundation_schema._connection_in_transaction(connection)
                )
                self.assertTrue(upgrade_fittings_foundation_schema._table_exists(connection, "fittings"))
                self.assertFalse(
                    upgrade_fittings_foundation_schema._column_exists(
                        connection,
                        "fittings",
                        "catalog_key",
                    )
                )
                self.assertFalse(
                    upgrade_fittings_foundation_schema._index_exists(connection, "ix_suppliers_code")
                )
                self.assertFalse(
                    upgrade_fittings_foundation_schema._supplier_exists(connection, "viyar")
                )

                catalog_rows = upgrade_fittings_foundation_schema._build_catalog_key_rows(
                    connection,
                    False,
                )
                self.assertEqual(len(catalog_rows), 1)
                self.assertEqual(catalog_rows[0]["fitting_id"], 1)
                self.assertEqual(catalog_rows[0]["old_code"], "F-001")

            engine.dispose()

    def test_upgrade_fittings_foundation_schema_is_idempotent_on_sqlalchemy_temp_db(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            db_path = Path(tmpdir) / "temp.sqlite3"
            engine = create_engine(f"sqlite:///{db_path.as_posix()}")
            try:
                connection = engine.connect()
                try:
                    transaction = connection.begin()
                    connection.exec_driver_sql(
                        """
                        CREATE TABLE fittings (
                            id INTEGER PRIMARY KEY,
                            code TEXT NOT NULL,
                            name TEXT NOT NULL
                        )
                        """
                    )
                    connection.exec_driver_sql(
                        """
                        CREATE TABLE suppliers (
                            id INTEGER PRIMARY KEY,
                            code TEXT NOT NULL,
                            name TEXT NOT NULL,
                            is_active BOOLEAN NOT NULL DEFAULT 1
                        )
                        """
                    )
                    connection.exec_driver_sql(
                        "INSERT INTO fittings (id, code, name) VALUES (1, 'F-001', 'Test fitting')"
                    )
                    self.assertEqual(
                        connection.exec_driver_sql("PRAGMA integrity_check").fetchone()[0],
                        "ok",
                    )

                    upgrade_fittings_foundation_schema.ensure_fittings_foundation_schema(connection)

                    self.assertEqual(
                        connection.exec_driver_sql("PRAGMA integrity_check").fetchone()[0],
                        "ok",
                    )
                    self.assertTrue(
                        upgrade_fittings_foundation_schema._table_exists(connection, "suppliers")
                    )
                    self.assertTrue(
                        upgrade_fittings_foundation_schema._table_exists(
                            connection,
                            "fitting_supplier_offers",
                        )
                    )
                    self.assertTrue(
                        upgrade_fittings_foundation_schema._column_exists(
                            connection,
                            "fittings",
                            "catalog_key",
                        )
                    )
                    self.assertTrue(
                        upgrade_fittings_foundation_schema._index_exists(
                            connection,
                            "ix_suppliers_code",
                        )
                    )
                    self.assertTrue(
                        upgrade_fittings_foundation_schema._supplier_exists(connection, "viyar")
                    )
                    self.assertEqual(
                        connection.exec_driver_sql("SELECT COUNT(*) FROM suppliers").fetchone()[0],
                        1,
                    )
                    upgrade_fittings_foundation_schema.ensure_fittings_foundation_schema(connection)

                    self.assertEqual(
                        connection.exec_driver_sql("SELECT COUNT(*) FROM suppliers").fetchone()[0],
                        1,
                    )
                    self.assertEqual(
                        connection.exec_driver_sql("PRAGMA integrity_check").fetchone()[0],
                        "ok",
                    )
                    self.assertTrue(connection.in_transaction())
                finally:
                    if transaction.is_active:
                        transaction.rollback()
                    connection.close()
            finally:
                engine.dispose()

    def test_upgrade_fittings_foundation_schema_commits_in_standalone_mode(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            db_path = Path(tmpdir) / "temp.sqlite3"
            engine = create_engine(f"sqlite:///{db_path.as_posix()}")
            try:
                with engine.begin() as setup_connection:
                    setup_connection.exec_driver_sql(
                        """
                        CREATE TABLE fittings (
                            id INTEGER PRIMARY KEY,
                            code TEXT NOT NULL,
                            name TEXT NOT NULL
                        )
                        """
                    )
                    setup_connection.exec_driver_sql(
                        "INSERT INTO fittings (id, code, name) VALUES (1, 'F-001', 'Test fitting')"
                    )

                with engine.connect() as connection:
                    self.assertFalse(connection.in_transaction())
                    upgrade_fittings_foundation_schema.ensure_fittings_foundation_schema(connection)
                    self.assertTrue(connection.exec_driver_sql(
                        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='suppliers'"
                    ).fetchone() is not None)
                    self.assertEqual(
                        connection.exec_driver_sql("SELECT COUNT(*) FROM suppliers").fetchone()[0],
                        1,
                    )

                with engine.connect() as verification_connection:
                    self.assertEqual(
                        verification_connection.exec_driver_sql("PRAGMA integrity_check").fetchone()[0],
                        "ok",
                    )
                    self.assertEqual(
                        verification_connection.exec_driver_sql("SELECT COUNT(*) FROM suppliers").fetchone()[0],
                        1,
                    )
                    self.assertTrue(
                        upgrade_fittings_foundation_schema._table_exists(
                            verification_connection,
                            "fitting_supplier_offers",
                        )
                    )
                    self.assertTrue(
                        upgrade_fittings_foundation_schema._column_exists(
                            verification_connection,
                            "fittings",
                            "catalog_key",
                        )
                    )
                    self.assertTrue(
                        upgrade_fittings_foundation_schema._index_exists(
                            verification_connection,
                            "ix_suppliers_code",
                        )
                    )
            finally:
                engine.dispose()

    def test_upgrade_fittings_foundation_schema_rolls_back_in_standalone_mode_on_failure(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            db_path = Path(tmpdir) / "temp.sqlite3"
            engine = create_engine(f"sqlite:///{db_path.as_posix()}")
            try:
                with engine.begin() as setup_connection:
                    setup_connection.exec_driver_sql(
                        """
                        CREATE TABLE fittings (
                            id INTEGER PRIMARY KEY,
                            code TEXT NOT NULL,
                            name TEXT NOT NULL
                        )
                        """
                    )
                    setup_connection.exec_driver_sql(
                        "INSERT INTO fittings (id, code, name) VALUES (1, 'F-001', 'Test fitting')"
                    )

                original_execute = upgrade_fittings_foundation_schema._driver_execute

                def failing_driver_execute(connection, statement: str, parameters=None):
                    if "CREATE TABLE IF NOT EXISTS suppliers" in statement:
                        raise RuntimeError("boom")
                    return original_execute(connection, statement, parameters)

                with patch.object(
                    upgrade_fittings_foundation_schema,
                    "_driver_execute",
                    side_effect=failing_driver_execute,
                ):
                    with engine.connect() as connection:
                        with self.assertRaises(RuntimeError):
                            upgrade_fittings_foundation_schema.ensure_fittings_foundation_schema(connection)

                with engine.connect() as verification_connection:
                    self.assertFalse(
                        upgrade_fittings_foundation_schema._table_exists(
                            verification_connection,
                            "suppliers",
                        )
                    )
                    self.assertFalse(
                        upgrade_fittings_foundation_schema._table_exists(
                            verification_connection,
                            "fitting_supplier_offers",
                        )
                    )
                    self.assertFalse(
                        upgrade_fittings_foundation_schema._column_exists(
                            verification_connection,
                            "fittings",
                            "catalog_key",
                        )
                    )
                    self.assertEqual(
                        verification_connection.exec_driver_sql("PRAGMA integrity_check").fetchone()[0],
                        "ok",
                    )
            finally:
                engine.dispose()

    def test_production_like_schema_sequence_runs_twice_in_single_transaction(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            db_path = Path(tmpdir) / "temp.sqlite3"
            engine = create_engine(f"sqlite:///{db_path.as_posix()}")

            def seed_base_schema() -> None:
                with engine.begin() as setup_connection:
                    setup_connection.exec_driver_sql(
                        """
                        CREATE TABLE IF NOT EXISTS fittings (
                            id INTEGER PRIMARY KEY,
                            code TEXT NOT NULL,
                            name TEXT NOT NULL
                        )
                        """
                    )
                    setup_connection.exec_driver_sql(
                        """
                        CREATE TABLE IF NOT EXISTS mounting_nodes (
                            id INTEGER PRIMARY KEY
                        )
                        """
                    )
                    setup_connection.exec_driver_sql(
                        "INSERT OR IGNORE INTO fittings (id, code, name) VALUES (1, 'F-001', 'Test fitting')"
                    )
                    setup_connection.exec_driver_sql(
                        "INSERT OR IGNORE INTO mounting_nodes (id) VALUES (1)"
                    )

            def run_sequence() -> None:
                with engine.begin() as connection:
                    self.assertTrue(connection.in_transaction())
                    upgrade_fittings_foundation_schema.ensure_fittings_foundation_schema(connection)
                    self.assertTrue(connection.in_transaction())
                    from scripts import upgrade_mounting_schemes_schema

                    upgrade_mounting_schemes_schema.ensure_mounting_schemes_schema(connection)
                    self.assertTrue(connection.in_transaction())
                    self.assertEqual(
                        connection.exec_driver_sql("PRAGMA integrity_check").fetchone()[0],
                        "ok",
                    )

            try:
                seed_base_schema()
                run_sequence()
                run_sequence()
                with engine.connect() as verification_connection:
                    self.assertEqual(
                        verification_connection.exec_driver_sql("PRAGMA integrity_check").fetchone()[0],
                        "ok",
                    )
                    self.assertTrue(
                        upgrade_fittings_foundation_schema._table_exists(
                            verification_connection,
                            "suppliers",
                        )
                    )
                    self.assertTrue(
                        upgrade_fittings_foundation_schema._table_exists(
                            verification_connection,
                            "fitting_supplier_offers",
                        )
                    )
                    from scripts import upgrade_mounting_schemes_schema

                    self.assertTrue(
                        upgrade_mounting_schemes_schema._table_exists(
                            verification_connection,
                            "mounting_schemes",
                        )
                    )
                    self.assertTrue(
                        upgrade_mounting_schemes_schema._table_exists(
                            verification_connection,
                            "mounting_scheme_nodes",
                        )
                    )
                    self.assertTrue(
                        upgrade_mounting_schemes_schema._table_exists(
                            verification_connection,
                            "mounting_scheme_placement_rules",
                        )
                    )
                    self.assertEqual(
                        verification_connection.exec_driver_sql("SELECT COUNT(*) FROM suppliers").fetchone()[0],
                        1,
                    )
            finally:
                engine.dispose()


if __name__ == "__main__":
    unittest.main()
