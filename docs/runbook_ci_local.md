# CI / Local Runbook

## Prerequisites
- Python 3.11
- Dependencies installed: `pip install -r requirements.txt`

## Local Commands (Migrate / Seed / Test)
```bash
# Import check
PYTHONPATH=. python -c "import app; print('ok')"

# Database migrate (SQLite example)
export DATABASE_URL=sqlite+pysqlite:///./aris3.db
alembic upgrade head

# Seed defaults (tenant/store/users/permissions)
python - <<'PY'
from app.aris3.db.session import SessionLocal
from app.aris3.db.seed import run_seed

db = SessionLocal()
try:
    run_seed(db)
finally:
    db.close()
PY

# Run tests
pytest -q
```

## Troubleshooting Quick Notes
- **Import check fails**: Ensure `PYTHONPATH=.` and dependencies are installed (`pip install -r requirements.txt`).
- **Multiple Alembic heads**: Resolve by merging migrations or rebasing to a single head; CI enforces one head.
- **Alembic upgrade fails**: Confirm `DATABASE_URL` points to a writable DB file and rerun `alembic upgrade head`.
- **SQLite file locked**: Remove stale `*.db` files or stop any process holding the DB open.
## Sprint 6 Day 6 Release Readiness
- See `docs/runbooks/sprint6_day6_release_readiness.md` for post-merge stabilization outcomes, known limitations, and rollback confirmation steps.

