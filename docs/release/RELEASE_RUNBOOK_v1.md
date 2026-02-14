# RELEASE_RUNBOOK_v1

## 1) Validación previa (baseline)
1. Confirmar rama de cierre operativo: `release/prompt13-finalize`.
2. Verificar endpoint por defecto:
   - `ARIS3_BASE_URL=https://aris-cloud-3-api-pecul.ondigitalocean.app/`
3. Ejecutar pruebas mínimas:
   - `PYTHONPATH=. pytest -q` (en `ARIS_CONTROL_2/`)
   - `PYTHONPATH=. pytest -q tests/unit/test_smoke.py`
4. Confirmar que no se alteró contrato API ni flujo tenant/store/user (solo cambios operativos/documentales).

## 2) Build y paquete
### Flujo oficial documentado en repo
- `scripts/windows/preflight_release.ps1`
- `scripts/windows/build_control_center.ps1`
- `scripts/windows/smoke_release.ps1`

### Mapeo ejecutado en este entorno Linux
- PowerShell no disponible (`pwsh` no instalado), por lo tanto no se pudo ejecutar `*.ps1`.
- Se intentó reproducir el build oficial instalando `pyinstaller`, pero el entorno no permitió descarga por proxy (403), por lo que no fue posible regenerar `dist/ARIS_CONTROL_2.exe`.

## 3) Promoción RC -> estable
Si `gh` está autenticado:
1. Revisar release RC4:
   - `gh release view v1.0.0-rc4`
2. Si la política del repo usa nuevo tag GA:
   - crear tag/release estable `v1.0.0` reutilizando notas y asset validado.
3. Si la política usa edición del release existente:
   - marcar `v1.0.0-rc4` como no pre-release y actualizar nombre/notas a GA.

## 4) Rollback
1. Si el estable presenta error crítico:
   - revertir visibilidad/promoción del release estable.
   - restituir release RC validado (`v1.0.0-rc4`) como referencia operativa.
2. Comunicar rollback en canal operativo con:
   - hora UTC, motivo, impacto tenant/store/user, estado mitigación.

## 5) Monitoreo primeras 24h
- Ventanas: 0h, 1h, 4h, 8h, 24h.
- Verificar:
  - login/auth
  - `/me` y contexto efectivo
  - listados tenant/store/user con filtros/paginación
  - errores HTTP mapeados (timeouts, 4xx/5xx)
- Criterio de incidente crítico:
  - caída total de login,
  - pérdida de aislamiento tenant,
  - corrupción de flujo store/user.
