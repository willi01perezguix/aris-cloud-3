# Sprint 6 Day 1 Notes

## Implemented
- Added reports and exports SDK clients with report/export models and polling helper.
- Added six report/export smoke CLI commands.
- Added ARIS CORE 3 Reports screen with filter presets, KPI summary, and export trigger/history.
- Added Control Center Effective Permissions Inspector (read-only grouped matrix).
- Added tests for report/export model serialization/parsing, client integrations, error mapping, and UI smoke coverage.

## Known limitations
- Profit summary endpoint is represented via overview totals because backend does not expose a dedicated route yet.
- Export generation currently uses synchronous backend behavior; polling helper remains for forward compatibility.
- Reports table preview in CORE is intentionally compact (first rows only) for Day 1 scope.

## Day 2 prep recommendations
- Expand CORE reports table into sortable grid with daily/calendar visual toggle controls.
- Add richer export history view (refresh button + download action + reason codes).
- Add optional user-picker API integration for Control Center inspector when user list endpoint is available.
