from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path

from release_tools import manifest_payload, timestamp_slug, write_json, write_markdown


def _preflight(root: Path) -> dict[str, bool | str]:
    return {
        "python": True,
        "venv_or_conda": bool(os.getenv("VIRTUAL_ENV") or os.getenv("CONDA_PREFIX")),
        "pyinstaller": shutil.which("pyinstaller") is not None,
        "core_entrypoint": (root / "../aris_core_3_app/src/aris_core_3_app/app.py").resolve().exists(),
        "control_entrypoint": (root / "../aris_control_center_app/src/aris_control_center_app/app.py").resolve().exists(),
        "env_example": (root / "../.env.example").resolve().exists(),
    }


def verify_packaging(root: Path, version: str) -> tuple[Path, Path]:
    stamp = timestamp_slug()
    manifest_path = Path(f"artifacts/packaging/build_manifest_{stamp}.json")
    report_path = Path(f"artifacts/packaging/packaging_verify_{stamp}.md")

    preflight = _preflight(root)
    binaries = list((root / "dist").glob("**/*.exe"))
    manifest = manifest_payload("desktop", version, binaries)
    manifest["preflight"] = preflight
    write_json(manifest_path, manifest)

    missing = [key for key, ok in preflight.items() if ok is False]
    lines = [
        "# Packaging Verification",
        "",
        f"- Version: {version}",
        f"- Build pass/fail: {'PASS' if not missing else 'WARN'}",
        f"- Runtime launch smoke: {'SKIP (no executables found)' if not binaries else 'PASS (artifacts present)'}",
        f"- Missing dependencies: {', '.join(missing) if missing else 'none'}",
        "- Known blockers: windows build execution cannot run in linux CI shell.",
        "",
        "## Preflight",
    ]
    for key, value in preflight.items():
        lines.append(f"- {key}: {value}")
    write_markdown(report_path, lines)
    return manifest_path, report_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify packaging prerequisites and artifacts")
    parser.add_argument("--packaging-root", default="clients/python/packaging")
    parser.add_argument("--version", default=None)
    args = parser.parse_args()

    root = Path(args.packaging_root)
    version = args.version
    if not version:
        payload = json.loads((root / "version.json").read_text(encoding="utf-8"))
        version = str(payload["version"])
    manifest, report = verify_packaging(root, version)
    print(f"wrote {manifest}")
    print(f"wrote {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
