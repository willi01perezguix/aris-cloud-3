# ARIS_CONTROL_2

Shell cliente de ARIS Control 2 con arquitectura por capas (`presentation/application/domain/infrastructure`) y SDK mínimo para ARIS3.

## Instalación

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

## Ejecución

```bash
python -m aris_control_2.app.main
```

## Pruebas

```bash
pytest -q
```

## Estructura de carpetas

```text
aris_control_2/
  app/
    main.py
    ui/
      views/
      components/
    application/
      state/
      use_cases/
    domain/
      models/
      policies/
    infrastructure/
      sdk_adapter/
      idempotency/
      errors/
      logging/
  clients/
    aris3_client_sdk/
      modules/
      http_client.py
      auth_store.py
      tracing.py

tests/
  unit/
  integration/
```
