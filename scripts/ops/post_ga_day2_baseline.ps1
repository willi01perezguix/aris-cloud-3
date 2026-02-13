$ErrorActionPreference = 'Stop'

param(
    [switch]$FullSuite
)

$argsList = @('--artifact-dir', 'artifacts/post-ga/day2')
if ($FullSuite.IsPresent) {
    $argsList += '--full-suite'
}

python scripts/ops/perf_snapshot.py @argsList
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
