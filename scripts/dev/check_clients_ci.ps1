$ErrorActionPreference = 'Stop'

$root = Resolve-Path "$PSScriptRoot/../.."
$python = "python"

$steps = @(
    @{ Name = "Preflight layout validation"; Command = "$python scripts/ci/validate_python_client_layout.py" },
    @{ Name = "Upgrade pip"; Command = "$python -m pip install --upgrade pip" },
    @{ Name = "Install client dependencies"; Command = "$python -m pip install -r ./clients/python/requirements.txt" },
    @{ Name = "Install aris3 client sdk"; Command = "$python -m pip install -e ./clients/python/aris3_client_sdk" },
    @{ Name = "Install core app"; Command = "$python -m pip install -e ./clients/python/aris_core_3_app" },
    @{ Name = "Install control center app"; Command = "$python -m pip install -e ./clients/python/aris_control_center_app" },
    @{ Name = "Run targeted client tests"; Command = "$python -m pytest clients/python/tests -q" }
)

$passed = 0
$failed = 0

Push-Location $root
try {
    foreach ($step in $steps) {
        Write-Host "==> $($step.Name)"
        Invoke-Expression $step.Command
        if ($LASTEXITCODE -ne 0) {
            $failed++
            Write-Host "[FAIL] $($step.Name)"
            exit $LASTEXITCODE
        }

        $passed++
        Write-Host "[PASS] $($step.Name)"
    }
}
finally {
    Pop-Location
}

Write-Host ""
Write-Host "Client CI local check summary: PASS=$passed FAIL=$failed"
exit 0
