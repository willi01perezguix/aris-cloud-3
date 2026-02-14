# Memo GO/NO-GO — preparación Day 7 (v1.0.5)

## Decisión recomendada
**NO-GO condicionado** a completar evidencia de empaquetado Windows `.exe`.

## Fundamentación
### Gate técnico
- Backend/smoke crítico: en verde.
- Regresión funcional obligatoria: en verde con set dirigido.
- Unitaria/integración de cliente: 1 falla no crítica, documentada.

### Bloqueadores de salida
1. No se pudo generar `ARIS_CONTROL_2.exe` con script oficial por falta de `pwsh` en entorno actual.
2. No se pudo registrar metadatos obligatorios del binario (`nombre/tamaño/timestamp/SHA256`) al no existir artefacto generado.

## Recomendación formal
- **NO-GO hoy** para promoción final Day 7.
- Cambiar a **GO** inmediatamente tras:
  1) build oficial Windows exitoso,
  2) smoke de arranque en limpio,
  3) hash SHA256 registrado y adjunto a expediente de release.

## Condiciones de aceptación restantes
- [ ] RC `.exe` generado con script oficial.
- [ ] Arranque validado en entorno limpio.
- [ ] SHA256 + metadatos completados.
- [x] Sin cambios de contrato API.
- [x] Rollback drill documentado y validado.
