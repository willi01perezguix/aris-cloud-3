# ARIS_CONTROL_2 / ARIS3 Backend Alignment — Certificación de Cierre (Step 5)

## Alcance
Certificación final de backend para cierre GO/NO-GO de ARIS_CONTROL_2, validando:
- scope tenant/store/user en admin core,
- hardening tenant-store-user,
- idempotencia (first/replay/conflict),
- auditoría y trace_id,
- compatibilidad de contrato API (rutas públicas + envelope de error).

## Cambios aplicados por step (estado de verificación)
- **Step 1 diagnóstico**: tomado como base (completado previamente).
- **Step 2 tenant scope/repos**: verificado por pruebas de scope en stores/users/actions.
- **Step 3 hardening DB tenant-store-user**: verificado por prueba de integridad y caso API TENANT_STORE_MISMATCH.
- **Step 4 idempotencia + auditoría + trace**: verificado por pruebas de admin core/idempotency/audit + ejecución dirigida HTTP.
- **Step 5 certificación**: ejecutado en este reporte con matriz G1..G8 y veredicto final.

## Comandos ejecutados (evidencia)
1. `pytest tests/test_admin_core.py tests/test_superadmin_tenants.py tests/test_tenant_store_user_integrity.py tests/test_idempotency_admin.py tests/test_audit_trace_admin.py -ra`
2. `python scripts/contract_safety_check.py --json`
3. Ejecución dirigida con `python - <<'PY' ... PY` usando `TestClient` para capturar ejemplos HTTP reales (mismatch tenant-store, idempotency replay/conflict, denegación MANAGER, audit persisted con trace_id).

## Resumen de ejecución
- Suite focal + regresión admin core:
  - **21 passed**, **0 failed**, **0 skipped** (`21 passed in 46.61s`).
- Contract safety check:
  - 4 checks en estado **PASS**.

## Verificación de contrato
- **Rutas públicas:** sin cambios detectados en routers durante esta certificación (no hubo cambios de código de rutas; validación estática de mapa crítico en PASS).
- **Envelope de error:** comprobado en respuestas reales con forma `code/message/details/trace_id`.
- **Compatibilidad cliente actual:** preservada según pruebas de regresión admin core + check de contrato en PASS.

## Matriz GO/NO-GO (G1..G8)

| Gate | Criterio | Estado | Evidencia técnica |
|---|---|---|---|
| G1 | SUPERADMIN crea store en tenant A y solo visible en A | PASS | `test_admin_store_tenant_scope_and_idempotency`: store creado bajo tenant del actor y listado no incluye store de tenant B. |
| G2 | create user con store de otro tenant falla (`TENANT_STORE_MISMATCH`) | PASS | Ejecución dirigida HTTP: `POST /aris3/admin/users` devuelve `403` con `code=TENANT_STORE_MISMATCH` y `trace_id=trace-script-mismatch-1`. |
| G3 | MANAGER create tenant devuelve `403 PERMISSION_DENIED` | PASS | Ejecución dirigida HTTP: `POST /aris3/admin/tenants` con MANAGER devuelve `403` + `code=PERMISSION_DENIED` + trace_id. |
| G4 | idempotencia: FIRST=success, REPLAY=success, CONFLICT=409 | PASS | Ejecución dirigida HTTP en `POST /aris3/admin/stores`: first `201`, replay `201` con header `X-Idempotency-Result=IDEMPOTENCY_REPLAY`, conflict `409` con `IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD`. |
| G5 | `/users/{id}/actions` respeta tenant/store scope según política vigente | PASS | `test_admin_core`: manager denied other store (`STORE_SCOPE_MISMATCH`), manager allowed same store, admin tenant-wide same tenant, cross-tenant denied para admin y permitido para superadmin según política. |
| G6 | auditoría registrada en mutaciones críticas con trace_id | PASS | `test_audit_trace_admin` y ejecución dirigida muestran `AuditEvent(action=admin.store.create, result=success, trace_id=trace-script-idem-1)`. |
| G7 | errores devuelven trace_id consistentemente | PASS | `test_admin_error_responses_include_trace_id` + respuestas reales dirigidas (TENANT_STORE_MISMATCH / PERMISSION_DENIED / IDEMPOTENCY conflict) incluyen `trace_id`. |
| G8 | sin ruptura de contrato API (endpoints/schemas/envelope) | PASS | `python scripts/contract_safety_check.py --json` con 4 checks en PASS + envelope error validado en respuestas reales. |

## Ejemplos de respuesta HTTP (capturados)
### Éxito (idempotency FIRST)
```json
{
  "store": {
    "id": "d911bbd7-bfa0-48fe-8866-d0ee8282da15",
    "tenant_id": "26749b6f-2327-416e-b349-5e0a4c541a9c",
    "name": "Script Created Store",
    "created_at": "2026-02-14T04:40:19.314437"
  },
  "trace_id": "trace-script-idem-1"
}
```

### Error (tenant-store mismatch)
```json
{
  "code": "TENANT_STORE_MISMATCH",
  "message": "Store does not belong to tenant",
  "details": null,
  "trace_id": "trace-script-mismatch-1"
}
```

### Error (idempotency conflict)
```json
{
  "code": "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD",
  "message": "Idempotency key reused with different payload",
  "details": null,
  "trace_id": "trace-script-idem-1"
}
```

## Evidencia de replay/conflict idempotente
- FIRST: `201`
- REPLAY: `201` + header `X-Idempotency-Result=IDEMPOTENCY_REPLAY`
- CONFLICT: `409` + `code=IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD`

## Evidencia de audit event persistido
Evento consultado post-mutations:
```json
{
  "action": "admin.store.create",
  "result": "success",
  "trace_id": "trace-script-idem-1"
}
```

## Riesgos abiertos
- No se detectan riesgos bloqueantes para Step 5.
- Riesgo residual normal: mantener estas suites en CI de release para evitar regresiones futuras en scope/contrato.

## Decisión final
**GO** (todos los gates G1..G8 en PASS).

## Próximos pasos para iniciar app Python
1. Configurar variables de entorno productivas (`DATABASE_URL`, `SECRET_KEY`, credenciales de superadmin según política).
2. Ejecutar migraciones a `head`.
3. Iniciar servicio Python/FastAPI (comando estándar del proyecto) y correr smoke de health + admin core.
4. Monitorear auditoría e idempotencia en primeros flujos críticos post-arranque.
