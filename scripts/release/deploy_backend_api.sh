#!/usr/bin/env bash
set -euo pipefail

EXPECTED_HEAD="${EXPECTED_ALEMBIC_HEAD:-0026_s9_inventory_intake_workflow}"
DATABASE_URL="${DATABASE_URL:-}"

if [[ -z "$DATABASE_URL" ]]; then
  echo "ERROR: DATABASE_URL is required." >&2
  exit 1
fi

if [[ "$DATABASE_URL" == sqlite* ]]; then
  echo "ERROR: refusing production deploy migration against sqlite DATABASE_URL." >&2
  exit 1
fi

echo "[deploy-backend] verifying single alembic head"
head_count="$(alembic heads | sed '/^$/d' | wc -l | tr -d ' ')"
if [[ "$head_count" != "1" ]]; then
  echo "ERROR: expected a single alembic head, got ${head_count}." >&2
  alembic heads
  exit 1
fi

actual_head="$(alembic heads | awk '{print $1}')"
if [[ "$actual_head" != "$EXPECTED_HEAD" ]]; then
  echo "ERROR: alembic head mismatch. expected=${EXPECTED_HEAD} actual=${actual_head}" >&2
  exit 1
fi

echo "[deploy-backend] current revision before upgrade"
alembic current || true

echo "[deploy-backend] running alembic upgrade head"
alembic upgrade head

echo "[deploy-backend] current revision after upgrade"
alembic current

current_rev="$(alembic current | awk '/^[0-9a-z_]+/ {print $1; exit}')"
if [[ "$current_rev" != "$EXPECTED_HEAD" ]]; then
  echo "ERROR: post-upgrade revision mismatch. expected=${EXPECTED_HEAD} current=${current_rev}" >&2
  exit 1
fi

echo "[deploy-backend] migration alignment OK (${current_rev})."

echo "[deploy-backend] starting API"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
