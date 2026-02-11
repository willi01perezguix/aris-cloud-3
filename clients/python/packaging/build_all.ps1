param(
  [switch]$DryRun,
  [switch]$CiMode,
  [string]$OutDir,
  [string]$VersionOverride
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$coreOutDir = if ($OutDir) { Join-Path $OutDir "core" } else { $null }
$controlOutDir = if ($OutDir) { Join-Path $OutDir "control_center" } else { $null }

& ./build_core.ps1 -DryRun:$DryRun -CiMode:$CiMode -OutDir:$coreOutDir -VersionOverride:$VersionOverride
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& ./build_control_center.ps1 -DryRun:$DryRun -CiMode:$CiMode -OutDir:$controlOutDir -VersionOverride:$VersionOverride
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "build_all completed successfully"
