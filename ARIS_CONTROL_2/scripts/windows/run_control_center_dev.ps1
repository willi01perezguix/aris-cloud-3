Param(
  [string]$PythonExe = "python"
)

$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path "$PSScriptRoot/../..")
& $PythonExe -m aris_control_2.app.main
