# Backend usage matrix (ARIS-CLOUD-3)

Static inventory based on router wiring, tests, and client package presence.

## KEEP (uso confirmado)
- `/aris3/auth/login`, `/aris3/auth/change-password` (PATCH + POST alias): usados ampliamente por tests e integraciones.
- `/aris3/me`: cubierto en tests de contrato de error/autenticación.
- `/aris3/admin/tenants*`, `/aris3/admin/stores*`, `/aris3/admin/users*`, `/aris3/admin/settings/*`: cubiertos por tests core/admin y contrato.
- `/aris3/admin/access-control/*` y `/aris3/access-control/*`: cubiertos por tests de jerarquía, límites, idempotencia.
- `/health`, `/ready`: cubiertos por tests de readiness/ops.
- Routers POS/stock/transfers/reports/exports/assets: preservados (alto volumen de tests dedicados).

## LEGACY (compatibilidad temporal)
- `POST /aris3/auth/change-password`: alias deprecated mantenido con headers `Deprecation` y `Sunset`.
- `query_tenant_id` en create store: mantenido como query param deprecated.
- `is_active` en list users: mantenido como filtro deprecated derivado de `status`.

## REMOVE (sin uso demostrado)
- No se eliminaron rutas/módulos en este cambio para evitar riesgo sobre ARIS CONTROL/OPERADOR.
- Se priorizó hardening de contrato de errores y OpenAPI sin borrado destructivo.

## Evidencia base
- Router composition: `app/aris3/api.py`.
- Contratos y consumo de endpoints: `tests/` (admin/auth/access-control/health/ready/pos/transfers/reports/exports).
- Cliente en repo detectado: `clients/python/aris_control_center_app`.
- No se detectó carpeta explícita de ARIS_OPERADOR en el monorepo.
