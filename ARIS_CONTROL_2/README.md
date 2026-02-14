# ARIS_CONTROL_2

Shell cliente de ARIS Control 2 con arquitectura por capas (`presentation/application/domain/infrastructure`) y SDK mínimo para ARIS3.

## Instalación

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

## Configuración

Variables soportadas (con defaults seguros):

- `ARIS3_BASE_URL` (`http://localhost:8000`)
- `ARIS3_TIMEOUT_SECONDS` (`30`)
- `ARIS3_VERIFY_SSL` (`true`)
- `ARIS3_RETRY_MAX_ATTEMPTS` (`3`)
- `ARIS3_RETRY_BACKOFF_MS` (`150`)

## Ejecución

```bash
python -m aris_control_2.app.main
```

## Windows pre-packaging (inicial)

Prerequisitos:

- Windows PowerShell 5+ (o PowerShell 7)
- Python 3.11+
- Dependencias del proyecto instaladas
- PyInstaller (solo para build): `pip install pyinstaller`

Scripts:

- Desarrollo: `scripts/windows/run_control_center_dev.ps1`
- Build inicial: `scripts/windows/build_control_center.ps1`
- Template spec: `packaging/control_center.spec.template`

## Pruebas

```bash
pytest -q
```
