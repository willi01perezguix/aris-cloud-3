# ARIS-CORE-3 App Shell (Sprint 7 Day 3)

## Purpose
This app-track deliverable establishes the ARIS-CORE-3 desktop shell foundation for:
- authentication bootstrap,
- `/aris3/me` profile loading,
- effective-permissions UI gating (default deny, deny-over-allow),
- navigation placeholders for upcoming module integrations.

No contract-breaking API changes are introduced.

## Run
From repository root:

```bash
export ARIS3_API_BASE_URL="https://api.example.com"
python clients/python/apps/core_app/main.py
```

## Environment configuration
Core inputs:
- `ARIS3_API_BASE_URL` (required, or `ARIS3_API_BASE_URL_<ENV>`)
- `ARIS3_ENV` (`dev`/`staging`/`prod`, default `dev`)
- `ARIS3_CONNECT_TIMEOUT_SECONDS` (optional)
- `ARIS3_READ_TIMEOUT_SECONDS` (optional)
- `ARIS3_APP_ID` (optional)
- `ARIS3_DEVICE_ID` (optional)

`.env` is supported via `python-dotenv`.

## Auth flow (text diagram)
1. App bootstrap starts.
2. Existing session token present?
   - No: route `login`.
   - Yes: load profile (`/aris3/me`).
3. After login success: establish session, load profile.
4. If profile has `must_change_password=true`: route `change_password`.
5. Load effective permissions.
6. Build permission gate and open shell.
7. Logout clears persisted session and routes back to login.

## Permission gating behavior
- Default deny when permission key is absent.
- Deny overrides allow if conflicting entries are present.
- Menu modules rendered only when any required key is allowed.

## Known limitations
- Module screens are placeholders only (status + context + required permission keys).
- No deep business workflows are included in Day 3.
