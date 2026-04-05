from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.main import create_app
from app.aris3.openapi_validation import assert_semantically_valid_openapi


DEFAULT_OUTPUT_DIR = Path("artifacts/release_candidate")
LEGACY_PRUNED_SPEC_PATH = Path("docs/openapi-pruned.json")


def main() -> int:
    parser = argparse.ArgumentParser(description="Export OpenAPI spec for ARIS3")
    parser.add_argument("--output", help="Output JSON path")
    args = parser.parse_args()

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = Path(args.output) if args.output else DEFAULT_OUTPUT_DIR / "openapi.json"

    app = create_app()
    spec = app.openapi()
    assert_semantically_valid_openapi(spec)
    output_path.write_text(json.dumps(spec, indent=2))
    if LEGACY_PRUNED_SPEC_PATH.exists():
        LEGACY_PRUNED_SPEC_PATH.unlink()
        print(f"removed stale non-canonical spec: {LEGACY_PRUNED_SPEC_PATH}")
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
