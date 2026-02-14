# 04 — Operación Diaria

## 1) Rutina diaria
### Arranque
1. Abrir PowerShell en `ARIS_CONTROL_2/`.
2. Activar `.venv` (si aplica).
3. Ejecutar smoke de operación:
   ```powershell
   .\scripts\windows\run_control_center_dev.ps1
   ```

### Verificación
- Login exitoso.
- `/me` responde con contexto correcto.
- Tenant activo consistente con operación del día.

### Cierre
- Exportar evidencias (logs/CSV/hash si hubo build).
- Registrar resultados en `out/uat/UAT_RESULTS_TEMPLATE.md`.

## 2) Validaciones rápidas
```powershell
git status --short
pytest -q
```

## 3) Monitoreo mínimo cliente
- Errores de autenticación repetidos.
- Timeouts de red (revisar `ARIS3_TIMEOUT_SECONDS`).
- Mismatches de tenant/store en operaciones de users.

## 4) Captura de evidencias operativas
- Captura consola con timestamp.
- Guardar `trace_id` de errores.
- Adjuntar hash SHA256 cuando se genere ejecutable.
