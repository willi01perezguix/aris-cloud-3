from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Any


def export_current_view(module: str, rows: list[dict[str, Any]], headers: list[str], output_dir: str = "ARIS_CONTROL_2/out/exports") -> Path:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{module}_{timestamp}.csv"
    path = destination / filename

    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    return path
