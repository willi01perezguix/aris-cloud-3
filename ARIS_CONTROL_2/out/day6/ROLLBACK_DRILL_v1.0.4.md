# Rollback drill simulado — v1.0.4 -> v1.0.3

Objetivo de tiempo: **< 15 min**  
Fecha simulación: 2026-02-14

## Escenario
- Se detecta incidente funcional en RC v1.0.4.
- Acción: retorno controlado al build estable v1.0.3 previamente validado.

## Pasos
1. **Freeze de distribución RC** (1 min)
   - Detener rollout y comunicar ventana de rollback.
2. **Recuperar binario v1.0.3 + hash oficial** (2 min)
3. **Validar integridad** (2 min)
   - `Get-FileHash .\ARIS_CONTROL_2.exe -Algorithm SHA256`
4. **Reemplazar artefacto** (2 min)
   - Promover v1.0.3 en canal release.
5. **Smoke post-rollback** (5 min)
   - Login/sesión
   - `/me` + tenant efectivo
   - listados Stores/Users
   - acción admin permitida
   - export CSV filtrado
6. **Checklist cierre + monitoreo** (2 min)

## Resultado del drill (simulado)
- Duración estimada: **14 min**
- Estado: **PASS (procedural)**
- Restricción CI: validación ejecutable real pendiente en host Windows.

## Checklist post-rollback
- [ ] Versión runtime vuelve a v1.0.3.
- [ ] Hash coincide con release oficial.
- [ ] Login y sesión válidos.
- [ ] Tenant context consistente en Stores/Users.
- [ ] RBAC visual correcto (sin permisos indebidos).
- [ ] Idempotencia UI sin doble-submit.
- [ ] Export CSV filtrado operativo.
- [ ] Diagnóstico/export soporte disponible.
