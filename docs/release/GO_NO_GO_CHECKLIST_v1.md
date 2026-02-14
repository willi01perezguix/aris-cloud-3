# GO_NO_GO_CHECKLIST_v1

## Criterios obligatorios

| Criterio | PASS/FAIL | Evidencia |
|---|---|---|
| `pytest -q` en verde (ARIS_CONTROL_2) | PASS | 51 tests OK |
| Smoke mínimo (`tests/unit/test_smoke.py`) | PASS | 1 test OK |
| Default endpoint en `ARIS3_BASE_URL` oficial | PASS | `AppConfig.from_env(...).base_url` => URL oficial |
| Rebuild `ARIS_CONTROL_2.exe` por flujo oficial | FAIL | `pwsh` no disponible + `pyinstaller` no instalable por proxy |
| SHA256 del `.exe` regenerado y registrado | FAIL | No se pudo generar `.exe` en este entorno |
| Promoción release GitHub ejecutada | FAIL | `gh` no disponible |
| Comandos de promoción listos | PASS | `docs/release/RELEASE_COMMANDS_READY.md` |
| Contrato API y flujo tenant/store/user intactos | PASS | sin cambios funcionales de dominio |

## Decisión
- **NO-GO** mientras no se complete build Windows + hash + promoción desde entorno con `pwsh`/`pyinstaller`/`gh`.
