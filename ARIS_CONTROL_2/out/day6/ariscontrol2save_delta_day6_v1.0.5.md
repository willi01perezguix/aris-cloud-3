# ariscontrol2save — delta-only Day 6 (v1.0.5)

## Δ QA/regresión
- `pytest -q` (repo raíz): PASS.
- `pytest -q tests/smoke/test_post_merge_readiness.py -ra`: PASS (5/5).
- `python scripts/release_readiness_gate.py --pytest-target tests/smoke/test_post_merge_readiness.py`: PASS_WITH_WARNINGS (`tests:postgres` en WARN por falta de URL).
- `PYTHONPATH=. pytest -q tests/unit tests/integration -ra` (ARIS_CONTROL_2): 125 PASS + 1 FAIL no crítico (`test_day1_kickoff_quickwins`).
- Set dirigido de cobertura obligatoria Day 6 (22 tests): PASS.

## Δ Entregables Day 6 v1.0.5
1. `ARIS_CONTROL_2/out/day6/DAY6_QA_REGRESSION_REPORT_v1.0.5.md`
2. `ARIS_CONTROL_2/out/day6/REGRESSION_MATRIX_v1.0.5.md`
3. `ARIS_CONTROL_2/out/day6/PACKAGING_RC_V1_0_5.md`
4. `ARIS_CONTROL_2/out/day6/ROLLBACK_DRILL_v1.0.5.md`
5. `ARIS_CONTROL_2/out/day6/RELEASE_NOTES_DRAFT_v1.0.5.md`
6. `ARIS_CONTROL_2/out/day6/GO_NO_GO_MEMO_DAY7_v1.0.5.md`

## Δ RC + rollback
- RC `.exe`: bloqueado en este entorno por ausencia de `pwsh`; SHA256 pendiente en runner Windows.
- Rollback drill v1.0.5->v1.0.4: validado, ETA 14 min (<15 min).

## Δ Contrato API
- Sin cambios de endpoints, payloads o reglas backend.
