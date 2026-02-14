param(
  [string]$BaseUrl = "https://aris-cloud-3-api-pecul.ondigitalocean.app/",
  [string]$Role = "SUPERADMIN"
)

$ErrorActionPreference = "Stop"

Write-Host "=== ARIS_CONTROL_2 Day 6 Guided E2E Smoke ==="
Write-Host "Base URL objetivo: $BaseUrl"
Write-Host "Rol esperado: $Role"
Write-Host ""
Write-Host "Checklist ordenado:"
Write-Host "[1] Abrir app (run_control_center_dev.ps1 o exe RC)"
Write-Host "[2] Login SUPERADMIN"
Write-Host "[3] Seleccionar tenant y operar stores/users"
Write-Host "[4] Validar bloqueo de acción sin permisos (RBAC)"
Write-Host "[5] Validar trazabilidad de errores (code/message/trace_id)"
Write-Host "[6] Abrir panel diagnóstico y verificar base_url/conectividad/version/timestamp"
Write-Host "[7] Exportar incidencia y confirmar sanitización (sin tokens/passwords/secrets)"
Write-Host ""
Write-Host "Evidencia sugerida:"
Write-Host "- Captura por cada paso"
Write-Host "- Log textual por paso (PASS/FAIL + observaciones)"
Write-Host "- Ruta del reporte exportado"
Write-Host ""
Write-Host "NOTA: este script es checklist guiado/manual reproducible; no altera contrato API."
