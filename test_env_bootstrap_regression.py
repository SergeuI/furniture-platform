from __future__ import annotations

import hashlib
import hmac
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


FALLBACK_AUTH_SECRET = "furniture-platform-local-dev-secret"
TEST_TOKEN = "registration-token-for-bootstrap"
STRONG_AUTH_SECRET = "0123456789abcdef0123456789abcdef"


class EnvBootstrapRegressionTests(unittest.TestCase):
    def test_bot_and_api_entrypoints_load_env_before_registration_auth_imports(self) -> None:
        repo_root = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            (tmp_path / ".env").write_text(
                "\n".join(
                    [
                        f"AUTH_SECRET_KEY={STRONG_AUTH_SECRET}",
                        "BOT_TOKEN=123456:telegram-test-bot-token",
                        "TELEGRAM_BOT_USERNAME=furniture_bot",
                    ]
                ),
                encoding="utf-8",
            )

            base_env = os.environ.copy()
            base_env.pop("AUTH_SECRET_KEY", None)
            base_env.pop("BOT_TOKEN", None)
            base_env.pop("TELEGRAM_BOT_USERNAME", None)
            base_env["PYTHONPATH"] = self._prepend_pythonpath(
                repo_root,
                base_env.get("PYTHONPATH"),
            )

            bot_result = self._run_probe(
                [
                    "import handlers.router",
                    "from services.registration_identity_service import hash_registration_token",
                    f'print(json.dumps({{"hash": hash_registration_token("{TEST_TOKEN}")}}))',
                ],
                cwd=tmp_path,
                env=base_env,
            )

            api_result = self._run_probe(
                [
                    "import types",
                    "import sys",
                    'stub = types.ModuleType("database.init_db")',
                    "stub.init_database = lambda: None",
                    'sys.modules["database.init_db"] = stub',
                    "import main_api",
                    "from services.registration_identity_service import hash_registration_token",
                    f'print(json.dumps({{"hash": hash_registration_token("{TEST_TOKEN}")}}))',
                ],
                cwd=tmp_path,
                env=base_env,
            )

        expected_hash = self._hash_with_secret(STRONG_AUTH_SECRET, TEST_TOKEN)
        fallback_hash = self._hash_with_secret(FALLBACK_AUTH_SECRET, TEST_TOKEN)

        self.assertEqual(bot_result["hash"], expected_hash)
        self.assertEqual(api_result["hash"], expected_hash)
        self.assertEqual(bot_result["hash"], api_result["hash"])
        self.assertNotEqual(bot_result["hash"], fallback_hash)
        self.assertNotEqual(api_result["hash"], fallback_hash)

    @staticmethod
    def _hash_with_secret(secret: str, token: str) -> str:
        return hmac.new(
            secret.encode("utf-8"),
            token.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    @staticmethod
    def _prepend_pythonpath(repo_root: Path, existing: str | None) -> str:
        parts = [str(repo_root)]
        if existing:
            parts.append(existing)
        return os.pathsep.join(parts)

    @staticmethod
    def _run_probe(script_parts: list[str], *, cwd: Path, env: dict[str, str]) -> dict[str, str]:
        script = textwrap.dedent(
            "\n".join(
                [
                    "import json",
                    *script_parts,
                ]
            )
        )
        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=str(cwd),
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        stdout = completed.stdout.strip()
        if not stdout:
            raise AssertionError("Probe produced no output")

        payload = json.loads(stdout)

        if STRONG_AUTH_SECRET in completed.stdout or STRONG_AUTH_SECRET in completed.stderr:
            raise AssertionError("Strong auth secret leaked into probe output")
        if FALLBACK_AUTH_SECRET in completed.stdout or FALLBACK_AUTH_SECRET in completed.stderr:
            raise AssertionError("Fallback auth secret leaked into probe output")

        return payload


if __name__ == "__main__":
    unittest.main()
