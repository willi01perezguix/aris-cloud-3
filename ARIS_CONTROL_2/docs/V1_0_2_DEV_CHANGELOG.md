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
