param()
$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path "$PSScriptRoot\..\..")

if (Test-Path ".\.venv\Scripts\Activate.ps1") { . .\.venv\Scripts\Activate.ps1 }

$candidates = @(
  ".\aris_control_2\app\main.py",
  ".\aris_control_2\main.py",
  ".\app\main.py",
  ".\main.py"
)

$entry = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $entry) {
  $found = Get-ChildItem -Recurse -File -Filter main.py |
    Where-Object { $_.FullName -notmatch "\\.venv\\|\\tests\\|\\artifacts\\|\\dist\\|\\build\\" } |
    Select-Object -First 1
  if ($found) { $entry = $found.FullName }
}

if (-not $entry) {
  throw "No se encontró entrypoint main.py en el proyecto."
}

Write-Host "Usando entrypoint: $entry"
python "$entry"
