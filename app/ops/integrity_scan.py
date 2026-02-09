from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import asdict

from app.aris3.core.config import settings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.ops.integrity_checks import IntegrityFinding, resolve_tenants, run_integrity_checks


def _serialize_findings(findings: list[IntegrityFinding]) -> list[dict]:
    return [asdict(finding) for finding in findings]


def _summarize(findings: list[IntegrityFinding]) -> dict:
    counts = Counter(f.severity for f in findings)
    return {
        "total": len(findings),
        "critical": counts.get("CRITICAL", 0),
        "warn": counts.get("WARN", 0),
    }


def _format_text(summary: dict, findings: list[IntegrityFinding]) -> str:
    lines = [
        "Integrity Scan Report",
        f"Total findings: {summary['total']}",
        f"CRITICAL: {summary['critical']}",
        f"WARN: {summary['warn']}",
        "",
    ]
    for finding in findings:
        lines.append(
            f"[{finding.severity}] {finding.check_id} tenant={finding.tenant_id} "
            f"entity={finding.entity} id={finding.entity_id or '-'} {finding.message}"
        )
        if finding.details:
            lines.append(f"  details={json.dumps(finding.details, default=str)}")
    return "\n".join(lines)


def run_scan(tenant: str, output_format: str, fail_on_critical: bool, *, database_url: str | None = None) -> int:
    if not settings.OPS_ENABLE_INTEGRITY_SCAN:
        print("Integrity scan disabled by OPS_ENABLE_INTEGRITY_SCAN.", file=sys.stderr)
        return 2
    engine = create_engine(database_url or settings.DATABASE_URL, future=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    with SessionLocal() as db:
        tenant_ids = resolve_tenants(db, tenant)
        findings: list[IntegrityFinding] = []
        for tenant_id in tenant_ids:
            findings.extend(run_integrity_checks(db, tenant_id))
    summary = _summarize(findings)
    output = {
        "summary": summary,
        "findings": _serialize_findings(findings),
    }
    if output_format == "json":
        print(json.dumps(output, indent=2, default=str))
    else:
        print(_format_text(summary, findings))
    if fail_on_critical and summary["critical"] > 0:
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ARIS3 integrity scan")
    parser.add_argument("--tenant", required=True, help="Tenant ID or 'all'")
    parser.add_argument("--format", choices=["json", "text"], default="text")
    parser.add_argument("--fail-on-critical", action="store_true")
    args = parser.parse_args(argv)
    return run_scan(args.tenant, args.format, args.fail_on_critical)


if __name__ == "__main__":
    raise SystemExit(main())
