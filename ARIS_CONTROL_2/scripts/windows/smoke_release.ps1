param()
$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path "$PSScriptRoot\..\..")

pytest -q

Write-Host "[SMOKE] Ejecutando run_control_center_dev.ps1"
& ".\scripts\windows\run_control_center_dev.ps1"

Write-Host "[SMOKE] Ejecutando build_control_center.ps1"
& ".\scripts\windows\build_control_center.ps1"

if (-not (Test-Path ".\dist\ARIS_CONTROL_2.exe")) {
  throw "No se encontró dist/ARIS_CONTROL_2.exe después del build."
}

Write-Host "[OK] dist/ARIS_CONTROL_2.exe generado"
Get-FileHash ".\dist\ARIS_CONTROL_2.exe" -Algorithm SHA256
