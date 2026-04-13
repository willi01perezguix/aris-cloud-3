#!/usr/bin/env bash
set -euo pipefail

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
heads_output="$(alembic heads)"
head_count="$(printf '%s\n' "$heads_output" | sed '/^$/d' | wc -l | tr -d ' ')"
if [[ "$head_count" != "1" ]]; then
  echo "ERROR: expected a single alembic head, got ${head_count}." >&2
  printf '%s\n' "$heads_output"
  exit 1
fi

repo_head="$(printf '%s\n' "$heads_output" | awk 'NF {print $1; exit}')"
if [[ -z "$repo_head" ]]; then
  echo "ERROR: unable to resolve repository alembic head." >&2
  exit 1
fi

if [[ -n "${EXPECTED_ALEMBIC_HEAD:-}" && "$EXPECTED_ALEMBIC_HEAD" != "$repo_head" ]]; then
  echo "ERROR: EXPECTED_ALEMBIC_HEAD mismatch. expected=${EXPECTED_ALEMBIC_HEAD} repo=${repo_head}" >&2
  exit 1
fi

echo "[deploy-backend] current revision before upgrade"
alembic current || true

echo "[deploy-backend] running alembic upgrade head"
alembic upgrade head

echo "[deploy-backend] current revision after upgrade"
alembic current

current_rev="$(alembic current | awk '/^[0-9a-z_]+/ {print $1; exit}')"
if [[ -z "$current_rev" ]]; then
  echo "ERROR: could not determine current alembic revision after upgrade." >&2
  exit 1
fi

if [[ "$current_rev" != "$repo_head" ]]; then
  echo "ERROR: post-upgrade revision mismatch. repo_head=${repo_head} current=${current_rev}" >&2
  exit 1
fi

echo "[deploy-backend] migration alignment OK (${current_rev})."

echo "[deploy-backend] starting API"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
