param([switch]$DryRun)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
$versionFile = Join-Path $root "version.json"
$versionPayload = Get-Content $versionFile -Raw | ConvertFrom-Json
$version = if ($env:PACKAGING_APP_VERSION) { $env:PACKAGING_APP_VERSION } elseif ($env:ARIS_APP_VERSION) { $env:ARIS_APP_VERSION } else { $versionPayload.version }
$env:ARIS_APP_VERSION = $version
$distDir = Join-Path $root "dist/control_center"
New-Item -ItemType Directory -Path $distDir -Force | Out-Null
$summary = @{
  app = "control_center"
  version = $version
  date = (Get-Date).ToString("yyyyMMdd")
  checks = @{}
}
$summary.checks.entrypoint = Test-Path "../aris_control_center_app/src/aris_control_center_app/app.py"
$summary.checks.env_example = Test-Path "../.env.example"
$summary.checks.spec = Test-Path "control_center.spec.template"
if (-not ($summary.checks.entrypoint -and $summary.checks.env_example -and $summary.checks.spec)) { throw "preflight failed" }
$cmd = "pyinstaller --clean --noconfirm --distpath `"$distDir`" control_center.spec.template"
if ($DryRun) { Write-Host $cmd } else { Invoke-Expression $cmd }
$summaryPath = Join-Path $root "dist/control_center/build_summary.json"
$summary | ConvertTo-Json -Depth 4 | Set-Content $summaryPath
Write-Host "summary: $summaryPath"
