$ErrorActionPreference = 'Stop'

param(
    [switch]$StrictGate
)

$argsList = @('--artifact-dir', 'artifacts/post-ga/day5')
if ($StrictGate.IsPresent) { $argsList += '--strict-gate' }

python scripts/ops/post_ga_day5_certify.py @argsList
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
