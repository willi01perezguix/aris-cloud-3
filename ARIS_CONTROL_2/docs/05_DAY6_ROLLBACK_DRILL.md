# Day 6 — Rollback drill (simulación controlada)

## Objetivo
Validar que el retorno a la versión estable previa de ARIS_CONTROL_2 sea ejecutable en menos de 15 minutos, sin cambios de contrato API.

## Preconditions checklist
- [ ] Versión previa estable identificada (tag/commit + release asset).
- [ ] Binario previo íntegro (SHA256 registrado y verificado).
- [ ] Operador con permisos para reemplazo de binario en host Windows.
- [ ] Runbook y smoke post-rollback disponibles.

## Procedimiento de rollback (target <15 min)
1. **Congelar operación de release** (1 min)
   - Detener despliegue del RC actual.
2. **Localizar release estable previa** (2 min)
   - Obtener `ARIS_CONTROL_2.exe` estable y su SHA256 publicado.
3. **Verificar integridad del binario previo** (1 min)
   - `Get-FileHash .\ARIS_CONTROL_2.exe -Algorithm SHA256`
   - Comparar contra hash oficial.
4. **Reemplazo de binario** (2 min)
   - Sustituir binario RC por estable previa en ruta operativa.
5. **Arranque y smoke post-rollback** (5 min)
   - Abrir app.
   - Login SUPERADMIN.
   - Ver `/me`, tenant selector, listado stores/users.
   - Abrir diagnóstico y validar base URL oficial.
6. **Cierre y comunicación** (2 min)
   - Registrar timestamp, operador, hash usado y resultado smoke.

Tiempo total objetivo: **13 minutos**.

## Simulación Day 6
- Estado: **SIMULACIÓN DOCUMENTAL COMPLETADA**.
- Resultado: secuencia validada como ejecutable en `<15 min` bajo disponibilidad de artefactos Windows.
- Restricción del entorno CI actual: no hay host Windows ni `.exe` para ejecutar sustitución real.

## Verificación post-rollback
- [ ] App abre sin errores.
- [ ] Login/session funcional.
- [ ] Tenant context activo y consistente.
- [ ] RBAC gating conserva restricciones esperadas.
- [ ] Diagnóstico muestra `base_url`, conectividad, versión y timestamp.
