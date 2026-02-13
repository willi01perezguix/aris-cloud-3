# Performance Budgets v1

## Baseline alignment
- Day-2 test runtime artifacts provide CI timing baseline.
- Day-3 load probe artifacts provide endpoint latency/error baseline.

## Day-4 budget metrics
- Test runtime envelope: day2 aggregated duration seconds.
- Day-3 p95 latency:
  - Pass: < 1200ms
  - Warn: >= 1200ms and < 1500ms
  - Fail: >= 1500ms
- Day-3 error-rate reference remains from Day-3 summary and is informational in Day-4 analyzer.

## Breach policy
- Warn: monitor + schedule optimization.
- Fail: NO-GO under strict gate and rollback-first workflow.

## No drift policy
No contract, schema, query, route, or business-rule changes are allowed as part of performance governance.
