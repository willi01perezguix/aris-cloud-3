from __future__ import annotations

import argparse
import csv
import json
import math
import platform
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Profile:
    iterations: int
    concurrency: int
    warmup: int
    timeout_seconds: float
    max_p95_ms: float
    max_p99_ms: float
    max_error_rate: float


PROFILES: dict[str, Profile] = {
    "L1": Profile(24, 2, 3, 5.0, 900.0, 1500.0, 0.01),
    "L2": Profile(48, 4, 4, 5.0, 1100.0, 1800.0, 0.015),
    "L3": Profile(72, 6, 6, 5.0, 1400.0, 2200.0, 0.02),
}


ENDPOINTS = (
    ("health", "/health"),
    ("stock", "/aris3/stock?limit=1"),
    ("reports_overview", "/aris3/reports/overview?date_from=2026-01-01&date_to=2026-01-03"),
)


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    k = (len(ordered) - 1) * p
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return ordered[int(k)]
    d0 = ordered[f] * (c - k)
    d1 = ordered[c] * (k - f)
    return d0 + d1


def _git_sha(repo_root: Path) -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_root, text=True).strip()
    except Exception:
        return "unknown"


def _request_once(base_url: str, endpoint_name: str, path: str, timeout_seconds: float, index: int) -> dict[str, Any]:
    url = urllib.parse.urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
    started = time.perf_counter()
    status_code = 0
    error_text = ""
    ok = False
    try:
        req = urllib.request.Request(url=url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout_seconds) as response:  # noqa: S310
            status_code = int(getattr(response, "status", 200))
            ok = 200 <= status_code < 300
            _ = response.read(64)
    except urllib.error.HTTPError as exc:
        status_code = int(exc.code)
        error_text = str(exc.reason)
    except Exception as exc:  # deterministic artifact capture
        error_text = str(exc)
    latency_ms = (time.perf_counter() - started) * 1000.0
    return {
        "iteration": index,
        "endpoint": endpoint_name,
        "path": path,
        "status_code": status_code,
        "latency_ms": round(latency_ms, 3),
        "ok": ok,
        "error": error_text,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Post-GA Day3 deterministic load probe")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--artifact-dir", default="artifacts/post-ga/day3")
    parser.add_argument("--profile", choices=sorted(PROFILES.keys()), default="L1")
    parser.add_argument("--iterations", type=int)
    parser.add_argument("--concurrency", type=int)
    parser.add_argument("--warmup", type=int)
    parser.add_argument("--timeout-seconds", type=float)
    parser.add_argument("--strict-gate", action="store_true", default=False)
    args = parser.parse_args()

    profile = PROFILES[args.profile]
    iterations = args.iterations if args.iterations is not None else profile.iterations
    concurrency = args.concurrency if args.concurrency is not None else profile.concurrency
    warmup = args.warmup if args.warmup is not None else profile.warmup
    timeout_seconds = args.timeout_seconds if args.timeout_seconds is not None else profile.timeout_seconds

    artifact_dir = Path(args.artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    repo_root = Path(__file__).resolve().parents[2]

    env_snapshot = {
        "git_sha": _git_sha(repo_root),
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "python_version": sys.version.replace("\n", " ").strip(),
        "platform": platform.platform(),
        "base_url": args.base_url,
        "profile": args.profile,
        "iterations": iterations,
        "concurrency": concurrency,
        "warmup": warmup,
        "timeout_seconds": timeout_seconds,
        "strict_gate": bool(args.strict_gate),
    }
    (artifact_dir / "env_snapshot.json").write_text(json.dumps(env_snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    for i in range(warmup):
        for endpoint_name, path in ENDPOINTS:
            _request_once(args.base_url, endpoint_name, path, timeout_seconds, -(i + 1))

    tasks: list[tuple[str, str, int]] = []
    for i in range(1, iterations + 1):
        for endpoint_name, path in ENDPOINTS:
            tasks.append((endpoint_name, path, i))

    rows: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as executor:
        futures = [
            executor.submit(_request_once, args.base_url, endpoint_name, path, timeout_seconds, idx)
            for endpoint_name, path, idx in tasks
        ]
        for fut in as_completed(futures):
            rows.append(fut.result())

    rows.sort(key=lambda row: (row["iteration"], row["endpoint"]))

    with (artifact_dir / "timings.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["iteration", "endpoint", "path", "status_code", "latency_ms", "ok", "error"])
        writer.writeheader()
        writer.writerows(rows)

    latencies = [float(r["latency_ms"]) for r in rows]
    total = len(rows)
    failures = sum(1 for r in rows if not r["ok"])
    success = total - failures
    error_rate = (failures / total) if total else 1.0

    endpoint_stats: dict[str, dict[str, Any]] = {}
    for endpoint_name, _ in ENDPOINTS:
        subset = [r for r in rows if r["endpoint"] == endpoint_name]
        vals = [float(r["latency_ms"]) for r in subset]
        ep_total = len(subset)
        ep_fail = sum(1 for r in subset if not r["ok"])
        endpoint_stats[endpoint_name] = {
            "count": ep_total,
            "success": ep_total - ep_fail,
            "failure": ep_fail,
            "availability": round(((ep_total - ep_fail) / ep_total) if ep_total else 0.0, 4),
            "p50_ms": round(_percentile(vals, 0.50), 3),
            "p95_ms": round(_percentile(vals, 0.95), 3),
            "p99_ms": round(_percentile(vals, 0.99), 3),
        }

    p95 = _percentile(latencies, 0.95)
    p99 = _percentile(latencies, 0.99)
    min_availability = min((s["availability"] for s in endpoint_stats.values()), default=0.0)

    hard_fail_reasons: list[str] = []
    if min_availability < 0.99:
        hard_fail_reasons.append(f"availability below 99% (min={min_availability:.2%})")
    if error_rate > profile.max_error_rate:
        hard_fail_reasons.append(f"error_rate {error_rate:.2%} above {profile.max_error_rate:.2%}")
    if p95 > profile.max_p95_ms:
        hard_fail_reasons.append(f"p95 {p95:.1f}ms above {profile.max_p95_ms:.1f}ms")
    if args.strict_gate and failures > 0:
        hard_fail_reasons.append("strict gate requires zero failed requests")
    if args.strict_gate and p99 > profile.max_p99_ms:
        hard_fail_reasons.append(f"strict p99 {p99:.1f}ms above {profile.max_p99_ms:.1f}ms")

    result = "GO" if not hard_fail_reasons else "NO-GO"

    summary = {
        "result": result,
        "profile": args.profile,
        "strict_gate": bool(args.strict_gate),
        "totals": {"requests": total, "success": success, "failure": failures, "error_rate": round(error_rate, 6)},
        "latency_ms": {
            "p50": round(_percentile(latencies, 0.50), 3),
            "p95": round(p95, 3),
            "p99": round(p99, 3),
        },
        "limits": {
            "max_p95_ms": profile.max_p95_ms,
            "max_p99_ms": profile.max_p99_ms,
            "max_error_rate": profile.max_error_rate,
        },
        "endpoint_stats": endpoint_stats,
        "hard_fail_reasons": hard_fail_reasons,
    }

    (artifact_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (artifact_dir / "gate_result.txt").write_text(result + "\n", encoding="utf-8")

    print(
        f"profile={args.profile} strict={args.strict_gate} requests={total} failures={failures} "
        f"error_rate={error_rate:.2%} p95_ms={p95:.1f} result={result}"
    )

    return 0 if result == "GO" else 1


if __name__ == "__main__":
    raise SystemExit(main())
