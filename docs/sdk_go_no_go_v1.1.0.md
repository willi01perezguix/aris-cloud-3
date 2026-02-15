# SDK GO/NO-GO v1.1.0

## Estado
**GO**

## Criterios evaluados (checklist)
- [x] Config estricta sin fallback runtime (`ARIS3_API_BASE_URL` obligatoria).
- [x] Polling de exports con lectura fresca por-request (sin dependencia de cache global stale).
- [x] Suite `clients/python/tests` en verde.
- [x] Release gate técnico de Day 6 en verde.
- [x] Empaquetado SDK generado (`sdist` + `wheel`) en `dist/`.
- [x] Metadatos de paquete validados (nombre, versión, dependencias, `python_requires`).
- [x] Consistencia de versión documentada y changelog actualizado.

## Riesgos residuales
1. Los workflows de CI remotos dependen del estado del runner/entorno GitHub Actions al abrir PR.
2. La adopción de config estricta puede afectar integraciones legacy que no definan `ARIS3_API_BASE_URL`.

## Plan de mitigación / rollback
- Ejecutar los workflows de SDK/release al abrir PR y bloquear merge ante fallas.
- Rollback funcional: volver a la última versión aprobada del SDK en consumers críticos.
- Rollback de release: revertir commit de release y regenerar artefactos desde tag previo.

## Comando/tag recomendado para release estable
```bash
git tag -a v1.1.0 -m "ARIS3 Python SDK v1.1.0 stable"
git push origin v1.1.0
```
