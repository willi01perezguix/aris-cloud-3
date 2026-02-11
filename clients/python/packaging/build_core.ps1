param(
  [switch]$DryRun,
  [switch]$CiMode,
  [string]$OutDir,
  [string]$VersionOverride
)

$ErrorActionPreference = "Stop"

function Fail([string]$Message) {
  Write-Error $Message
  exit 1
}

function Resolve-NormalizedPath {
  param(
    [Parameter(Mandatory)]
    [string]$Path,
    [string]$Base = $PSScriptRoot
  )

  if ([System.IO.Path]::IsPathRooted($Path)) {
    return [System.IO.Path]::GetFullPath($Path)
  }

  return [System.IO.Path]::GetFullPath((Join-Path $Base $Path))
}

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $root "../..")
Set-Location $root

$versionFile = Join-Path $root "version.json"
$versionPayload = Get-Content $versionFile -Raw | ConvertFrom-Json
$version = if ($VersionOverride) { $VersionOverride } elseif ($env:PACKAGING_APP_VERSION) { $env:PACKAGING_APP_VERSION } elseif ($env:ARIS_APP_VERSION) { $env:ARIS_APP_VERSION } else { $versionPayload.version }
$env:ARIS_APP_VERSION = $version

$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) { Fail "Preflight failed: python executable not found in PATH." }

$entrypoint = Resolve-Path (Join-Path $root "../aris_core_3_app/src/aris_core_3_app/app.py") -ErrorAction SilentlyContinue
if (-not $entrypoint) { Fail "Preflight failed: expected entrypoint missing at clients/python/aris_core_3_app/src/aris_core_3_app/app.py." }

$specTemplate = Join-Path $root "core_app.spec.template"
if (-not (Test-Path $specTemplate -PathType Leaf)) { Fail "Preflight failed: spec template missing at clients/python/packaging/core_app.spec.template." }

$targetOutDir = if ($OutDir) { $OutDir } elseif ($CiMode) { "temp/artifacts/core" } else { "dist/core" }
$resolvedOutDir = Resolve-NormalizedPath -Path $targetOutDir -Base $root
New-Item -ItemType Directory -Path $resolvedOutDir -Force | Out-Null

try {
  $probeFile = Join-Path $resolvedOutDir ".write_test"
  "ok" | Set-Content -Path $probeFile -Encoding utf8
  Remove-Item $probeFile -Force
} catch {
  Fail "Preflight failed: output directory is not writable: $resolvedOutDir"
}

$gitSha = (git -C $repoRoot rev-parse --short HEAD 2>$null)
if (-not $gitSha) { $gitSha = "unknown" }

$pythonVersion = & python --version 2>&1
$buildTimeUtc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
$metadata = [ordered]@{
  app_name = "aris-core-3-app"
  version = $version
  git_sha = $gitSha.Trim()
  build_time_utc = $buildTimeUtc
  python_version = "$pythonVersion".Trim()
  os = "windows"
  dry_run = [bool]$DryRun
}

$metadataPath = Join-Path $resolvedOutDir "core_packaging_metadata.json"
$metadata | ConvertTo-Json -Depth 3 | Set-Content -Path $metadataPath -Encoding utf8

$renderedSpecPath = Join-Path $resolvedOutDir "core_app.rendered.spec"
$specContent = Get-Content -Path $specTemplate -Raw
$specContent | Set-Content -Path $renderedSpecPath -Encoding utf8

if (-not (Test-Path $renderedSpecPath -PathType Leaf)) {
  Fail "Preflight failed: rendered spec could not be written to $renderedSpecPath"
}

$distPath = Join-Path $resolvedOutDir "dist"
if ($DryRun) {
  Write-Host "[DRY-RUN] core packaging summary"
  Write-Host "  app_name=$($metadata.app_name)"
  Write-Host "  version=$($metadata.version)"
  Write-Host "  git_sha=$($metadata.git_sha)"
  Write-Host "  output_dir=$resolvedOutDir"
  Write-Host "  rendered_spec=$renderedSpecPath"
  Write-Host "  metadata=$metadataPath"
  Write-Host "  ci_mode=$([bool]$CiMode)"
  Write-Host "  installer_skipped=true"
  exit 0
}

$pyinstallerCmd = "pyinstaller --clean --noconfirm --distpath `"$distPath`" `"$renderedSpecPath`""
Write-Host "Running: $pyinstallerCmd"
Invoke-Expression $pyinstallerCmd
Write-Host "Build complete. metadata=$metadataPath"

# scaffold test guardrail: build_summary.json
$summaryOutDir = if ($resolvedOutDir -and $resolvedOutDir -ne "") { $resolvedOutDir } else { (Get-Location).Path }
$buildSummaryPath = Join-Path $summaryOutDir "build_summary.json"
$buildSummary = [ordered]@{
  app_name = "aris-core-3-app"
  version  = $version
  dry_run  = [bool]$DryRun
  ci_mode  = [bool]$CiMode
}
$buildSummary | ConvertTo-Json -Depth 4 | Set-Content -Path $buildSummaryPath -Encoding utf8
Write-Host "build_summary.json => $buildSummaryPath"
