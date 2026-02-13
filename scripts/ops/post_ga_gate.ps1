$ErrorActionPreference = 'Stop'

param(
    [switch]$FullSuite
)

$ArtifactDir = "artifacts/post-ga/day1"
$SummaryFile = Join-Path $ArtifactDir "summary.txt"
$CommandLog = Join-Path $ArtifactDir "commands.log"
$MatrixFile = Join-Path $ArtifactDir "command_matrix.tsv"
$ResultsFile = Join-Path $ArtifactDir "results.tsv"
$MetadataFile = Join-Path $ArtifactDir "metadata.txt"

New-Item -ItemType Directory -Path $ArtifactDir -Force | Out-Null
Set-Content -Path $SummaryFile -Value ""
Set-Content -Path $CommandLog -Value ""
Set-Content -Path $MatrixFile -Value ""
Set-Content -Path $ResultsFile -Value ""

$Sha = (git rev-parse HEAD).Trim()
$TimestampUtc = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
$PythonVersion = (python --version 2>&1 | Out-String).Trim()

@(
    "sha=$Sha"
    "timestamp_utc=$TimestampUtc"
    "python_version=$PythonVersion"
    "run_full_suite=$($FullSuite.IsPresent)"
) | Set-Content -Path $MetadataFile

$PassCount = 0
$FailCount = 0

function Invoke-PostGaCheck {
    param(
        [string]$Name,
        [string]$Command
    )

    Add-Content -Path $MatrixFile -Value "$Name`t$Command"
    Add-Content -Path $SummaryFile -Value "[RUN] $Name"
    Add-Content -Path $CommandLog -Value "$ $Command"

    $output = Invoke-Expression $Command 2>&1
    if ($null -ne $output) {
        $output | Out-String | Add-Content -Path $CommandLog
    }

    if ($LASTEXITCODE -eq 0) {
        Add-Content -Path $SummaryFile -Value "[PASS] $Name"
        Add-Content -Path $ResultsFile -Value "$Name`tPASS"
        $script:PassCount += 1
        return
    }

    Add-Content -Path $SummaryFile -Value "[FAIL] $Name"
    Add-Content -Path $ResultsFile -Value "$Name`tFAIL"
    $script:FailCount += 1
}

Invoke-PostGaCheck -Name "Packaging scaffold (repo path)" -Command "python -m pytest clients/python/tests/test_packaging_scaffold.py -q"
Invoke-PostGaCheck -Name "Packaging scaffold (clients/python cwd)" -Command "Push-Location clients/python; python -m pytest tests/test_packaging_scaffold.py -q; Pop-Location"
Invoke-PostGaCheck -Name "Timezone boundary report" -Command "python -m pytest tests/test_reports_day3_daily_timezone.py::test_reports_daily_timezone_boundary_and_week_span -q -vv"
Invoke-PostGaCheck -Name "Go-live smoke POS checkout and reports" -Command "python -m pytest tests/smoke/test_go_live_validation.py::test_go_live_pos_checkout_and_reports_exports -q -vv"
Invoke-PostGaCheck -Name "Packaging scripts contract" -Command "python -m pytest tests/packaging/test_packaging_scripts_contract.py -q"

if ($FullSuite.IsPresent) {
    Invoke-PostGaCheck -Name "Full suite gate" -Command "python -m pytest tests -q -x --maxfail=1"
}

$result = if ($FailCount -gt 0) { 'NO-GO' } else { 'GO' }

@(
    "pass_count=$PassCount"
    "fail_count=$FailCount"
    "result=$result"
) | Add-Content -Path $MetadataFile

Add-Content -Path $SummaryFile -Value "POST-GA DAY1 RESULT: $result"
Add-Content -Path $SummaryFile -Value "Artifacts: $ArtifactDir"
Write-Host "POST-GA DAY1 RESULT: $result"
Write-Host "Artifacts: $ArtifactDir"

if ($FailCount -gt 0) {
    exit 1
}

exit 0
