#!/usr/bin/env bash
set -euo pipefail

RUN_FULL_SUITE="false"
if [[ "${1:-}" == "--full-suite" ]]; then
  RUN_FULL_SUITE="true"
fi

ARTIFACT_DIR="artifacts/post-ga/day1"
SUMMARY_FILE="$ARTIFACT_DIR/summary.txt"
COMMAND_LOG="$ARTIFACT_DIR/commands.log"
MATRIX_FILE="$ARTIFACT_DIR/command_matrix.tsv"
RESULTS_FILE="$ARTIFACT_DIR/results.tsv"
METADATA_FILE="$ARTIFACT_DIR/metadata.txt"

mkdir -p "$ARTIFACT_DIR"
: > "$SUMMARY_FILE"
: > "$COMMAND_LOG"
: > "$MATRIX_FILE"
: > "$RESULTS_FILE"

SHA="$(git rev-parse HEAD)"
TIMESTAMP_UTC="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
PYTHON_VERSION="$(python --version 2>&1)"

{
  echo "sha=$SHA"
  echo "timestamp_utc=$TIMESTAMP_UTC"
  echo "python_version=$PYTHON_VERSION"
  echo "run_full_suite=$RUN_FULL_SUITE"
} > "$METADATA_FILE"

declare -i PASS_COUNT=0
declare -i FAIL_FLAG=0

run_check() {
  local name="$1"
  local cmd="$2"

  echo -e "${name}\t${cmd}" >> "$MATRIX_FILE"
  echo "[RUN] $name" | tee -a "$SUMMARY_FILE"
  echo "$ $cmd" | tee -a "$COMMAND_LOG"

  if bash -lc "$cmd" >> "$COMMAND_LOG" 2>&1; then
    echo "[PASS] $name" | tee -a "$SUMMARY_FILE"
    echo -e "${name}\tPASS" >> "$RESULTS_FILE"
    PASS_COUNT+=1
  else
    echo "[FAIL] $name" | tee -a "$SUMMARY_FILE"
    echo -e "${name}\tFAIL" >> "$RESULTS_FILE"
    FAIL_FLAG=1
  fi
}

run_check "Packaging scaffold (repo path)" "python -m pytest clients/python/tests/test_packaging_scaffold.py -q"
run_check "Packaging scaffold (clients/python cwd)" "pushd clients/python >/dev/null; python -m pytest tests/test_packaging_scaffold.py -q; popd >/dev/null"
run_check "Timezone boundary report" "python -m pytest tests/test_reports_day3_daily_timezone.py::test_reports_daily_timezone_boundary_and_week_span -q -vv"
run_check "Go-live smoke POS checkout and reports" "python -m pytest tests/smoke/test_go_live_validation.py::test_go_live_pos_checkout_and_reports_exports -q -vv"
run_check "Packaging scripts contract" "python -m pytest tests/packaging/test_packaging_scripts_contract.py -q"

if [[ "$RUN_FULL_SUITE" == "true" ]]; then
  run_check "Full suite gate" "python -m pytest tests -q -x --maxfail=1"
fi

FAIL_COUNT=$(( $(wc -l < "$RESULTS_FILE") - PASS_COUNT ))
RESULT="GO"
if [[ $FAIL_FLAG -ne 0 ]]; then
  RESULT="NO-GO"
fi

{
  echo "pass_count=$PASS_COUNT"
  echo "fail_count=$FAIL_COUNT"
  echo "result=$RESULT"
} >> "$METADATA_FILE"

echo "POST-GA DAY1 RESULT: $RESULT" | tee -a "$SUMMARY_FILE"
echo "Artifacts: $ARTIFACT_DIR" | tee -a "$SUMMARY_FILE"

if [[ "$RESULT" == "NO-GO" ]]; then
  exit 1
fi
