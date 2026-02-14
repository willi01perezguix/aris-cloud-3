# 01 — Manual Operativo ARIS_CONTROL_2

## 1) Requisitos
- **OS:** Windows 10/11.
- **Shell:** PowerShell 5.1+ (o PowerShell 7+).
- **Python:** 3.11+ recomendado.
- **Git:** para validaciones de rama/estado.

## 2) Instalación paso a paso
1. Entrar a carpeta del módulo:
   ```powershell
   cd ARIS_CONTROL_2
   ```
2. Crear entorno virtual (opcional, recomendado):
   ```powershell
   py -3 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
3. Instalar dependencias del proyecto:
   ```powershell
   python -m pip install --upgrade pip
   pip install -e .[dev]
   ```

## 3) Configuración `.env` / `.env.example`
1. Copiar archivo de ejemplo:
   ```powershell
   Copy-Item .env.example .env
   ```
2. Validar variables:
   - `ARIS3_BASE_URL=https://aris-cloud-3-api-pecul.ondigitalocean.app/`
   - `ARIS3_TIMEOUT_SECONDS=30`
   - `ARIS3_VERIFY_SSL=true`
3. **No versionar `.env`** (está ignorado por `.gitignore`).

## 4) Ejecución modo dev
Desde `ARIS_CONTROL_2/`:
```powershell
.\scripts\windows\run_control_center_dev.ps1
```
El script detecta el entrypoint principal y ejecuta `python` con ese archivo.

## 5) Uso de módulos
- **Login:** autenticación con credenciales y persistencia local segura de sesión.
- **`/me`:** validación de identidad y contexto efectivo.
- **Admin Core:** gestión de tenants/stores/users.
- **Filtros y paginación:** navegación de listados admin con estado consistente.
- **Export CSV:** exportación de tablas hacia `out/exports`.

## 6) Interpretación de errores
Cuando exista error de API, usar:
- `code`: tipo funcional/técnico del error.
- `message`: mensaje principal legible.
- `details`: datos adicionales del backend.
- `trace_id`: correlación para soporte y auditoría.

## 7) Buenas prácticas operativas
- Confirmar tenant activo antes de mutaciones.
- Usar llaves de idempotencia en operaciones críticas.
- Exportar CSV tras validar filtros/paginación.
- Adjuntar `trace_id` en reportes de incidentes.

## 8) Solución de problemas frecuentes
- **ExecutionPolicy bloquea scripts:**
  ```powershell
  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
  ```
- **`.venv` faltante o corrupto:** recrear entorno virtual y reinstalar dependencias.
- **Rutas PowerShell:** ejecutar scripts desde `ARIS_CONTROL_2/`.
- **Advertencias CRLF en git:** normalizar fin de línea con configuración de equipo/repositorio.
- **Entrypoint no encontrado:** revisar `aris_control_2/app/main.py` y usar `run_control_center_dev.ps1`.

## 9) Comandos operativos rápidos
### PowerShell local (sin activar `.venv`)
```powershell
git status --short
git branch --show-current
.\scripts\windows\preflight_release.ps1
.\scripts\windows\smoke_release.ps1
Get-FileHash .\dist\ARIS_CONTROL_2.exe -Algorithm SHA256
```

### PowerShell con `.venv` activo
```powershell
pytest -q
.\scripts\windows\run_control_center_dev.ps1
.\scripts\windows\build_control_center.ps1
```
