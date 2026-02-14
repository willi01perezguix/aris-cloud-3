# 02 — UAT Final Checklist

## Matriz de pruebas funcionales
| ID | Caso | Pasos | Esperado | Resultado | Evidencia |
|---|---|---|---|---|---|
| UAT-001 | Login válido | Ingresar credenciales correctas | Sesión iniciada | PENDIENTE | Log/captura |
| UAT-002 | Login inválido | Ingresar credenciales incorrectas | Error controlado con mensaje | PENDIENTE | Log/captura |
| UAT-003 | `/me` autenticado | Ejecutar consulta con token válido | Datos de usuario/contexto | PENDIENTE | Log/captura |
| UAT-004 | `/me` no autenticado | Ejecutar sin token | Error de autenticación | PENDIENTE | Log/captura |
| UAT-005 | Tenant selector superadmin | Cambiar tenant en sesión superadmin | Contexto efectivo actualizado | PENDIENTE | Log/captura |
| UAT-006 | Stores/Users tenant correcto | Listar stores/users con tenant activo | Datos scope correcto | PENDIENTE | Log/captura |
| UAT-007 | Guardrail tenant-store mismatch create user | Crear user con combinación inválida | Bloqueo por guardrail | PENDIENTE | Log/captura |
| UAT-008 | Idempotency mutaciones | Repetir operación con misma key | No duplicación/consistencia | PENDIENTE | Log/captura |
| UAT-009 | Export CSV | Exportar listado filtrado | Archivo CSV válido en out/exports | PENDIENTE | Archivo generado |
| UAT-010 | Run/Build Windows | Ejecutar scripts run/build | Flujo sin errores críticos | PENDIENTE | Salida consola |
| UAT-011 | EXE abre y retorna salida válida | Ejecutar `dist/ARIS_CONTROL_2.exe` | Arranca correctamente | PENDIENTE | Salida consola/hash |

## Estado final UAT
- **Resultado global:** PENDIENTE (actualizar a PASS/FAIL al cierre).
- **Fecha/hora de cierre:** PENDIENTE.
- **Responsable:** PENDIENTE.
