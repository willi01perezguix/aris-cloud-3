# ARIS_CONTROL_2 — Changelog interno v1.0.2-dev

## 2026-02-14 — Kickoff Day 1

### Alcance
- Sin cambios de contrato API.
- Se mantiene endpoint por defecto: `https://aris-cloud-3-api-pecul.ondigitalocean.app/`.
- Cambios incrementales en UX/operación y pruebas mínimas de regresión.

### Cambios implementados
1. **UX (quick win)**
   - Mensajes de error API con diagnóstico accionable por tipo de falla (network/authz/server).
   - Estado de carga explícito (`Cargando datos...`) en listados.
   - Estado vacío explícito con sugerencia de recuperación.
2. **Operación (quick win)**
   - Chequeo visible de conectividad API al inicio de la app.
   - Opción de menú para diagnóstico básico (`/health` y `/ready`) con latencia y detalle.
3. **Regresión mínima**
   - Nuevas pruebas unitarias para diagnóstico API y mensajes de error.

### Riesgos y mitigación
- **Riesgo bajo**: solo cambios de presentación/mensajería en cliente CLI.
- **Mitigación**: sin cambios en payloads ni rutas API; cobertura unitaria de helpers nuevos.

### Rollback
- Revertir commit de `feature/v1.0.2-kickoff` restaura el comportamiento v1.0.1 en cliente.

## 2026-02-14 — Hardening Day 6

### Alcance
- QA integral de flujos críticos cliente (login/session, tenant/store/user, idempotencia, RBAC, diagnóstico/export).
- Preparación de evidencias de smoke E2E guiado y rollback drill simulado.
- Sin cambios de contrato API.

### Evidencia generada
- Reporte consolidado de pruebas Day 6: `out/day6/DAY6_TEST_REPORT.md`.
- Evidencia smoke E2E guiado: `out/day6/E2E_SMOKE_EVIDENCE.md`.
- Resultado de packaging RC en entorno CI: `out/day6/PACKAGING_RC_V1_0_2.md`.
- Rollback drill documentado: `docs/05_DAY6_ROLLBACK_DRILL.md`.
- Memo Go/No-Go Day 7: `docs/06_DAY7_GO_NO_GO_MEMO.md`.

### Estado
- Suite de pruebas automatizadas objetivo en verde.
- Packaging `.exe` pendiente de ejecución en host Windows release.

## 2026-02-14 — Final Release Gate Day 7
- Decisión formal de gate emitida en `out/day7/DAY7_RELEASE_GATE_DECISION.md` (estado NO-GO).
- Plan hotfix operativo y tiempos definidos en `out/day7/DAY7_HOTFIX_PLAN.md`.
- Handoff operativo, bitácora 72h y backlog v1.0.3 inicial documentados en `out/day7/`.
