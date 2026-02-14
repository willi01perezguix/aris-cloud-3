# Day 6 — Evidencia smoke E2E guiado (manual reproducible)

Fecha: 2026-02-14

## Script/checklist único
- Script: `scripts/windows/day6_guided_e2e_smoke.ps1`
- Orden validado:
  1. Abrir app
  2. Login SUPERADMIN
  3. Selección tenant + operaciones stores/users
  4. Bloqueo RBAC sin permisos
  5. Trazabilidad de errores (`code/message/trace_id`)

## Resultado por paso (entorno CI Linux actual)
| Paso | Estado | Evidencia |
|---|---|---|
| Abrir app | PASS (modo scriptado parcial) | `python -m aris_control_2.app.main` con input automatizado para salida controlada. |
| Login SUPERADMIN | BLOCKED (credenciales no disponibles en CI) | Requiere secretos operativos no presentes en entorno. |
| Tenant + stores/users | BLOCKED (depende de login real) | Flujo cubierto en tests de integración de tenant/store/user. |
| Bloqueo RBAC | PASS (por pruebas) | `tests/integration/test_users_actions_rbac_ui_guard.py` y `tests/unit/test_permission_gate.py`. |
| Trazabilidad errores | PASS (por pruebas) | `tests/unit/test_day5_diagnostics_and_context.py`, `tests/unit/test_main_api_diagnostics.py`. |

## Capturas / evidencia
- En este entorno no hay desktop Windows ni herramienta de captura GUI; se deja evidencia reproducible en reportes de pruebas JUnit y reporte consolidado Day 6.
- Artefactos:
  - `out/day6/day6_validation_junit.xml`
  - `out/day6/day6_smoke_junit.xml`
  - `out/day6/day6_observability_junit.xml`
  - `out/day6/DAY6_TEST_REPORT.md`
