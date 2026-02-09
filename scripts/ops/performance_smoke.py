from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen


DEFAULT_OUTPUT_DIR = Path("artifacts/release_candidate")
ENDPOINTS = [
    "/aris3/stock",
    "/aris3/pos/checkout",
    "/aris3/transfers/actions/dispatch",
    "/aris3/reports/sales",
]


def _measure_endpoint(base_url: str, path: str, timeout: float) -> dict:
    url = base_url.rstrip("/") + path
    req = Request(url, method="GET")
    start = time.perf_counter()
    try:
        with urlopen(req, timeout=timeout) as response:
            _ = response.read(1024)
            status_code = response.status
        duration_ms = (time.perf_counter() - start) * 1000
        return {
            "endpoint": path,
            "url": url,
            "status": "PASS" if 200 <= status_code < 500 else "FAIL",
            "http_status": status_code,
            "p95_ms": round(duration_ms, 2),
            "error": None,
        }
    except URLError as exc:
        duration_ms = (time.perf_counter() - start) * 1000
        return {
            "endpoint": path,
            "url": url,
            "status": "FAIL",
            "http_status": None,
            "p95_ms": round(duration_ms, 2),
            "error": str(exc),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Performance smoke tests for ARIS3")
    parser.add_argument("--base-url", help="Base URL for API (e.g. http://localhost:8000)")
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--baseline", help="Baseline JSON path")
    parser.add_argument("--output", help="Output JSON path")
    args = parser.parse_args()

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = Path(args.output) if args.output else DEFAULT_OUTPUT_DIR / "performance_smoke_report.json"

    results = []
    status = "SKIPPED"
    note = "Performance smoke not executed (missing base URL)."

    if args.base_url:
        status = "PASS"
        note = "Smoke executed against provided base URL."
        for endpoint in ENDPOINTS:
            result = _measure_endpoint(args.base_url, endpoint, args.timeout)
            results.append(result)
            if result["status"] != "PASS":
                status = "FAIL"

    baseline = None
    if args.baseline and Path(args.baseline).exists():
        baseline = json.loads(Path(args.baseline).read_text())

    payload = {
        "status": status,
        "note": note,
        "baseline": baseline,
        "results": results,
    }

    output_path.write_text(json.dumps(payload, indent=2))
    print(output_path)
    return 0 if status == "PASS" else 1 if status == "FAIL" else 2


if __name__ == "__main__":
    raise SystemExit(main())
