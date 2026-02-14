# RELEASE CHECKLIST ARIS_CONTROL_2 v1

## Pre-release
- [x] Unit tests finales (permission gate, tenant policy, error mapper, idempotency key factory, config validation).
- [x] Integration tests finales (login/me/effective_tenant, stores/users scope, tenant switch reset, retry/timeout).
- [x] UAT guardrails U1..U6 ejecutado con evidencia en `docs/UAT_ARIS_CONTROL_2_v1.md`.
- [x] Validación de observabilidad y no-exposición de secretos en logs.
- [x] Verificación de contratos API intactos (sin cambios backend ARIS3).

## Packaging Windows RC
- [x] Script build PowerShell preparado: `ARIS_CONTROL_2/scripts/windows/build_control_center.ps1`.
- [x] Script run dev PowerShell preparado: `ARIS_CONTROL_2/scripts/windows/run_control_center_dev.ps1`.
- [x] Plantilla spec de PyInstaller preparada: `ARIS_CONTROL_2/packaging/control_center.spec.template`.
- [ ] Build ejecutado en Windows runner (bloqueado en entorno actual sin `pwsh`).
- [ ] Smoke de ejecutable (`dist/`) con login + navegación base (pendiente ejecución en Windows).

## Deploy
- [ ] Ejecutar build desde host Windows:
  1. `pwsh -NoProfile -File ARIS_CONTROL_2/scripts/windows/build_control_center.ps1`
  2. Validar artefacto generado en `ARIS_CONTROL_2/dist/`
- [ ] Ejecutar smoke de artefacto:
  1. Arranque binario
  2. Login de usuario de prueba
  3. Navegación Tenants/Stores/Users

## Post-deploy
- [ ] Confirmar telemetry: logs con `trace_id` y sin secretos.
- [ ] Confirmar errores funcionales muestran `code/message/trace_id`.
- [ ] Confirmar no duplicaciones por replay de mutaciones.

## Gate final GO/NO-GO
- Reglas en `out/aris_control_2_release_readiness.json`.
- GO únicamente si G1..G10 en PASS.
