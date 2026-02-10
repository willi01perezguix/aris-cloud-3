from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

REDACT_RE = re.compile(r"(?i)(token|secret|password|api[_-]?key|authorization)\s*[:=]\s*([^\s,;]+)")


def timestamp_slug() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def redact_text(value: str) -> tuple[str, int]:
    count = 0

    def _repl(match: re.Match[str]) -> str:
        nonlocal count
        count += 1
        return f"{match.group(1)}=<REDACTED>"

    return REDACT_RE.sub(_repl, value), count


@dataclass
class ManifestEntry:
    path: str
    size: int
    sha256: str


def hash_file(path: Path) -> ManifestEntry:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return ManifestEntry(path=str(path), size=path.stat().st_size, sha256=digest.hexdigest())


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_markdown(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def manifest_payload(app: str, version: str, build_files: list[Path]) -> dict:
    entries = [asdict(hash_file(path)) for path in build_files if path.exists()]
    return {
        "app": app,
        "version": version,
        "timestamp": timestamp_slug(),
        "files": entries,
    }
