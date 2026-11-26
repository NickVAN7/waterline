"""CSV export's cells and file (build plan, S3-C14; S3-plan's risk table: formula injection)."""

from enum import StrEnum

import pytest

from app.core import labels
from app.core.csv import TRUNCATED_HEADER, CsvExport, cell, csv_response, selected
from app.enums import Priority, RequirementStatus, Severity, TaskStatus, TaskType


@pytest.mark.security
@pytest.mark.parametrize(
    "value",
    ["=SUM(A1:A2)", "+1+1", "-2+3", "@SUM(A1)", "\t=1", "\r=1"],
)
def test_a_cell_starting_like_a_formula_is_quoted(value: str) -> None:
    """Every prefix a spreadsheet runs as a formula. Bug: one prefix missing from the list."""
    assert cell(value) == f"'{value}"


@pytest.mark.parametrize("value", ["Sign-in throttling", "a=b", "", "2026-11-25", " =1"])
def test_any_other_cell_is_left_as_it_is(value: str) -> None:
    """Only a leading prefix: a dash or `=` inside the text, or after a space, is text already."""
    assert cell(value) == value


def test_the_file_has_a_bom_crlf_rows_quoting_and_escaped_cells() -> None:
    response = csv_response(
        CsvExport(
            filename="PMT-tasks-2026-11-25.csv",
            header=["ID", "Title"],
            rows=[["PMT-TA-1", "=cmd"], ["PMT-TA-2", 'Say "hi", then go']],
            truncated=False,
        )
    )

    assert bytes(response.body).decode() == (
        '﻿ID,Title\r\nPMT-TA-1,\'=cmd\r\nPMT-TA-2,"Say ""hi"", then go"\r\n'
    )
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert response.headers["content-disposition"] == (
        'attachment; filename="PMT-tasks-2026-11-25.csv"'
    )
    assert TRUNCATED_HEADER.lower() not in response.headers


def test_a_capped_export_says_so_in_a_header() -> None:
    response = csv_response(CsvExport(filename="x.csv", header=[], rows=[], truncated=True))

    assert response.headers[TRUNCATED_HEADER] == "true"


class _Column(StrEnum):
    A = "a"
    B = "b"
    C = "c"


def test_columns_come_in_the_order_asked_or_all_in_declared_order() -> None:
    assert selected([_Column.C, _Column.A], list(_Column)) == [_Column.C, _Column.A]
    assert selected(None, list(_Column)) == [_Column.A, _Column.B, _Column.C]
    assert selected([], list(_Column)) == [_Column.A, _Column.B, _Column.C]


@pytest.mark.parametrize(
    ("enum", "label_map"),
    [
        (Priority, labels.PRIORITY),
        (RequirementStatus, labels.REQUIREMENT_STATUS),
        (TaskStatus, labels.TASK_STATUS),
        (TaskType, labels.TASK_TYPE),
        (Severity, labels.SEVERITY),
    ],
)
def test_every_value_has_a_label(enum: type[StrEnum], label_map: dict[StrEnum, str]) -> None:
    """A new enum member without a label would break every export holding it (KeyError)."""
    assert set(label_map) == set(enum)
