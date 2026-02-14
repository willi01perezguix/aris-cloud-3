# v1.0.5 Scope

Estado base: `v1.0.4` estable.
Versión de trabajo: `v1.0.5-dev`.
Endpoint base por defecto: `https://aris-cloud-3-api-pecul.ondigitalocean.app/`.

## Permitido (scope freeze)
- UX de operación (mensajes, atajos, claridad de estado).
- Estabilidad y degradación controlada ante fallas transitorias.
- Observabilidad y diagnóstico operativo.
- Soporte operacional y evidencia de smoke.
- Rendimiento UI/flujo en listados sin tocar contrato API.

## No permitido
- Cambios de contrato API (endpoints, payloads, códigos funcionales esperados).
- Refactors grandes o cambios estructurales de alto riesgo.
- Cambios que alteren guardrails de tenant/store/user del backend.

## Criterio de cierre de ciclo
- `v1.0.5` cierra la etapa de estabilización/finalización.
- Siguiente salto de versión: `v1.1.0` únicamente si hay cambio mayor.
