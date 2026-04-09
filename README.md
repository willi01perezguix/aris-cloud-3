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

## Deploy backend API (production-safe)

Use the release entrypoint below so the deploy fails fast when migrations are not aligned with
the runtime build:

```bash
DATABASE_URL=postgresql+psycopg://... EXPECTED_ALEMBIC_HEAD=0026_s9_inventory_intake_workflow \
  ./scripts/release/deploy_backend_api.sh
```

The script enforces:
- `DATABASE_URL` must be set (and non-sqlite for production paths).
- Single Alembic head in the checked-out code.
- Expected head revision matches the checked-out migration chain.
- `alembic upgrade head` completes before API startup.

## Tests

```bash
pytest -q
```

## Access control admin (ARIS3)

Mutaciones en `/aris3/admin/access-control/*` y `/aris3/access-control/*` requieren `Idempotency-Key`
en headers y `transaction_id` en el payload JSON. Las políticas se evalúan en orden:
role template global → tenant policy → store policy → user override, con `DENY` ganando
siempre sobre `ALLOW` (default deny).

## API contract hardening (2026-Q1)

- **Error envelope unificado**: todos los errores HTTP/validación/backend exponen `{code,message,details,trace_id}`.
- **`change-password` canónico**: `PATCH /aris3/auth/change-password` es la ruta canónica.
  - `POST /aris3/auth/change-password` sigue disponible como alias temporal (`deprecated=true` + headers `Deprecation`/`Sunset`).
  - **Fecha de retiro alias POST**: `2026-06-30`.
- **Admin stores scoping**:
  - `tenant_id` (query) es el selector explícito para superadmin/platform admin en `GET /aris3/admin/stores`.
  - `query_tenant_id` se mantiene por compatibilidad y está deprecado.
  - **Fecha de retiro `query_tenant_id`**: `2026-06-30`.
- **Users status vs is_active**:
  - `status` es el estado canónico de negocio (`ACTIVE|SUSPENDED|CANCELED`).
  - `is_active` queda como flag derivado de compatibilidad (`ACTIVE=true`, resto `false`) y está deprecado como filtro de entrada.
- **Health probes**:
  - `GET /health` y `GET /ready` devuelven JSON estructurado con `ok/service/timestamp/version/trace_id/readiness`.
