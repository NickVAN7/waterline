"""CSV export of a list (build plan, "API conventions": CSV export; S3-C14): one file per list,
its cells formula-escaped, UTF-8 with a BOM so a spreadsheet reads accented names."""

import csv
import io
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from fastapi import Response
from pydantic import BaseModel, Field, create_model

from app.core.lists import ListSpec

# Defends against formula injection: a cell a spreadsheet would run as a formula (S3-plan's risk
# table: `=`, `+`, `-`, `@`, tab, CR). Out of scope: what a cell says, and spreadsheets that
# evaluate a quoted cell anyway.
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
TRUNCATED_HEADER = "Waterline-Truncated"


def cell(value: str) -> str:
    """The value as a cell a spreadsheet shows as text: a leading `'` before a formula prefix."""
    return f"'{value}" if value.startswith(FORMULA_PREFIXES) else value


@dataclass(frozen=True)
class CsvExport:
    """A list's export: the file name, the chosen columns' headers, the rows' values (in the
    same order), and whether the list's cap cut it short."""

    filename: str
    header: Sequence[str]
    rows: Sequence[Sequence[str]]
    truncated: bool


def selected[C: StrEnum](columns: Sequence[C] | None, every: Sequence[C]) -> list[C]:
    """The `columns=` asked for, in the order asked, or every column in its declared order."""
    return list(columns) if columns else list(every)


def export_query(spec: ListSpec, columns: type[StrEnum]) -> type[BaseModel]:
    """The export's query model: the list's own parameters plus `columns=` (repeat it; each at
    most once is not enforced, a repeat is just a repeated column)."""
    return create_model(
        f"{spec.name}ExportQuery",
        __base__=spec.query_model,
        columns=(list[columns] | None, Field(None, max_length=len(columns))),  # pyright: ignore[reportInvalidTypeForm]
    )


def csv_response(export: CsvExport) -> Response:
    """The export as a download: `text/csv`, every value cell escaped, `Content-Disposition` with
    its file name, and `Waterline-Truncated: true` when the cap cut it short."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(export.header)
    writer.writerows([cell(value) for value in row] for row in export.rows)
    headers = {"Content-Disposition": f'attachment; filename="{export.filename}"'}
    if export.truncated:
        headers[TRUNCATED_HEADER] = "true"
    return Response("﻿" + buffer.getvalue(), media_type="text/csv; charset=utf-8", headers=headers)
