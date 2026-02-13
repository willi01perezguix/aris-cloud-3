#!/usr/bin/env bash
set -euo pipefail

python scripts/ops/post_ga_day4_retention_audit.py --artifact-dir artifacts/post-ga/day4 "$@"
