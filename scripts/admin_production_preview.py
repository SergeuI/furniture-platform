from __future__ import annotations

import os
import shutil
import subprocess
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = PROJECT_ROOT / "frontend" / "admin"
DIST_ROOT = FRONTEND_ROOT / "dist"
HOST = "127.0.0.1"
PORT = 4175
URL_PREFIX = "/admin"


class AdminProductionHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        request_path = urlsplit(self.path).path
        if request_path != URL_PREFIX and not request_path.startswith(f"{URL_PREFIX}/"):
            self.send_error(404)
            return
        relative_path = request_path[len(URL_PREFIX):].lstrip("/")
        candidate = (DIST_ROOT / relative_path).resolve()
        self.path = "/" + relative_path if candidate.is_file() and DIST_ROOT in candidate.parents else "/index.html"
        super().do_GET()

    def translate_path(self, path):
        relative_path = urlsplit(path).path.lstrip("/")
        return str((DIST_ROOT / relative_path).resolve())

    def log_message(self, format, *args):
        print(f"{self.address_string()} - - [{self.log_date_time_string()}] {format % args}", flush=True)


def run_build() -> None:
    if not FRONTEND_ROOT.is_dir():
        raise RuntimeError(f"Frontend directory not found: {FRONTEND_ROOT}")
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if not npm:
        raise RuntimeError("npm executable was not found on PATH")
    environment = os.environ.copy()
    environment["VITE_API_BASE_URL"] = "http://127.0.0.1:8000"
    print("[admin-production] Building frontend/admin...", flush=True)
    result = subprocess.run([npm, "run", "build"], cwd=FRONTEND_ROOT, env=environment, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"Frontend build failed with exit code {result.returncode}")
    if not (DIST_ROOT / "index.html").is_file():
        raise RuntimeError(f"Build output missing: {DIST_ROOT / 'index.html'}")
    if not (DIST_ROOT / "assets").is_dir():
        raise RuntimeError(f"Build output missing: {DIST_ROOT / 'assets'}")


def run_server() -> None:
    try:
        server = ThreadingHTTPServer((HOST, PORT), AdminProductionHandler)
    except OSError as exc:
        raise RuntimeError(f"Port {PORT} is already in use on {HOST}") from exc
    print(f"[admin-production] Serving {DIST_ROOT} at http://{HOST}:{PORT}{URL_PREFIX}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("[admin-production] Shutting down.", flush=True)
    finally:
        server.server_close()


def main() -> int:
    try:
        run_build()
        run_server()
    except Exception as exc:
        print(f"[admin-production] ERROR: {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
