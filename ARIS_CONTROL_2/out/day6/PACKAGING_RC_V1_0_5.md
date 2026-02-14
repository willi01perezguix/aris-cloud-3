# RC build v1.0.5 — evidencia de empaquetado

## Script oficial
Comando objetivo (host Windows):
- `pwsh -NoProfile -File scripts/windows/build_control_center.ps1`

## Ejecución en este entorno
- Comando ejecutado: `pwsh -NoProfile -File scripts/windows/build_control_center.ps1`
- Resultado: **BLOCKED**
- Evidencia: `bash: command not found: pwsh`

## Estado de artefacto `.exe`
- Nombre archivo: **N/A (bloqueado por entorno Linux sin PowerShell)**
- Tamaño: **N/A**
- Timestamp: **N/A**
- SHA256: **N/A**

## Validación de arranque en entorno limpio
- Estado: **PENDIENTE (requiere runner Windows limpio)**.

## Plan mínimo para cierre operativo
1. Ejecutar build oficial en host Windows con `pwsh`.
2. Confirmar existencia `dist/ARIS_CONTROL_2.exe`.
3. Registrar:
   - `Get-Item .\dist\ARIS_CONTROL_2.exe | Select Name,Length,LastWriteTime`
   - `Get-FileHash .\dist\ARIS_CONTROL_2.exe -Algorithm SHA256`
4. Ejecutar smoke de arranque con `scripts/windows/smoke_release.ps1`.
