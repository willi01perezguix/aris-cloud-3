from __future__ import annotations

from typing import Any


def print_table(title: str, rows: list[dict[str, Any]], columns: list[tuple[str, str]]) -> None:
    print(f"\n{title}")
    if not rows:
        print("(sin resultados)")
        return

    widths = []
    for key, header in columns:
        max_cell = max(len(_display(row.get(key))) for row in rows)
        widths.append(max(len(header), max_cell))

    header_line = " | ".join(header.ljust(widths[idx]) for idx, (_, header) in enumerate(columns))
    separator = "-+-".join("-" * width for width in widths)
    print(header_line)
    print(separator)

    for row in rows:
        line = " | ".join(_display(row.get(key)).ljust(widths[idx]) for idx, (key, _) in enumerate(columns))
        print(line)


def _display(value: Any) -> str:
    if value is None:
        return ""
    return str(value)
