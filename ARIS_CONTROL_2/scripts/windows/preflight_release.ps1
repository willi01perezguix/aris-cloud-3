param(
  [string]$ExpectedBranch = ""
)
$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path "$PSScriptRoot\..\..")

function Assert-Condition {
  param(
    [bool]$Condition,
    [string]$Message
  )
  if (-not $Condition) { throw $Message }
  Write-Host "[OK] $Message"
}

$currentBranch = (git branch --show-current).Trim()
Assert-Condition (-not [string]::IsNullOrWhiteSpace($currentBranch)) "Rama actual detectada: $currentBranch"
if ($ExpectedBranch) {
  Assert-Condition ($currentBranch -eq $ExpectedBranch) "Rama actual coincide con ExpectedBranch ($ExpectedBranch)"
}

$gitStatus = (git status --porcelain)
Assert-Condition ([string]::IsNullOrWhiteSpace(($gitStatus | Out-String))) "Working tree limpio"

Assert-Condition (Test-Path ".\.env.example") "Existe .env.example"

$ignoredEnv = (git check-ignore .env 2>$null)
Assert-Condition (-not [string]::IsNullOrWhiteSpace($ignoredEnv)) ".env está ignorado por git"

$candidates = @(
  ".\aris_control_2\app\main.py",
  ".\aris_control_2\main.py",
  ".\app\main.py",
  ".\main.py"
)
$entry = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
Assert-Condition (-not [string]::IsNullOrWhiteSpace($entry)) "Existe entrypoint"

Assert-Condition (Test-Path ".\tests") "Tests ejecutables (carpeta tests existe)"
Assert-Condition (Test-Path ".\scripts\windows\run_control_center_dev.ps1") "Existe run_control_center_dev.ps1"
Assert-Condition (Test-Path ".\scripts\windows\build_control_center.ps1") "Existe build_control_center.ps1"

if (-not (Test-Path ".\out\exports")) {
  New-Item -ItemType Directory -Path ".\out\exports" | Out-Null
  Write-Host "[OK] Carpeta out/exports creada"
} else {
  Write-Host "[OK] Carpeta out/exports existe"
}

Write-Host "Preflight release completado."
