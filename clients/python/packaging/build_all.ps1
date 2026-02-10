param([switch]$DryRun)
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
./build_core.ps1 -DryRun:$DryRun
./build_control_center.ps1 -DryRun:$DryRun
