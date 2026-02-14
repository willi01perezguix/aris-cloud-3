Param(
  [string]$PythonExe = "python"
)

$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path "$PSScriptRoot/../..")
& $PythonExe -m PyInstaller --clean --noconfirm packaging/control_center.spec.template
