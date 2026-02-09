from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.main import create_app


DEFAULT_OUTPUT_DIR = Path("artifacts/release_candidate")


def main() -> int:
    parser = argparse.ArgumentParser(description="Export OpenAPI spec for ARIS3")
    parser.add_argument("--output", help="Output JSON path")
    args = parser.parse_args()

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = Path(args.output) if args.output else DEFAULT_OUTPUT_DIR / "openapi.json"

    app = create_app()
    spec = app.openapi()
    output_path.write_text(json.dumps(spec, indent=2))
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
