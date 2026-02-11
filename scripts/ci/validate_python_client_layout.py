#!/usr/bin/env python3
"""CI guardrails for Python client project layout and install patterns."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REQUIRED_SUBPROJECTS = (
    "clients/python/aris3_client_sdk",
    "clients/python/aris_core_3_app",
    "clients/python/aris_control_center_app",
)
REQUIRED_PYPROJECTS = tuple(f"{path}/pyproject.toml" for path in REQUIRED_SUBPROJECTS)
REQUIREMENTS_FILES = (
    "clients/python/requirements.txt",
    "requirements.txt",
)
WORKFLOW_GLOB = ".github/workflows/*.yml"

BLOCKED_WORKFLOW_PATTERNS = {
    "clients/python[dev]": re.compile(r"clients/python\[dev\]"),
    "aris3_client_sdk[dev]": re.compile(r"aris3_client_sdk\[dev\]"),
}

ALLOWED_CLIENT_EDITABLES = {
    "-e ./aris3_client_sdk",
    "-e ./aris_core_3_app",
    "-e ./aris_control_center_app",
}


def _read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def validate_layout(repo_root: Path) -> list[str]:
    errors: list[str] = []

    for rel in REQUIRED_SUBPROJECTS:
        target = repo_root / rel
        if not target.is_dir():
            errors.append(
                f"Missing required client subproject directory: {rel}. "
                "Restore it or update the CI install matrix."
            )

    for rel in REQUIRED_PYPROJECTS:
        target = repo_root / rel
        if not target.is_file():
            errors.append(
                f"Missing required pyproject.toml: {rel}. "
                "Every client subproject must be installable as a package."
            )

    return errors


def validate_requirements(repo_root: Path) -> list[str]:
    errors: list[str] = []

    for rel in REQUIREMENTS_FILES:
        req_path = repo_root / rel
        if not req_path.is_file():
            continue

        for line_no, raw_line in enumerate(_read_lines(req_path), start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            if "-e" not in line and "--editable" not in line:
                continue

            normalized = line.replace("--editable", "-e").strip()

            if "[dev]" in normalized:
                errors.append(
                    f"{rel}:{line_no} uses editable extras ('{line}'). "
                    "Use canonical editable installs without extras."
                )
                continue

            if rel == "clients/python/requirements.txt" and normalized not in ALLOWED_CLIENT_EDITABLES:
                errors.append(
                    f"{rel}:{line_no} has unsupported editable target '{line}'. "
                    "Allowed entries are: ./aris3_client_sdk, ./aris_core_3_app, ./aris_control_center_app."
                )

    return errors


def validate_workflows(repo_root: Path) -> list[str]:
    errors: list[str] = []

    for workflow_path in sorted(repo_root.glob(WORKFLOW_GLOB)):
        for line_no, line in enumerate(_read_lines(workflow_path), start=1):
            for label, pattern in BLOCKED_WORKFLOW_PATTERNS.items():
                if pattern.search(line):
                    errors.append(
                        f"{workflow_path.relative_to(repo_root)}:{line_no} contains blocked pattern '{label}'. "
                        "Use canonical installs: pip install -e ./clients/python/<subproject>."
                    )

    return errors


def run_validation(repo_root: Path) -> list[str]:
    return [
        *validate_layout(repo_root),
        *validate_requirements(repo_root),
        *validate_workflows(repo_root),
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        default=None,
        help="Optional repository root override (defaults to script-relative root).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve() if args.repo_root else Path(__file__).resolve().parents[2]
    errors = run_validation(repo_root)

    if errors:
        print("Python client CI layout validation failed:\n", file=sys.stderr)
        for item in errors:
            print(f"- {item}", file=sys.stderr)
        return 1

    print("Python client CI layout validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
