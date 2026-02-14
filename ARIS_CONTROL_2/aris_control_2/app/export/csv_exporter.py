from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Any

from aris_control_2.app.ui.listing_view import sanitize_row


def export_current_view(
    *,
    module: str,
    rows: list[dict[str, Any]],
    headers: list[str],
    output_dir: str = "ARIS_CONTROL_2/out/exports",
    tenant_id: str | None = None,
    filters: dict[str, str] | None = None,
) -> Path:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)

    now = datetime.now().astimezone()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    filename = f"{module}_{timestamp}.csv"
    path = destination / filename

    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        handle.write(f"# timestamp_local: {now.isoformat()}\n")
        handle.write(f"# module: {module}\n")
        handle.write(f"# tenant_id: {tenant_id or 'N/A'}\n")
        handle.write(f"# filters: {filters or {}}\n")
        writer = csv.DictWriter(handle, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(sanitize_row(row, headers=headers))

    return path
