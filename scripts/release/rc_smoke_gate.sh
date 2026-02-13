#!/usr/bin/env bash
set -euo pipefail

ARTIFACT_DIR="artifacts/rc"
SUMMARY_FILE="$ARTIFACT_DIR/summary.txt"
COMMAND_LOG="$ARTIFACT_DIR/commands.log"

mkdir -p "$ARTIFACT_DIR"
: > "$SUMMARY_FILE"
: > "$COMMAND_LOG"

FULL_SUITE=0
if [[ "${1:-}" == "--full-suite" ]]; then
  FULL_SUITE=1
fi

run_check() {
  local name="$1"
  shift
  local cmd=("$@")

  echo "[RUN] $name" | tee -a "$SUMMARY_FILE"
  echo "$ ${cmd[*]}" | tee -a "$COMMAND_LOG"

  if "${cmd[@]}" 2>&1 | tee -a "$COMMAND_LOG"; then
    echo "[PASS] $name" | tee -a "$SUMMARY_FILE"
  else
    echo "[FAIL] $name" | tee -a "$SUMMARY_FILE"
    echo "RC RESULT: NO-GO" | tee -a "$SUMMARY_FILE"
    exit 1
  fi
}

run_check "Packaging scaffold (repo path)" python -m pytest clients/python/tests/test_packaging_scaffold.py -q
run_check "Timezone boundary report" python -m pytest tests/test_reports_day3_daily_timezone.py::test_reports_daily_timezone_boundary_and_week_span -q -vv
run_check "Go-live smoke POS checkout and reports" python -m pytest tests/smoke/test_go_live_validation.py::test_go_live_pos_checkout_and_reports_exports -q -vv
run_check "Packaging scripts contract" python -m pytest tests/packaging/test_packaging_scripts_contract.py -q

if [[ "$FULL_SUITE" -eq 1 ]]; then
  run_check "Full suite gate" python -m pytest tests -q -x --maxfail=1
fi

echo "RC RESULT: GO" | tee -a "$SUMMARY_FILE"
echo "Artifacts: $ARTIFACT_DIR"
