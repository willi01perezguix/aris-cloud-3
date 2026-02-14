# ARIS_CONTROL_2 — Matriz de Pruebas Mínimas v1.0.1

## Estado
- **Estado operativo:** `PENDIENTE EJECUCIÓN` (bloqueado por gate inicial NO-GO).

| ID | Tipo | Precondición | Pasos | Resultado esperado | Evidencia |
|---|---|---|---|---|---|
| TST-01 | Regresión login/sesión | API disponible, credenciales válidas | Iniciar sesión, expirar sesión, reingresar | Sin crash, control correcto de sesión | Log + captura flujo |
| TST-02 | Tenant context | Tenant y stores de prueba cargados | Seleccionar tenant, listar stores/users | Datos coherentes por tenant | Export de resultado |
| TST-03 | Flujo Tenants | Usuario con permisos admin | CRUD básico tenant (sin alterar contrato) | Operaciones válidas y trazables | Registro UI/API |
| TST-04 | Flujo Stores | Tenant activo | CRUD básico store | Persistencia correcta | Log operativo |
| TST-05 | Flujo Users | Store activa | Alta/edición usuario y consulta | Sin fuga de contexto | Evidencia QA |
| TST-06 | Manejo de errores | Simular timeout/5xx | Ejecutar acción crítica y observar UI | Error controlado, no crash | Captura + log |
| TST-07 | Conectividad endpoint default | Config por defecto intacta | Arrancar app y verificar base URL | Usa `https://aris-cloud-3-api-pecul.ondigitalocean.app/` | Salida de config/log |
| TST-08 | Empaquetado y arranque `.exe` | Runner Windows preparado | Ejecutar smoke oficial de empaquetado/arranque | `.exe` inicia y conecta | Log build + checksum |
