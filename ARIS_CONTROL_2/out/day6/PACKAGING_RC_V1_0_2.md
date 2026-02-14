# Day 6 — Packaging RC v1.0.2

Fecha: 2026-02-14

## Script oficial esperado
- `scripts/windows/build_control_center.ps1`

## Ejecución en entorno actual
- Estado: **BLOCKED por limitación de entorno**.
- Hallazgos:
  - `pwsh` no está instalado en el runner Linux.
  - Instalación de `pyinstaller` bloqueada por restricción de red/proxy (403).

## Evidencia de comandos
- `pwsh --version` → `bash: command not found: pwsh`
- `python -m pip install pyinstaller` → `No matching distribution found for pyinstaller` (proxy 403)

## Resultado RC
- `dist/ARIS_CONTROL_2.exe`: **No generado en este entorno**.
- SHA256: **N/A (sin .exe)**.
- Tamaño/fecha/ruta: **N/A (sin artefacto)**.

## Procedimiento reproducible en host Windows release
1. `./scripts/windows/preflight_release.ps1`
2. `./scripts/windows/smoke_release.ps1`
3. `./scripts/windows/build_control_center.ps1`
4. `Get-FileHash .\dist\ARIS_CONTROL_2.exe -Algorithm SHA256`
5. Verificar arranque: `./dist/ARIS_CONTROL_2.exe`
