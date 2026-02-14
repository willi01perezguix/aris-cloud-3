param(
  [string]$Version = "v1.0.0"
)
$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path "$PSScriptRoot\..\..")

if (-not (Test-Path ".\out\release")) {
  New-Item -ItemType Directory -Path ".\out\release" | Out-Null
}

$branch = (git branch --show-current).Trim()
$commit = (git rev-parse --short HEAD).Trim()
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss zzz"
$output = ".\out\release\release_notes_$Version.md"

@"
# Release Notes $Version

> Plantilla base autogenerada. Editar antes de publicar.

- Fecha/Hora de generación: $timestamp
- Rama: $branch
- Commit: $commit

## Resumen
- Estabilización operativa ARIS_CONTROL_2.
- Manual operativo y runbook de release.
- Checklist UAT final y plantillas de evidencia.
- Hardening de preflight/smoke para salida estable.

## Validaciones sugeridas
- [ ] pytest -q
- [ ] run_control_center_dev.ps1
- [ ] build_control_center.ps1
- [ ] hash SHA256 de dist/ARIS_CONTROL_2.exe

## Assets esperados
- dist/ARIS_CONTROL_2.exe
- SHA256 del binario
"@ | Set-Content -Path $output -Encoding UTF8

Write-Host "Release notes generadas: $output"
