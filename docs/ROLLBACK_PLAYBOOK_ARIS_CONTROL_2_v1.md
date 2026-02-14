# ROLLBACK PLAYBOOK ARIS_CONTROL_2 v1

## Triggers de rollback
- Error crítico en login/me/session context.
- Scope de tenant incorrecto en Stores/Users.
- Acciones de usuario permitidas sin permiso o sin tenant efectivo.
- Errores sin `trace_id` o con fuga de secretos en logs.
- Falla de arranque de artefacto empaquetado en Windows.

## Procedimiento
1. **Detener distribución RC actual**
   - Congelar despliegues del artefacto nuevo.
2. **Volver al artefacto estable previo**
   - Reinstalar binario/control package anterior validado.
3. **Revertir configuración local de launcher**
   - Restaurar scripts de ejecución previos en estaciones de operación.
4. **Verificación post-rollback**
   - Login correcto.
   - Navegación básica disponible.
   - Operaciones Stores/Users con scope correcto.
   - Errores con `trace_id` visible.
5. **Registro de incidente**
   - Documentar causa raíz, alcance, fecha/hora y plan de remediación.

## Checklist de validación post-rollback
- [ ] Build estable anterior arranca sin fallas.
- [ ] Flujo login + `/me` correcto.
- [ ] Guardrails tenant/RBAC funcionando.
- [ ] Logs sin secretos y con trazabilidad mínima.

## Remediación mínima (archivo por archivo)
- `ARIS_CONTROL_2/aris_control_2/app/application/use_cases/*.py`: ajustar enforcement RBAC/tenant e idempotencia.
- `ARIS_CONTROL_2/aris_control_2/app/infrastructure/errors/error_mapper.py`: asegurar mapeo semántico de errores.
- `ARIS_CONTROL_2/aris_control_2/app/infrastructure/logging/logger.py`: preservar contrato de logging.
- `ARIS_CONTROL_2/scripts/windows/*.ps1` y `ARIS_CONTROL_2/packaging/control_center.spec.template`: corregir empaquetado/arranque Windows.
- `ARIS_CONTROL_2/tests/unit|integration/*`: reforzar cobertura de regresión de la falla detectada.
