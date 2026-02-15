# Release Notes SDK v1.1.1

## Day 9 — Top 3 P0

### Alcance ejecutado
- P0 #1: Telemetría de polling por estado (`CREATED`, `READY`, `FAILED`/terminal) en `wait_for_export_ready` vía hook opcional.
- P0 #2: Retries con jitter configurable para requests idempotentes en `HttpClient`.
- P0 #3: CLI smoke del SDK reforzada para evidencias JSON/log configurables por argumento.

### No-regresiones explícitas
- Se preserva config estricta: `ARIS3_API_BASE_URL` sigue siendo obligatoria.
- Polling de exports sigue usando bypass de cache por request (`use_get_cache=False`) sin side-effects globales.
- Comportamiento de cache GET global se mantiene intacto fuera del polling.

### Evidencia técnica Day 9
- `pytest ./clients/python/tests -q` en verde.
- `python ./clients/python/scripts/release_gate.py` en verde.
- Cobertura nueva de:
  - telemetría de polling,
  - jitter en retries,
  - CLI smoke con artifacts.

### Pendientes sugeridos para Day 10
- Consolidar dashboard de health SDK (P1 #4) con artifact de flaky/timeouts.
- Documentar contrato de cache por endpoint (P1 #6) en tabla formal para consumidores.
