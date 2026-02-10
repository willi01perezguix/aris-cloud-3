param([switch]$DryRun)
if (-not $env:ARIS_APP_VERSION) { $env:ARIS_APP_VERSION = '0.6.2' }
$cmd = 'pyinstaller --clean --noconfirm control_center.spec.template'
if ($DryRun) { Write-Host $cmd; exit 0 }
Invoke-Expression $cmd
