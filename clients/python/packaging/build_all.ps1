param(
  [switch]$DryRun,
  [switch]$CiMode,
  [string]$OutDir,
  [string]$VersionOverride
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $true

function Fail([string]$Message) {
  Write-Error $Message
  exit 1
}

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$coreScript = Join-Path $root "./build_core.ps1"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$controlCenterScript = Join-Path $root "./build_control_center.ps1"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (-not (Test-Path $coreScript -PathType Leaf)) {
  Fail "Preflight failed: missing script at $coreScript"
}
if (-not (Test-Path $controlCenterScript -PathType Leaf)) {
  Fail "Preflight failed: missing script at $controlCenterScript"
}

$coreOutDir = if ($OutDir) { Join-Path $OutDir "core" } else { $null }
$controlOutDir = if ($OutDir) { Join-Path $OutDir "control_center" } else { $null }

& $coreScript -DryRun:$DryRun -CiMode:$CiMode -OutDir:$coreOutDir -VersionOverride:$VersionOverride
if ($LASTEXITCODE -ne 0) {
  Fail "build_core.ps1 failed with exit code $LASTEXITCODE"
}

& $controlCenterScript -DryRun:$DryRun -CiMode:$CiMode -OutDir:$controlOutDir -VersionOverride:$VersionOverride
if ($LASTEXITCODE -ne 0) {
  Fail "build_control_center.ps1 failed with exit code $LASTEXITCODE"
}

Write-Host "build_all completed successfully"
