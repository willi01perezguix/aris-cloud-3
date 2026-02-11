#!/usr/bin/env python3
"""Validate Windows packaging scaffold inputs for Python clients."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REQUIRED_PACKAGING_FILES = (
    "core_app.spec.template",
    "control_center.spec.template",
    "build_core.bat",
    "build_core.ps1",
    "build_control_center.bat",
    "build_control_center.ps1",
    "build_all.ps1",
    "installer_placeholder.ps1",
    "version.json",
    "README.md",
)

REQUIRED_CLIENT_PYPROJECTS = (
    "clients/python/aris3_client_sdk/pyproject.toml",
    "clients/python/aris_core_3_app/pyproject.toml",
    "clients/python/aris_control_center_app/pyproject.toml",
)


def validate_packaging_scaffold(repo_root: Path) -> list[str]:
    errors: list[str] = []
    packaging_root = repo_root / "clients/python/packaging"

    if not packaging_root.is_dir():
        errors.append(
            "Missing packaging directory: clients/python/packaging. "
            "Restore packaging scaffold before running Windows packaging jobs."
        )
        return errors

    for file_name in REQUIRED_PACKAGING_FILES:
        target = packaging_root / file_name
        if not target.is_file():
            errors.append(
                f"Missing packaging scaffold file: clients/python/packaging/{file_name}. "
                "Restore this file or update scaffold expectations intentionally."
            )

    for rel_path in REQUIRED_CLIENT_PYPROJECTS:
        target = repo_root / rel_path
        if not target.is_file():
            errors.append(
                f"Missing required client pyproject: {rel_path}. "
                "Each app/sdk must remain installable in CI packaging smoke jobs."
            )

    return errors


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
    errors = validate_packaging_scaffold(repo_root)

    if errors:
        print("Packaging scaffold validation failed:\n", file=sys.stderr)
        for err in errors:
            print(f"- {err}", file=sys.stderr)
        return 1

    print("Packaging scaffold validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
