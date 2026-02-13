#!/usr/bin/env bash
set -euo pipefail

ARGS=()
if [[ "${1:-}" == "--full-suite" ]]; then
  ARGS+=("--full-suite")
fi

python scripts/ops/perf_snapshot.py --artifact-dir artifacts/post-ga/day2 "${ARGS[@]}"
