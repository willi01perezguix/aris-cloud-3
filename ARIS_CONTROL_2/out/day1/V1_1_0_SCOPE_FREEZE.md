# Scope v1.1.0 (Freeze inicial Day 1)

Estado base: `v1.0.5` estable (sin cambios de contrato API en Day 1).
Rama de trabajo: `feature/v1.1.0-day1-kickoff`.
Versión de trabajo: `v1.1.0-dev`.
Endpoint base por defecto: `https://aris-cloud-3-api-pecul.ondigitalocean.app/`.

## Objetivos mayores permitidos en v1.1.0
1. UX operacional: reducir tiempo de diagnóstico e incident response en consola.
2. Seguridad/permisos: robustecer RBAC + scope por tenant/store sin regresiones.
3. Observabilidad/soporte: trazabilidad homogénea y paquetes de evidencia replicables.
4. Performance/estabilidad: degradación controlada, retry defensivo y smoke continuo.

## Fuera de alcance
- Cambios silenciosos de contrato API.
- Refactors masivos cross-stack sin feature flag.
- Alteración de flujo base Tenant/Store/User fuera de plan de validación.
- Introducción de dependencias críticas sin plan de rollback.

## Riesgos y mitigaciones
- Riesgo: regresión operativa en flujo core admin.
  - Mitigación: PRs pequeños por objetivo + smoke mínimo por módulo.
- Riesgo: expansión de alcance (scope creep) en semana 1.
  - Mitigación: freeze de objetivos y backlog fuera de alcance documentado.
- Riesgo: deuda de permisos y efectos laterales RBAC.
  - Mitigación: pruebas de guardrails tenant/store/user en cada track.

## Criterio de salida de etapa v1.1.0
- Entregables de tracks A-D cerrados con evidencia verificable.
- Cero regresiones críticas en flujo Tenant/Store/User.
- Cambios con contrato API versionado explícitamente y documentado.
- Runbook de rollback actualizado y validado por smoke final.

## Separación de mejoras
### Mejoras sin contrato (permitidas sin versionado API)
- UX de consola, badges de estado, atajos operativos.
- Mejoras de logging/diagnóstico local y exportes operativos.
- Optimizaciones de performance internas sin alterar payloads.

### Mejoras con contrato versionado (obligatorio versionar)
- Nuevos endpoints o cambios en request/response existentes.
- Nuevos códigos funcionales expuestos a clientes SDK/UI.
- Cambios de semántica de permisos/scope que impacten API pública.
