# Day 6 — RC build v1.0.4

Fecha: 2026-02-14

## Scripts oficiales
- `scripts/windows/preflight_release.ps1`
- `scripts/windows/smoke_release.ps1`
- `scripts/windows/build_control_center.ps1`

## Resultado en entorno actual
- Comando ejecutado: `pwsh -NoProfile -Command "./scripts/windows/build_control_center.ps1"`
- Estado: **BLOCKED**
- Evidencia: `bash: command not found: pwsh`

Verificación adicional:
- `python -m PyInstaller --version` -> `No module named PyInstaller`

## Artefacto RC requerido
| Campo | Valor |
|---|---|
| Archivo | `dist/ARIS_CONTROL_2.exe` |
| Tamaño | N/A (no generado en CI Linux) |
| Timestamp | N/A |
| SHA256 | N/A |

## Validación de arranque RC en entorno limpio
- Estado: **PENDIENTE** (requiere host Windows limpio).

## Procedimiento para cierre en Day 7 (runner Windows)
1. `./scripts/windows/preflight_release.ps1`
2. `./scripts/windows/smoke_release.ps1`
3. `./scripts/windows/build_control_center.ps1`
4. `Get-Item .\dist\ARIS_CONTROL_2.exe | Select Name,Length,LastWriteTime`
5. `Get-FileHash .\dist\ARIS_CONTROL_2.exe -Algorithm SHA256`
6. Ejecutar `.\dist\ARIS_CONTROL_2.exe` y validar arranque.
