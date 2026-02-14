from __future__ import annotations

import argparse
import json
import os
import zipfile
from pathlib import Path

from release_tools import redact_text, timestamp_slug

SENSITIVE_ENV_MARKERS = ("TOKEN", "SECRET", "PASSWORD", "AUTH", "KEY")


def _collect_env_profile() -> tuple[dict[str, str], int]:
    included = {}
    redactions = 0
    for key, value in os.environ.items():
        if not key.startswith("ARIS3_"):
            continue
        if any(marker in key.upper() for marker in SENSITIVE_ENV_MARKERS):
            included[key] = "<REDACTED>"
            redactions += 1
            continue
        masked, count = redact_text(f"{key}={value}")
        redactions += count
        included[key] = masked.split("=", 1)[1]
    return included, redactions


def _read_text_file(path: Path) -> tuple[str, int]:
    if not path.exists():
        return "", 0
    text = path.read_text(encoding="utf-8", errors="ignore")
    return redact_text(text)


def create_bundle(output_dir: Path) -> Path:
    stamp = timestamp_slug()
    output_dir.mkdir(parents=True, exist_ok=True)
    bundle = output_dir / f"support_bundle_{stamp}.zip"
    env_profile, env_redactions = _collect_env_profile()

    qa_files = sorted(Path("artifacts/qa").glob("client_qa_matrix_*.json"))
    packaging_files = sorted(Path("artifacts/packaging").glob("build_manifest_*.json"))
    logs = sorted(Path("artifacts").glob("**/*.log"))[-5:]

    redaction_total = env_redactions
    metadata = {
        "bundle_version": 1,
        "generated_at": stamp,
        "redaction_applied": True,
        "redactions": 0,
        "included": {
            "qa": [str(path) for path in qa_files[-1:]],
            "packaging": [str(path) for path in packaging_files[-1:]],
            "logs": [str(path) for path in logs],
        },
    }

    with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("env_profile.json", json.dumps(env_profile, indent=2, sort_keys=True))
        for path in qa_files[-1:] + packaging_files[-1:] + logs:
            text, count = _read_text_file(path)
            redaction_total += count
            zf.writestr(path.name, text)
        metadata["redactions"] = redaction_total
        zf.writestr("metadata.json", json.dumps(metadata, indent=2, sort_keys=True))

    return bundle


def main() -> int:
    parser = argparse.ArgumentParser(description="Create sanitized support bundle")
    parser.add_argument("--output-dir", default=os.getenv("ARIS3_SUPPORT_BUNDLE_DIR", "artifacts/support"))
    args = parser.parse_args()
    path = create_bundle(Path(args.output_dir))
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
