from __future__ import annotations

import csv
import hashlib
import io
import os
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Iterable

try:  # pragma: no cover - optional dependency
    from openpyxl import Workbook
except ModuleNotFoundError:  # pragma: no cover
    Workbook = None

try:  # pragma: no cover - optional dependency
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
except ModuleNotFoundError:  # pragma: no cover
    canvas = None
    letter = (612, 792)

from app.aris3.core.error_catalog import AppError, ErrorCatalog
from app.aris3.schemas.exports import ExportFilters, ExportFormat, ExportSourceType
from app.aris3.services.reports import (
    daily_sales_refunds,
    iter_dates,
    resolve_date_range,
    resolve_timezone,
    validate_date_range,
)


@dataclass
class ExportDataset:
    columns: list[str]
    rows: list[list[object]]
    totals: dict[str, object] | None


class ExportStorage:
    def __init__(self, base_path: str) -> None:
        self.base_path = base_path
        os.makedirs(self.base_path, exist_ok=True)

    def build_path(self, export_id: str, format: ExportFormat) -> str:
        filename = f"{export_id}.{format}"
        return os.path.join(self.base_path, filename)

    def write_bytes(self, path: str, data: bytes) -> None:
        tmp_path = f"{path}.tmp"
        with open(tmp_path, "wb") as handle:
            handle.write(data)
        os.replace(tmp_path, path)


def sanitize_filename(name: str | None, format: ExportFormat, *, fallback: str) -> str:
    if not name:
        return f"{fallback}.{format}"
    base = os.path.basename(name)
    base = re.sub(r"\.[^.]+$", "", base)
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("._-")
    if not cleaned:
        cleaned = fallback
    return f"{cleaned}.{format}"


def _totals_from_days(rows: list[dict]) -> dict[str, Decimal]:
    gross_sales = sum((row["gross_sales"] for row in rows), Decimal("0.00"))
    refunds_total = sum((row["refunds_total"] for row in rows), Decimal("0.00"))
    net_sales = sum((row["net_sales"] for row in rows), Decimal("0.00"))
    cogs_gross = sum((row["cogs_gross"] for row in rows), Decimal("0.00"))
    cogs_reversed = sum((row["cogs_reversed_from_returns"] for row in rows), Decimal("0.00"))
    net_cogs = sum((row["net_cogs"] for row in rows), Decimal("0.00"))
    net_profit = sum((row["net_profit"] for row in rows), Decimal("0.00"))
    orders_paid_count = sum((row["orders_paid_count"] for row in rows), 0)
    average_ticket = net_sales / Decimal(orders_paid_count) if orders_paid_count else Decimal("0.00")
    return {
        "gross_sales": gross_sales,
        "refunds_total": refunds_total,
        "net_sales": net_sales,
        "cogs_gross": cogs_gross,
        "cogs_reversed_from_returns": cogs_reversed,
        "net_cogs": net_cogs,
        "net_profit": net_profit,
        "orders_paid_count": orders_paid_count,
        "average_ticket": average_ticket.quantize(Decimal("0.01")),
    }


def _build_daily_rows(
    sales_by_date: dict[date, Decimal],
    orders_by_date: dict[date, int],
    refunds_by_date: dict[date, Decimal],
    *,
    start_date: date,
    end_date: date,
) -> list[dict]:
    rows: list[dict] = []
    for day in iter_dates(start_date, end_date):
        gross_sales = sales_by_date.get(day, Decimal("0.00"))
        refunds_total = refunds_by_date.get(day, Decimal("0.00"))
        net_sales = gross_sales - refunds_total
        orders_paid_count = orders_by_date.get(day, 0)
        average_ticket = net_sales / Decimal(orders_paid_count) if orders_paid_count else Decimal("0.00")
        rows.append(
            {
                "business_date": day,
                "gross_sales": gross_sales,
                "refunds_total": refunds_total,
                "net_sales": net_sales,
                "cogs_gross": Decimal("0.00"),
                "cogs_reversed_from_returns": Decimal("0.00"),
                "net_cogs": Decimal("0.00"),
                "net_profit": net_sales,
                "orders_paid_count": orders_paid_count,
                "average_ticket": average_ticket.quantize(Decimal("0.01")),
            }
        )
    return rows


def build_report_dataset(
    *,
    db,
    tenant_id: str,
    store_id: str,
    source_type: ExportSourceType,
    filters: ExportFilters,
    max_days: int,
) -> ExportDataset:
    tz = resolve_timezone(filters.timezone)
    date_range = resolve_date_range(filters.from_value, filters.to_value, tz)
    validate_date_range(date_range, max_days=max_days)
    sales_by_date, orders_by_date, refunds_by_date = daily_sales_refunds(
        db,
        tenant_id=tenant_id,
        store_id=store_id,
        start_utc=date_range.start_utc,
        end_utc=date_range.end_utc,
        tz=tz,
        cashier_id=filters.cashier,
        payment_method=filters.payment_method,
    )
    daily_rows = _build_daily_rows(
        sales_by_date,
        orders_by_date,
        refunds_by_date,
        start_date=date_range.start_date,
        end_date=date_range.end_date,
    )

    if source_type == "reports_overview":
        totals = _totals_from_days(daily_rows)
        columns = list(totals.keys())
        rows = [[totals[col] for col in columns]]
        return ExportDataset(columns=columns, rows=rows, totals=totals)

    if source_type == "reports_daily":
        columns = [
            "business_date",
            "gross_sales",
            "refunds_total",
            "net_sales",
            "cogs_gross",
            "cogs_reversed_from_returns",
            "net_cogs",
            "net_profit",
            "orders_paid_count",
            "average_ticket",
        ]
        rows = [[row[col] for col in columns] for row in daily_rows]
        return ExportDataset(columns=columns, rows=rows, totals=_totals_from_days(daily_rows))

    if source_type == "reports_calendar":
        columns = ["business_date", "net_sales", "net_profit", "orders_paid_count"]
        rows = [
            [row["business_date"], row["net_sales"], row["net_profit"], row["orders_paid_count"]]
            for row in daily_rows
        ]
        return ExportDataset(columns=columns, rows=rows, totals=_totals_from_days(daily_rows))

    raise AppError(ErrorCatalog.VALIDATION_ERROR, details={"message": "invalid source_type"})


def _format_cell(value: object) -> object:
    if isinstance(value, Decimal):
        return value.quantize(Decimal("0.01"))
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def render_csv(dataset: ExportDataset) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(dataset.columns)
    for row in dataset.rows:
        writer.writerow([_format_cell(value) for value in row])
    return buffer.getvalue().encode("utf-8")


def render_xlsx(dataset: ExportDataset) -> bytes:
    if Workbook is None:
        return _render_xlsx_fallback(dataset)
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "report"
    worksheet.append(dataset.columns)
    for row in dataset.rows:
        worksheet.append([_format_cell(value) for value in row])
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


def _draw_lines(pdf: canvas.Canvas, lines: Iterable[str], *, start_y: int, line_height: int) -> int:
    y = start_y
    for line in lines:
        if y < 72:
            pdf.showPage()
            pdf.setFont("Helvetica", 10)
            y = start_y
        pdf.drawString(72, y, line)
        y -= line_height
    return y


def render_pdf(dataset: ExportDataset, *, title: str, filters: dict, generated_at: datetime) -> bytes:
    if canvas is None:
        return _render_pdf_fallback(dataset, title=title, filters=filters, generated_at=generated_at)
    output = io.BytesIO()
    pdf = canvas.Canvas(output, pagesize=letter)
    pdf.setFont("Helvetica", 12)
    pdf.drawString(72, 750, title)
    pdf.setFont("Helvetica", 10)
    lines = [f"Generated at: {generated_at.isoformat()}", "Filters:"]
    for key, value in filters.items():
        lines.append(f"- {key}: {value}")
    if dataset.totals:
        lines.append("Totals:")
        for key, value in dataset.totals.items():
            lines.append(f"- {key}: {_format_cell(value)}")
    y = _draw_lines(pdf, lines, start_y=730, line_height=14)
    y -= 10
    header_line = " | ".join(dataset.columns)
    y = _draw_lines(pdf, [header_line], start_y=y, line_height=14)
    row_lines = [" | ".join(str(_format_cell(value)) for value in row) for row in dataset.rows]
    _draw_lines(pdf, row_lines, start_y=y, line_height=14)
    pdf.showPage()
    pdf.save()
    return output.getvalue()


def checksum_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _column_letter(index: int) -> str:
    letters = ""
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def _render_xlsx_fallback(dataset: ExportDataset) -> bytes:
    import zipfile
    import xml.etree.ElementTree as ET

    def _cell_value(value: object) -> tuple[str, str | None]:
        formatted = _format_cell(value)
        if isinstance(formatted, (int, float, Decimal)):
            return str(formatted), None
        return str(formatted), "inlineStr"

    def _build_sheet_xml() -> bytes:
        worksheet = ET.Element(
            "worksheet",
            {"xmlns": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"},
        )
        sheet_data = ET.SubElement(worksheet, "sheetData")
        for row_index, row in enumerate([dataset.columns, *dataset.rows], start=1):
            row_element = ET.SubElement(sheet_data, "row", {"r": str(row_index)})
            for col_index, value in enumerate(row, start=1):
                cell_ref = f"{_column_letter(col_index)}{row_index}"
                cell_value, cell_type = _cell_value(value)
                attrs = {"r": cell_ref}
                if cell_type:
                    attrs["t"] = cell_type
                cell = ET.SubElement(row_element, "c", attrs)
                if cell_type == "inlineStr":
                    inline = ET.SubElement(cell, "is")
                    ET.SubElement(inline, "t").text = cell_value
                else:
                    ET.SubElement(cell, "v").text = cell_value
        return ET.tostring(worksheet, encoding="utf-8", xml_declaration=True)

    content_types = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>
"""
    rels = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>
"""
    workbook_xml = """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="report" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>
"""
    workbook_rels = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>
"""
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr("[Content_Types].xml", content_types)
        zip_file.writestr("_rels/.rels", rels)
        zip_file.writestr("xl/workbook.xml", workbook_xml)
        zip_file.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        zip_file.writestr("xl/worksheets/sheet1.xml", _build_sheet_xml())
    return output.getvalue()


def _render_pdf_fallback(dataset: ExportDataset, *, title: str, filters: dict, generated_at: datetime) -> bytes:
    lines = [title, f"Generated at: {generated_at.isoformat()}", "Filters:"]
    for key, value in filters.items():
        lines.append(f"{key}: {value}")
    if dataset.totals:
        lines.append("Totals:")
        for key, value in dataset.totals.items():
            lines.append(f"{key}: {_format_cell(value)}")
    lines.append("Rows:")
    lines.append(" | ".join(dataset.columns))
    for row in dataset.rows:
        lines.append(" | ".join(str(_format_cell(value)) for value in row))

    text = "\\n".join(lines).replace("(", "\\(").replace(")", "\\)")
    content_stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET"
    objects = []
    objects.append("1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj")
    objects.append("2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj")
    objects.append(
        "3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        "/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj"
    )
    objects.append(f"4 0 obj << /Length {len(content_stream)} >> stream\n{content_stream}\nendstream endobj")
    objects.append("5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj")
    xref_offset = 9
    body = "%PDF-1.4\n" + "\n".join(objects) + "\n"
    xref_positions = []
    current = len("%PDF-1.4\n")
    for obj in objects:
        xref_positions.append(current)
        current += len(obj) + 1
    xref = "xref\n0 6\n0000000000 65535 f \n"
    for pos in xref_positions:
        xref += f"{pos:010d} 00000 n \n"
    trailer = "trailer << /Size 6 /Root 1 0 R >>\nstartxref\n"
    trailer += f"{len(body)}\n%%EOF"
    return (body + xref + trailer).encode("utf-8")
