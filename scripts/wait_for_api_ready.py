from __future__ import annotations

import argparse
import time
from urllib.error import URLError
from urllib.request import urlopen


def _is_ready(url: str, timeout: float) -> bool:
    try:
        with urlopen(url, timeout=timeout) as response:
            return 200 <= getattr(response, "status", 200) < 500
    except URLError:
        return False
    except OSError:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Wait until the local API becomes available."
    )
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8000/health",
        help="URL to probe for readiness.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=90.0,
        help="Maximum time to wait in seconds.",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=2.0,
        help="Delay between probes in seconds.",
    )
    args = parser.parse_args()

    deadline = time.monotonic() + max(args.timeout, 0.0)
    while True:
        if _is_ready(args.url, timeout=min(args.interval, 5.0)):
            print(f"READY {args.url}")
            return 0

        if time.monotonic() >= deadline:
            print(f"TIMEOUT {args.url}")
            return 1

        time.sleep(max(args.interval, 0.2))


if __name__ == "__main__":
    raise SystemExit(main())
