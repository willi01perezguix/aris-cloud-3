$ErrorActionPreference = 'Stop'

param(
    [ValidateSet('L1', 'L2', 'L3')]
    [string]$Profile = 'L1',
    [switch]$StrictGate,
    [int]$Iterations,
    [int]$Concurrency,
    [int]$Warmup,
    [double]$TimeoutSeconds = 0,
    [string]$BaseUrl = 'http://127.0.0.1:8000'
)

$argsList = @('--artifact-dir', 'artifacts/post-ga/day3', '--profile', $Profile, '--base-url', $BaseUrl)
if ($StrictGate.IsPresent) { $argsList += '--strict-gate' }
if ($Iterations -gt 0) { $argsList += @('--iterations', $Iterations) }
if ($Concurrency -gt 0) { $argsList += @('--concurrency', $Concurrency) }
if ($Warmup -ge 0) { $argsList += @('--warmup', $Warmup) }
if ($TimeoutSeconds -gt 0) { $argsList += @('--timeout-seconds', $TimeoutSeconds) }

python scripts/ops/load_probe.py @argsList
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
