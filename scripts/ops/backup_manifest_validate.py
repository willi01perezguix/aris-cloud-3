from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.ops.backup_utils import validate_manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate backup manifest for ARIS3")
    parser.add_argument("manifest", help="Path to manifest.json")
    args = parser.parse_args(argv)
    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        print("manifest not found", file=sys.stderr)
        return 1
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors = validate_manifest(manifest, manifest_path.parent)
    if errors:
        print(f"manifest invalid: {errors}", file=sys.stderr)
        return 1
    print("manifest valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
