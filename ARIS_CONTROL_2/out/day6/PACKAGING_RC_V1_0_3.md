# Day 6 — Packaging RC v1.0.3

Fecha: 2026-02-14

## Scripts oficiales esperados
- `scripts/windows/preflight_release.ps1`
- `scripts/windows/smoke_release.ps1`
- `scripts/windows/build_control_center.ps1`

## Resultado en entorno actual (CI Linux)
- Estado: **BLOCKED por limitación de plataforma**.
- Evidencia:
  - `pwsh --version` -> `bash: command not found: pwsh`
  - `python -m PyInstaller --version` -> `No module named PyInstaller`
- Verificación de scaffold de packaging: **PASS** con `python clients/python/tools/packaging_verify.py --packaging-root clients/python/packaging`.
  - Artefactos: `artifacts/packaging/build_manifest_20260214T205955Z.json`, `artifacts/packaging/packaging_verify_20260214T205955Z.md`

## Artefacto RC (.exe) + SHA256
- `dist/ARIS_CONTROL_2.exe`: **NO GENERADO en este entorno**.
- SHA256: **N/A**.
- Tamaño: **N/A**.
- Timestamp: **N/A**.

## Procedimiento reproducible (host Windows release)
1. `./scripts/windows/preflight_release.ps1`
2. `./scripts/windows/smoke_release.ps1`
3. `./scripts/windows/build_control_center.ps1`
4. `Get-Item .\dist\ARIS_CONTROL_2.exe | Select-Object Name,Length,LastWriteTime`
5. `Get-FileHash .\dist\ARIS_CONTROL_2.exe -Algorithm SHA256`
6. `./dist/ARIS_CONTROL_2.exe` (validación de arranque)

## Registro requerido al ejecutar en Windows
| archivo | tamaño | timestamp | sha256 |
|---|---:|---|---|
| `ARIS_CONTROL_2.exe` | _pending_ | _pending_ | _pending_ |
