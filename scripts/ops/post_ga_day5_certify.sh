#!/usr/bin/env bash
set -euo pipefail

python scripts/ops/post_ga_day5_certify.py --artifact-dir artifacts/post-ga/day5 "$@"
