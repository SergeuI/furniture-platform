from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
