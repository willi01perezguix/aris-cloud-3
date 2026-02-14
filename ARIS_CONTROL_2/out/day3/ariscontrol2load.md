# ariscontrol2load — Day 3 v1.1.0

Checkpoint activo:
- `ARIS_CONTROL_2/out/day3/ariscontrol2save_delta_day3_v1_1_0.md`

Estado:
- Data Access Layer cliente unificada para Tenants/Stores/Users.
- Política de red homogénea (retry GET, no retry ciego en mutaciones, timeout configurable).
- Cache GET TTL corto + invalidación segura post-mutación.
- Cancelación por cambio de contexto para estabilidad en navegación rápida.
- Trazabilidad técnica unificada con `last_operation`.
