# ariscontrol2save — Delta-only Day 3 v1.1.0

Fecha: 2026-02-14  
Proyecto: ARIS_CONTROL_2  
Fase: v1.1.0 Day 3

## Delta aplicado
- Se consolidó una capa cliente unificada para Tenants/Stores/Users (`AdminDataAccessClient`) con operaciones GET y mutaciones con `RetryableMutation` manual.
- Se unificó la política de headers en mutaciones críticas: `Authorization` (desde `BaseClient`), `Idempotency-Key` y `transaction_id`.
- Se incorporó política homogénea en `HttpClient`:
  - retry/backoff para GET/HEAD,
  - sin retry automático para mutaciones,
  - timeout configurable por `ClientConfig`.
- Se añadió normalización de error transversal (`NormalizedError`) con formato: `code`, `message`, `trace_id`, `type` (`network/auth/validation/conflict/internal`).
- Se implementó cache temporal de lectura GET (TTL corto) y invalidación selectiva tras mutaciones por prefijos de recurso.
- Se agregó cancelación por cambio de contexto (`switch_context`) para descartar respuestas viejas y evitar mezcla tenant/rol/sesión.
- Se registró trazabilidad técnica por operación en `last_operation` (módulo, operación, duración, resultado, trace_id).
- Se fijó endpoint base por defecto del cliente en `https://aris-cloud-3-api-pecul.ondigitalocean.app/`.
- Se añadieron unit tests para: mapper de errores, invalidación cache post-mutación, cancelación por contexto y política retry GET vs mutación.

## No-delta (explícito)
- Sin cambios silenciosos de contrato API.
- Sin modificaciones en flujo base Tenant/Store/User del backend.

## Riesgos + rollback simple
- Riesgo medio-bajo: cambios encapsulados en SDK cliente y pruebas unitarias nuevas.
- Rollback simple: revertir commit Day 3 v1.1.0.

## Continuidad de alias
- Alias checkpoint: `ariscontrol2save` -> este archivo.
- Reanudación: `ariscontrol2load` desde `ARIS_CONTROL_2/out/day3/ariscontrol2load.md`.
