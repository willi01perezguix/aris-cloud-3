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
