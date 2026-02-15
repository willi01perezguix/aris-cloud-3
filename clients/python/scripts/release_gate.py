from __future__ import annotations

import argparse
import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SDK_SRC = REPO_ROOT / "clients" / "python" / "aris3_client_sdk" / "src"
if str(SDK_SRC) not in sys.path:
    sys.path.insert(0, str(SDK_SRC))


@contextmanager
def _without_api_base_url() -> None:
    keys = [key for key in os.environ if key.startswith("ARIS3_API_BASE_URL")]
    keys.append("ARIS3_ENV")
    snapshot = {key: os.environ.get(key) for key in keys}
    for key in keys:
        os.environ.pop(key, None)
    try:
        yield
    finally:
        for key, value in snapshot.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def check_imports() -> None:
    import aris3_client_sdk
    from aris3_client_sdk.clients import exports_client, stock_client

    if not hasattr(aris3_client_sdk, "__version__"):
        raise RuntimeError("SDK package does not expose __version__")
    _ = exports_client.ExportsClient
    _ = stock_client.StockClient


def check_strict_config() -> None:
    from aris3_client_sdk.config import ConfigError, load_config

    with _without_api_base_url():
        try:
            load_config()
        except ConfigError:
            return
    raise RuntimeError("load_config() must fail without ARIS3_API_BASE_URL")


def run_pytest(pytest_target: str) -> None:
    cmd = [sys.executable, "-m", "pytest", *pytest_target.split()]
    completed = subprocess.run(cmd, cwd=REPO_ROOT, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"pytest failed with exit code {completed.returncode}")


def main() -> int:
    parser = argparse.ArgumentParser(description="SDK release quality gate")
    parser.add_argument(
        "--pytest-target",
        default="clients/python/tests -q",
        help="pytest target arguments, e.g. 'clients/python/tests -q'",
    )
    args = parser.parse_args()

    checks = [
        ("imports del SDK", check_imports),
        ("load_config estricto sin ARIS3_API_BASE_URL", check_strict_config),
        ("tests SDK", lambda: run_pytest(args.pytest_target)),
    ]

    for label, check in checks:
        print(f"[release-gate] START {label}")
        check()
        print(f"[release-gate] OK {label}")

    print("[release-gate] RESULT OK")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - exercised in CI failures
        print(f"[release-gate] FAIL {exc}", file=sys.stderr)
        raise SystemExit(1)
