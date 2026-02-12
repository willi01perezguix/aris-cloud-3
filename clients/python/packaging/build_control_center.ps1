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
if (-not (Test-Path $versionFile -PathType Leaf)) {
  Fail "Preflight failed: version file missing at clients/python/packaging/version.json."
}

$versionPayload = Get-Content $versionFile -Raw | ConvertFrom-Json
if (-not $versionPayload.version) {
  Fail "Preflight failed: version.json must contain a non-empty 'version' value."
}

$version = if ($VersionOverride) { $VersionOverride } elseif ($env:PACKAGING_APP_VERSION) { $env:PACKAGING_APP_VERSION } elseif ($env:ARIS_APP_VERSION) { $env:ARIS_APP_VERSION } else { $versionPayload.version }
$env:ARIS_APP_VERSION = $version

$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) { Fail "Preflight failed: python executable not found in PATH." }

$entrypoint = Resolve-Path (Join-Path $root "../aris_control_center_app/src/aris_control_center_app/app.py") -ErrorAction SilentlyContinue
if (-not $entrypoint) { Fail "Preflight failed: expected entrypoint missing at clients/python/aris_control_center_app/src/aris_control_center_app/app.py." }

$specTemplate = Join-Path $root "control_center.spec.template"
if (-not (Test-Path $specTemplate -PathType Leaf)) { Fail "Preflight failed: spec template missing at clients/python/packaging/control_center.spec.template." }

$targetOutDir = if ($OutDir) { $OutDir } elseif ($CiMode) { "temp/artifacts/control_center" } else { "dist/control_center" }
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
  app_name = "aris-control-center-app"
  version = $version
  git_sha = $gitSha.Trim()
  build_time_utc = $buildTimeUtc
  python_version = "$pythonVersion".Trim()
  os = "windows"
  dry_run = [bool]$DryRun
}

$metadataPath = Join-Path $resolvedOutDir "control_center_packaging_metadata.json"
$metadata | ConvertTo-Json -Depth 3 | Set-Content -Path $metadataPath -Encoding utf8
if (-not (Test-Path $metadataPath -PathType Leaf)) {
  Fail "Preflight failed: metadata file was not created: $metadataPath"
}

# scaffold test guardrail: venv runtime check
$venvActive = [bool]$env:VIRTUAL_ENV
if (-not $venvActive) {
  $msg = "venv is not active."
  if ($CiMode) { Write-Warning "$msg CI mode enabled; continuing." }
  else { throw "$msg Activate your venv before packaging." }
} else {
  Write-Host "venv active: $($env:VIRTUAL_ENV)"
}

# --- scaffold runtime markers (contract tests) ---
if (-not $version) { $version = "0.0.0-dev" }
$buildStamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddHHmmss")

$artifactPrefix = "aris-control-center-$version-$buildStamp"
$artifact_prefix = $artifactPrefix  # required by tests

$buildSummaryPath = Join-Path $resolvedOutDir "build_summary.json"
$summary = [ordered]@{
  app_name        = "aris-control-center-app"
  artifact_prefix = $artifactPrefix
  version         = $version
  dry_run         = [bool]$DryRun
  ci_mode         = [bool]$CiMode
  venv            = $venvActive
}
$summary | ConvertTo-Json -Depth 6 | Set-Content -Path $buildSummaryPath -Encoding utf8
if (-not (Test-Path $buildSummaryPath -PathType Leaf)) {
  Fail "Preflight failed: build summary file was not created: $buildSummaryPath"
}

Write-Host "artifact_prefix=$artifactPrefix"
Write-Host "build_summary=$buildSummaryPath"
# --- end scaffold runtime markers ---

$renderedSpecPath = Join-Path $resolvedOutDir "control_center.rendered.spec"
$specContent = Get-Content -Path $specTemplate -Raw
$specContent | Set-Content -Path $renderedSpecPath -Encoding utf8

if (-not (Test-Path $renderedSpecPath -PathType Leaf)) {
  Fail "Preflight failed: rendered spec could not be written to $renderedSpecPath"
}

$distPath = Join-Path $resolvedOutDir "dist"
if ($DryRun) {
  Write-Host "[DRY-RUN] control center packaging summary"
  Write-Host "  app_name=$($metadata.app_name)"
  Write-Host "  version=$($metadata.version)"
  Write-Host "  git_sha=$($metadata.git_sha)"
  Write-Host "  output_dir=$resolvedOutDir"
  Write-Host "  rendered_spec=$renderedSpecPath"
  Write-Host "  metadata=$metadataPath"
  Write-Host "  build_summary=$buildSummaryPath"
  Write-Host "  ci_mode=$([bool]$CiMode)"
  Write-Host "  installer_skipped=true"
  exit 0
}

$pyInstallerCmd = Get-Command pyinstaller -ErrorAction SilentlyContinue
if (-not $pyInstallerCmd) {
  Fail "Preflight failed: pyinstaller executable not found in PATH. Install pyinstaller before non-dry-run packaging."
}

Write-Host "Running: pyinstaller --clean --noconfirm --distpath '$distPath' '$renderedSpecPath'"
& pyinstaller --clean --noconfirm --distpath $distPath $renderedSpecPath

if (-not (Test-Path $distPath -PathType Container)) {
  Fail "Packaging failed: expected dist directory missing at $distPath"
}

$distItems = Get-ChildItem -Path $distPath -Recurse -File -ErrorAction SilentlyContinue
if (-not $distItems -or $distItems.Count -eq 0) {
  Fail "Packaging failed: dist directory is empty at $distPath"
}

Write-Host "Build complete. metadata=$metadataPath"
Write-Host "Build complete. build_summary=$buildSummaryPath"
