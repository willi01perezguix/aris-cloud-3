# SMOKE_MATRIX_v1

| Área | Caso mínimo | Resultado esperado | Estado |
|---|---|---|---|
| Login | Autenticación con credenciales válidas | Token de sesión + estado autenticado | PASS (cubierto por suite) |
| `/me` contexto | Obtener contexto efectivo post-login | tenant efectivo consistente | PASS (suite integración existente) |
| Tenant | Listado tenant por contexto | datos restringidos al tenant activo | PASS (suite integración existente) |
| Store | Listado store por tenant | no fuga cross-tenant | PASS (suite integración existente) |
| User | Listado/acciones user por tenant | respetar alcance tenant/store/user | PASS (suite integración existente) |
| Endpoint API | Cargar config sin env | usar `https://aris-cloud-3-api-pecul.ondigitalocean.app/` | PASS |
| Manejo de errores | timeout/4xx/5xx mapeados | error controlado sin crash de flujo | PASS (tests SDK/UI) |
| Arranque local mínimo | `pytest -q tests/unit/test_smoke.py` | ejecución en verde | PASS |
| Build Windows | `scripts/windows/build_control_center.ps1` | generar `dist/ARIS_CONTROL_2.exe` | BLOCKED (pwsh ausente) |
