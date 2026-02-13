#!/usr/bin/env bash
set -euo pipefail

python scripts/ops/load_probe.py --artifact-dir artifacts/post-ga/day3 "$@"
