$ErrorActionPreference = 'Stop'

param(
    [switch]$Apply,
    [switch]$StrictGate,
    [int]$PostGaDays = 30,
    [int]$DiagDays = 14,
    [int]$TempDays = 7
)

$argsList = @('--artifact-dir', 'artifacts/post-ga/day4', '--post-ga-days', $PostGaDays, '--diag-days', $DiagDays, '--temp-days', $TempDays)
if ($Apply.IsPresent) { $argsList += '--apply' }
if ($StrictGate.IsPresent) { $argsList += '--strict-gate' }

python scripts/ops/post_ga_day4_retention_audit.py @argsList
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
