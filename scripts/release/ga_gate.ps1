$ErrorActionPreference = 'Stop'

$ArtifactDir = "artifacts/ga"
$SummaryFile = Join-Path $ArtifactDir "summary.txt"
$CommandLog = Join-Path $ArtifactDir "commands.log"

New-Item -ItemType Directory -Path $ArtifactDir -Force | Out-Null
Set-Content -Path $SummaryFile -Value ""
Set-Content -Path $CommandLog -Value ""

function Invoke-GaCheck {
    param(
        [string]$Name,
        [string]$Command
    )

    Write-Host "[RUN] $Name"
    Add-Content -Path $SummaryFile -Value "[RUN] $Name"
    Add-Content -Path $CommandLog -Value "$ $Command"

    Invoke-Expression $Command 2>&1 | Tee-Object -FilePath $CommandLog -Append
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[FAIL] $Name"
        Add-Content -Path $SummaryFile -Value "[FAIL] $Name"
        Add-Content -Path $SummaryFile -Value "GA RESULT: NO-GO"
        exit $LASTEXITCODE
    }

    Write-Host "[PASS] $Name"
    Add-Content -Path $SummaryFile -Value "[PASS] $Name"
}

Invoke-GaCheck -Name "Packaging scaffold (repo path)" -Command "python -m pytest clients/python/tests/test_packaging_scaffold.py -q"
Invoke-GaCheck -Name "Packaging scaffold (clients/python cwd)" -Command "Push-Location clients/python; python -m pytest tests/test_packaging_scaffold.py -q; Pop-Location"
Invoke-GaCheck -Name "Timezone boundary report" -Command "python -m pytest tests/test_reports_day3_daily_timezone.py::test_reports_daily_timezone_boundary_and_week_span -q -vv"
Invoke-GaCheck -Name "Go-live smoke POS checkout and reports" -Command "python -m pytest tests/smoke/test_go_live_validation.py::test_go_live_pos_checkout_and_reports_exports -q -vv"
Invoke-GaCheck -Name "Packaging scripts contract" -Command "python -m pytest tests/packaging/test_packaging_scripts_contract.py -q"
Invoke-GaCheck -Name "Full suite gate" -Command "python -m pytest tests -q -x --maxfail=1"

Add-Content -Path $SummaryFile -Value "GA RESULT: GO"
Write-Host "GA RESULT: GO"
Write-Host "Artifacts: $ArtifactDir"
exit 0
