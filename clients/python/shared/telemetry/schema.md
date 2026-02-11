# ARIS Shared Telemetry Schema (Sprint 8 Day 1)

## Purpose
This schema defines a **minimal, non-PII telemetry envelope** shared by ARIS-CORE-3 and Control Center clients for beta-readiness hardening.

## Event categories
- `auth`
- `navigation`
- `api_call_result`
- `error`
- `permission_denied`

## Event payload
| Field | Type | Required | Notes |
|---|---|---:|---|
| `category` | string | yes | Must be one of the five categories above. |
| `name` | string | yes | Stable event name, e.g., `login_success`. |
| `module` | string | yes | Client module origin (`core_app`, `control_center`, etc.). |
| `action` | string | yes | Action semantic (`submit_login`, `open_screen`, etc.). |
| `timestamp_utc` | ISO-8601 string | yes | UTC timestamp at event creation time. |
| `trace_id` | string | no | Correlation id from request/middleware when available. |
| `duration_ms` | integer | no | Duration for measured operations. |
| `success` | boolean | no | `true` / `false` outcome where relevant. |
| `error_code` | string | no | Stable error identifier (non-sensitive). |
| `context` | object | no | Must stay non-PII. |
| `app_name` | string | yes (sink-level) | Added by logger sink for source identification. |

## Non-PII constraints
Forbidden telemetry keys include (case-insensitive):
- `email`
- `password`
- `phone`
- `full_name`
- `address`
- `token`
- `authorization`
- `bank_name`
- `voucher_number`
- `card_number`

## Sinks
- Local JSONL file sink (default): `artifacts/telemetry/<app_name>.jsonl`
- Optional stdout sink (for CI/debug stream visibility)

## Toggle model
Telemetry is disabled by default and is enabled per environment with:

```bash
ARIS3_TELEMETRY_ENABLED=1
```

Any value outside `1/true/yes/on` keeps telemetry off.
