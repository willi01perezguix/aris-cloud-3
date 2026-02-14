# ARIS_CONTROL_2 — Plan de Estabilización Semanal (7 días) v1

## Estado de activación
- **Estado:** `BLOCKED (NO-GO)`
- **Motivo:** Gate inicial de Prompt 15 no aprobado (Prompt 14 no está en GO, release estable v1.0.0 no evidenciada, smoke post-release sin ejecución real).
- **Uso:** Este plan queda preaprobado para ejecución inmediata al levantar bloqueantes del gate.

## Objetivo general
Reducir riesgo operativo post-release, asegurar estabilidad de login/sesión y flujos Tenants/Stores/Users, y preparar ejecución de release `v1.0.1` bajo control de cambio mínimo.

## D1 — Confirmación de baseline estable
- **Objetivo diario:** Validar baseline release estable y trazabilidad de artefactos.
- **Checklist técnico:**
  1. Confirmar versión estable promovida (`v1.0.0` o equivalente formal).
  2. Verificar evidencia de `.exe` + SHA256 publicado.
  3. Verificar endpoint por defecto obligatorio sin cambios.
- **Validación mínima:** Manifest y release notes consistentes.
- **Cierre diario:** PASS si hay evidencia verificable; FAIL en cualquier inconsistencia.
- **Evidencia requerida:** Captura de manifest/release notes + hash.

## D2 — Salud API y sesión
- **Objetivo diario:** Validar conectividad API y robustez de sesión.
- **Checklist técnico:**
  1. Smoke login y sesión activa/inactiva.
  2. Verificar timeout/renovación de sesión.
  3. Confirmar manejo de 401/403 sin crash.
- **Validación mínima:** 0 crash UI en flujo de autenticación.
- **Cierre diario:** PASS si login/sesión estables.
- **Evidencia requerida:** Logs de smoke + reporte corto de incidencias.

## D3 — Integridad tenant->store->user
- **Objetivo diario:** Asegurar contrato funcional multi-contexto.
- **Checklist técnico:**
  1. Probar filtros tenant->store->user.
  2. Validar aislamiento de contexto por tenant.
  3. Confirmar navegación cruzada sin fuga de datos.
- **Validación mínima:** Resultados esperados en casos nominales y de borde.
- **Cierre diario:** PASS si no hay desalineación de contexto.
- **Evidencia requerida:** Matriz de pruebas ejecutada (subset D3).

## D4 — Robustez de errores operativos
- **Objetivo diario:** Endurecer manejo de fallos controlados.
- **Checklist técnico:**
  1. Simular caída temporal API.
  2. Validar mensajes de error y reintento.
  3. Confirmar no-crash en rutas críticas.
- **Validación mínima:** Errores recuperables correctamente comunicados.
- **Cierre diario:** PASS si no hay crash ni pérdida de estado crítico.
- **Evidencia requerida:** Evidencia de pruebas negativas.

## D5 — Empaquetado y arranque cliente
- **Objetivo diario:** Verificar artefacto de distribución y startup.
- **Checklist técnico:**
  1. Ejecutar smoke de empaquetado oficial del repo.
  2. Arranque limpio de `.exe`.
  3. Verificación endpoint por defecto configurado.
- **Validación mínima:** Build/arranque sin bloqueo crítico.
- **Cierre diario:** PASS si `.exe` inicia y conecta.
- **Evidencia requerida:** Log de build/smoke + hash.

## D6 — Pre-release v1.0.1 readiness
- **Objetivo diario:** Consolidar criterios GO/NO-GO para v1.0.1.
- **Checklist técnico:**
  1. Revisar Bug Bar/SLA y estado de severidades.
  2. Confirmar que backlog IN de v1.0.1 cumple criterios.
  3. Validar plan rollout/rollback actualizado.
- **Validación mínima:** 0 SEV1 y SEV2 con mitigación definida.
- **Cierre diario:** PASS con paquete de release listo.
- **Evidencia requerida:** Checklist de readiness firmado por roles.

## D7 — Cierre semanal y handoff
- **Objetivo diario:** Entregar estado operativo y siguiente ciclo.
- **Checklist técnico:**
  1. Consolidar incidentes, riesgos y deuda inmediata.
  2. Actualizar cadencia semanal y propietarios.
  3. Definir plan de acción de la semana siguiente.
- **Validación mínima:** Documentación y responsables asignados.
- **Cierre diario:** PASS con handoff completo.
- **Evidencia requerida:** Minuta de handoff + backlog actualizado.
