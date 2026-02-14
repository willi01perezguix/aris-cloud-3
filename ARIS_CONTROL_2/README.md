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

## Ejecución local

```bash
python -m aris_control_2.app.main
```

## Build / run en Windows (RC inicial)

Prerequisitos:

- Windows PowerShell 5+ (o PowerShell 7)
- Python 3.11+
- Dependencias del proyecto instaladas
- PyInstaller para build (`pip install pyinstaller`)

Comandos:

- Dev run:
  - `pwsh -NoProfile -File scripts/windows/run_control_center_dev.ps1`
- Build RC:
  - `pwsh -NoProfile -File scripts/windows/build_control_center.ps1`

Artefacto esperado:

- `dist/aris_control_2*` (según plataforma y plantilla spec)

## Pruebas

```bash
pytest -q
```

## Troubleshooting

- `TENANT_CONTEXT_REQUIRED`: SUPERADMIN debe seleccionar tenant antes de Stores/Users.
- `PERMISSION_DENIED`: validar `effective_permissions` y rol del actor.
- `TENANT_STORE_MISMATCH`: la store elegida no pertenece al tenant efectivo.
- `trace_id` faltante: revisar respuesta backend y headers `X-Trace-ID`.
- Build Windows falla: validar instalación de `pwsh` y `pyinstaller` en host Windows.

## Documentación de cierre Prompt 8

- UAT final: `docs/UAT_ARIS_CONTROL_2_v1.md`
- Release checklist: `docs/RELEASE_CHECKLIST_ARIS_CONTROL_2_v1.md`
- Rollback playbook: `docs/ROLLBACK_PLAYBOOK_ARIS_CONTROL_2_v1.md`
