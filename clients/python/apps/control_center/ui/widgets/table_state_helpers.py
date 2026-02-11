from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TableState:
    sort_key: str = "username"
    descending: bool = False
    page: int = 1
    page_size: int = 25
    filters: dict[str, str] | None = None

    def stable_sort(self, rows: list[dict]) -> list[dict]:
        enumerated = list(enumerate(rows))
        ordered = sorted(
            enumerated,
            key=lambda pair: (pair[1].get(self.sort_key), pair[0]),
            reverse=self.descending,
        )
        return [row for _, row in ordered]

    def apply_filters(self, rows: list[dict]) -> list[dict]:
        if not self.filters:
            return rows
        filtered = rows
        for key, value in self.filters.items():
            probe = value.lower()
            filtered = [row for row in filtered if probe in str(row.get(key, "")).lower()]
        return filtered

    def paginate(self, rows: list[dict]) -> dict[str, object]:
        total = len(rows)
        start = max(self.page - 1, 0) * self.page_size
        end = start + self.page_size
        return {
            "rows": rows[start:end],
            "page": self.page,
            "page_size": self.page_size,
            "total": total,
            "total_pages": (total + self.page_size - 1) // self.page_size,
        }


def selected_row_summary(row: dict | None) -> dict[str, str | None]:
    if not row:
        return {"id": None, "summary": "No row selected"}
    return {
        "id": str(row.get("id")),
        "summary": f"{row.get('username', 'unknown')} ({row.get('email', 'n/a')}) role={row.get('role', 'n/a')}",
    }
