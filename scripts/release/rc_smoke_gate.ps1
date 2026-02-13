$ErrorActionPreference = 'Stop'

$ArtifactDir = "artifacts/rc"
$SummaryFile = Join-Path $ArtifactDir "summary.txt"
$CommandLog = Join-Path $ArtifactDir "commands.log"
$RunFullSuite = $false

if ($args.Count -gt 0 -and $args[0] -eq "--full-suite") {
    $RunFullSuite = $true
}

New-Item -ItemType Directory -Path $ArtifactDir -Force | Out-Null
Set-Content -Path $SummaryFile -Value ""
Set-Content -Path $CommandLog -Value ""

function Invoke-RcCheck {
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
        Add-Content -Path $SummaryFile -Value "RC RESULT: NO-GO"
        exit $LASTEXITCODE
    }

    Write-Host "[PASS] $Name"
    Add-Content -Path $SummaryFile -Value "[PASS] $Name"
}

Invoke-RcCheck -Name "Packaging scaffold (repo path)" -Command "python -m pytest clients/python/tests/test_packaging_scaffold.py -q"
Invoke-RcCheck -Name "Timezone boundary report" -Command "python -m pytest tests/test_reports_day3_daily_timezone.py::test_reports_daily_timezone_boundary_and_week_span -q -vv"
Invoke-RcCheck -Name "Go-live smoke POS checkout and reports" -Command "python -m pytest tests/smoke/test_go_live_validation.py::test_go_live_pos_checkout_and_reports_exports -q -vv"
Invoke-RcCheck -Name "Packaging scripts contract" -Command "python -m pytest tests/packaging/test_packaging_scripts_contract.py -q"

if ($RunFullSuite) {
    Invoke-RcCheck -Name "Full suite gate" -Command "python -m pytest tests -q -x --maxfail=1"
}

Add-Content -Path $SummaryFile -Value "RC RESULT: GO"
Write-Host "RC RESULT: GO"
Write-Host "Artifacts: $ArtifactDir"
exit 0
