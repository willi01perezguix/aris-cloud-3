# ARIS_CONTROL_2

Bootstrap inicial de ARIS Control 2 con arquitectura por capas:

- presentation (`app/ui`)
- application (`app/application`)
- domain (`app/domain`)
- infrastructure (`app/infrastructure`)
- client SDK (`clients/aris3_client_sdk`)

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
cp .env.example .env
```

## Ejecutar shell app

```bash
python -m aris_control_2.app.main
```

## Tests

```bash
pytest -q
```
