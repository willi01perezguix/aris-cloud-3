# Go / No-Go Checklist — Sprint 6 Day 7

Use this checklist at the release decision meeting. Mark each item with ✅/❌ and attach evidence links.

## 1) Technical readiness
- [ ] CI is green on required checks (`CI`, `Release Readiness`).
- [ ] Migrations are safe (`alembic heads` single head + `upgrade head` successful).
- [ ] Critical smokes pass:
  - `tests/smoke/test_post_merge_readiness.py`
  - `tests/smoke/test_go_live_validation.py`
- [ ] Rollback steps validated against runbooks:
  - `runbooks/10_RECOVERY_PLAYBOOK_ARIS3_v1.md`
  - `runbooks/11_GO_LIVE_PLAYBOOK_ARIS3_v1.md`

## 2) Security readiness
- [ ] Admin boundaries enforced (RBAC deny > allow, default deny confirmed through smoke/automation).
- [ ] Secrets/config are safe for release (no debug mode, no leaked credentials, expected env vars set).

## 3) Operational readiness
- [ ] On-call owner assigned for release window and hypercare.
- [ ] Hypercare watch schedule set (24–72h coverage).
- [ ] Alerting channels verified (PagerDuty/Slack/Teams/email bridge).

## 4) Business readiness
- [ ] Release notes prepared (`docs/releases/RELEASE_NOTES_S6D7.md`).
- [ ] Known limitations and deferred items documented and accepted.

---

## Final Decision Block
- **Decision:** `GO` / `NO-GO`
- **Timestamp (UTC):** ______________________
- **Decision owner:** ______________________
- **Rationale (evidence-based):**
  - ___________________________________________
  - ___________________________________________
  - ___________________________________________
