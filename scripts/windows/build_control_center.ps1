param()
$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path "$PSScriptRoot\..\..")

if (Test-Path ".\.venv\Scripts\Activate.ps1") { . .\.venv\Scripts\Activate.ps1 }

python -m pip install --upgrade pip
python -m pip install pyinstaller

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
  throw "No se encontró entrypoint para empaquetar."
}

Write-Host "Empaquetando entrypoint: $entry"
pyinstaller --noconfirm --onefile --name ARIS_CONTROL_2 "$entry"
Write-Host "Build listo. Revisa .\dist\ARIS_CONTROL_2.exe"
