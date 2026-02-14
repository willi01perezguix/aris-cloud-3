# ariscontrol2save — Delta-only Day 2 v1.1.0

## Baseline conservado
- Endpoint base por defecto sin cambios:
  `https://aris-cloud-3-api-pecul.ondigitalocean.app/`.
- Flujo base Tenant/Store/User se mantiene.
- Sin cambios de contrato API.

## Delta aplicado (Day 2)
1. Shell de navegación v1.1.0 integrado en cliente:
   - Header operativo (conexión + tenant activo).
   - Sidebar por módulos.
   - Context bar visible (tenant/store/rol/conexión).
   - Rutas protegidas con bloqueo explícito.
2. Permission map centralizado para menús y acciones del shell.
3. Tenant context hardening en punto único de resolución de tenant cliente.
4. Feature flags cliente para cambios mayores con fallback seguro a comportamiento previo.
5. Acceso rápido “Cambiar tenant” habilitado para SUPERADMIN.
6. Unit tests Day 2 verdes:
   - permission map allow/deny,
   - tenant resolver por rol,
   - rutas protegidas del shell.

## Feature flags activas Day 2
- `ARIS_UI_NAV_SHELL_V110=true`
- `ARIS_UI_TENANT_SWITCHER_V110=true`
- `ARIS_UI_DIAGNOSTICS_ENABLED=true`
- `ARIS_UI_INCIDENTS_ENABLED=true`
- `ARIS_UI_SUPPORT_EXPORT_ENABLED=true`

## Riesgos y rollback simple
- Riesgo: configuración de permisos de menú demasiado restrictiva para ciertos roles.
  - Mitigación: ajustar permission map central.
- Riesgo: módulos deshabilitados accidentalmente por feature flags.
  - Mitigación: revisar variables de entorno en startup.
- Rollback simple:
  1. Desactivar shell nuevo: `ARIS_UI_NAV_SHELL_V110=false`.
  2. Mantener menú operativo v1.0.5 sin tocar API.

## Continuidad
- Alias checkpoint: `ariscontrol2save` -> este archivo.
- Reanudación: `ariscontrol2load` desde este delta-only Day 2.
