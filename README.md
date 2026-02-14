# ARIS-CLOUD-3

Backend base para ARIS 3 con FastAPI, SQLAlchemy 2.x y Alembic.

## Requisitos

- Python 3.11+
- SQLite para desarrollo local (por defecto)
- PostgreSQL opcional con `DATABASE_URL`

## Configuración rápida

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Variables de entorno relevantes (Reports/Exports)

- `REPORTS_MAX_DATE_RANGE_DAYS`: rango máximo de días permitido en reportes/exportes.
- `EXPORTS_MAX_ROWS`: filas máximas exportables por solicitud.
- `EXPORTS_LIST_MAX_PAGE_SIZE`: límite superior para `page_size` en listados de exports.

## Ejecutar local

```bash
uvicorn app.main:app --reload
```

## Migraciones

```bash
alembic upgrade head
```

## Tests

```bash
pytest -q
```

## Access control admin (ARIS3)

Mutaciones en `/aris3/admin/access-control/*` y `/aris3/access-control/*` requieren `Idempotency-Key`
en headers y `transaction_id` en el payload JSON. Las políticas se evalúan en orden:
role template global → tenant policy → store policy → user override, con `DENY` ganando
siempre sobre `ALLOW` (default deny).

## ARIS_CONTROL_2 cierre Prompt 8

- UAT final: `docs/UAT_ARIS_CONTROL_2_v1.md`
- Release checklist: `docs/RELEASE_CHECKLIST_ARIS_CONTROL_2_v1.md`
- Rollback playbook: `docs/ROLLBACK_PLAYBOOK_ARIS_CONTROL_2_v1.md`
- Reportes JSON: `out/aris_control_2_uat_report.json`, `out/aris_control_2_release_readiness.json`
