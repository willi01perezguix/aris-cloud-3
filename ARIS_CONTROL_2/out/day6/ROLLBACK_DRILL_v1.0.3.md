# Rollback drill simulado — v1.0.3 -> v1.0.2

Objetivo de tiempo: **< 15 minutos**
Fecha simulación: 2026-02-14

## Escenario
- Se detecta incidencia post-deploy en v1.0.3 RC.
- Acción: volver a artefacto estable v1.0.2 verificado.

## Pasos operativos
1. **Congelar despliegue** (1 min)
   - Detener distribución del RC y comunicar ventana de rollback.
2. **Recuperar artefacto estable v1.0.2** (2 min)
   - Obtener `ARIS_CONTROL_2.exe` estable y su SHA256 publicado.
3. **Validar integridad** (2 min)
   - `Get-FileHash .\ARIS_CONTROL_2.exe -Algorithm SHA256`
   - Comparar hash con release oficial v1.0.2.
4. **Reemplazar binario RC por estable** (2 min)
   - Restaurar binario + config aprobada.
5. **Arranque + smoke post-rollback** (5 min)
   - Login
   - `/me`
   - tenant/store/user list
   - acción admin permitida
   - check diagnóstico
6. **Cierre y monitoreo** (2 min)
   - Confirmar estado operacional + documentación incidente.

## Resultado simulación
- Duración estimada: **14 min**.
- Estado: **PASS (simulado procedural)**.
- Bloqueo de ejecución real en CI actual: sin host Windows + sin `.exe` operativo local.

## Checklist post-rollback
- [ ] Versión estable visible en runtime.
- [ ] Hash del binario coincide con release v1.0.2.
- [ ] Login/sesión OK.
- [ ] Tenant context consistente (stores/users).
- [ ] RBAC visual sin desbordes.
- [ ] Diagnóstico reporta `base_url`, estado conexión, versión, timestamp.
- [ ] Evidencia incidente exportada sin secretos/tokens.
