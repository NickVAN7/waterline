"""The docs agree with the code and with each other (build-plan, "Verification").

Mechanical checks only; the `docs-consistency` agent reviews what needs judgment. Each test
reads files (and `Base.metadata`), never the database. Parsers are strict: a doc whose
structure changes fails with `DocsStructureError` instead of passing by finding nothing.
"""

import re
from collections.abc import Callable
from enum import StrEnum
from pathlib import Path

import pytest
from _pytest.mark import ParameterSet
from sqlalchemy import Column, MetaData, String, Table

import app.models  # noqa: F401  # pyright: ignore[reportUnusedImport] -- registers every model
from app.core.base_model import Base
from app.core.enums import enum_type
from tests.support import docs


def _report(problems: list[str]) -> str:
    return "\n" + "\n".join(problems)


def _reading(text: str) -> Callable[[str], str]:
    """A stand-in for `docs.read` that returns `text` for any path."""

    def fake_read(_path: str) -> str:
        return text

    return fake_read


# --- 1-3: models vs schema-doc ----------------------------------------------------------------


def test_every_model_table_is_documented_and_not_deferred() -> None:
    problems = docs.model_tables_missing_from_schema_doc(
        Base.metadata, docs.schema_doc_tables(), docs.deferred_tables()
    )

    assert problems == [], _report(problems)


def _column_params() -> list[ParameterSet]:
    """One parameter per model column, decided at collection: a column the schema doc marks
    `Added in Slice <n>.` for a slice that isn't finished is collected as skipped, so it shows in
    the report. A malformed schema doc fails collection of this module (a DocsStructureError)."""
    latest, order = docs.latest_checkpoint(), docs.checkpoint_order()
    params: list[ParameterSet] = []
    for check in docs.column_checks(Base.metadata, docs.schema_doc_tables()):
        verdict = docs.column_verdict(check, latest, order)
        marks = [pytest.mark.skip(reason=verdict.skip_reason)] if verdict.skip_reason else []
        params.append(pytest.param(verdict, id=str(check), marks=marks))
    return params


@pytest.mark.parametrize("verdict", _column_params())
def test_model_column_matches_schema_doc(verdict: docs.ColumnVerdict) -> None:
    assert verdict.problem is None, verdict.problem


def test_model_enum_values_match_schema_doc() -> None:
    problems = docs.enum_mismatches(Base.metadata, docs.schema_doc_tables())

    assert problems == [], _report(problems)


# The app has no models before Slice 1, so the three tests above compare nothing yet. These
# prove the comparisons report what they should, on a synthetic table.


class _Colour(StrEnum):
    RED = "red"
    BLUE = "blue"


def _synthetic_metadata() -> MetaData:
    metadata = MetaData()
    Table(
        "widget",
        metadata,
        Column("id", String, primary_key=True),
        Column("name", String),
        Column("colour", enum_type(_Colour, "colour")),
    )
    return metadata


def _documented(columns: set[str], colours: set[str]) -> dict[str, docs.DocTable]:
    return {"widget": docs.DocTable("widget", frozenset(columns), {"colour": frozenset(colours)})}


def test_missing_and_deferred_model_tables_are_reported() -> None:
    problems = docs.model_tables_missing_from_schema_doc(
        _synthetic_metadata(), {}, frozenset({"widget"})
    )

    assert problems == [
        "table `widget` is a model (Base.metadata) but has no ### `widget` section in "
        "docs/schema-doc.md",
        "table `widget` is a model (Base.metadata) but is listed under Deferred tables in "
        "docs/schema-doc.md",
    ]


def _slice(slice_number: int, *numbers: str) -> docs.CheckpointOrder:
    """A checkpoint order for one slice, from its table's # cells ("1", "2", "13a", ...). Built
    without `Checkpoint.parse`, so a broken parser fails the tests that use it, not collection."""
    return {
        slice_number: tuple(
            docs.Checkpoint(slice_number, int(n.rstrip("ab")), n.lstrip("0123456789"))
            for n in numbers
        )
    }


# Slice 3 has five checkpoints in these tests; slice 2 is long finished.
_SLICE_3_OF_5 = _slice(3, "1", "2", "3", "4", "5")
_MID_SLICE_2 = docs.Checkpoint(2, 4)


def _verdicts(
    documented: dict[str, docs.DocTable],
    latest: docs.Checkpoint = _MID_SLICE_2,
    order: docs.CheckpointOrder = _SLICE_3_OF_5,
) -> dict[str, docs.ColumnVerdict]:
    return {
        str(check): docs.column_verdict(check, latest, order)
        for check in docs.column_checks(_synthetic_metadata(), documented)
    }


def test_missing_and_extra_columns_are_reported_per_column() -> None:
    verdicts = _verdicts(_documented({"id", "colour", "size"}, {"red", "blue"}))

    assert verdicts == {
        "widget.colour": docs.ColumnVerdict(),
        "widget.id": docs.ColumnVerdict(),
        "widget.name": docs.ColumnVerdict(
            problem="`widget.name` is in the model but not in docs/schema-doc.md"
        ),
        "widget.size": docs.ColumnVerdict(
            problem="`widget.size` is in docs/schema-doc.md but not in the model"
        ),
    }


def _with_marked_size(added_in: int) -> dict[str, docs.DocTable]:
    columns = frozenset({"id", "name", "colour", "size"})
    table = docs.DocTable(
        "widget", columns, {"colour": frozenset({"red", "blue"})}, {"size": added_in}
    )
    return {"widget": table}


@pytest.mark.parametrize(
    ("latest", "order"),
    [
        (docs.Checkpoint(2, 4), _SLICE_3_OF_5),  # an earlier slice
        (docs.Checkpoint(3, 1), _SLICE_3_OF_5),  # the slice has started
        (docs.Checkpoint(3, 4), _SLICE_3_OF_5),  # one checkpoint before its last
        (docs.Checkpoint(3, 7), {}),  # no checkpoint table yet: not finished within the slice
    ],
)
def test_marked_column_is_skipped_until_its_slice_is_finished(
    latest: docs.Checkpoint, order: docs.CheckpointOrder
) -> None:
    verdicts = _verdicts(_with_marked_size(added_in=3), latest, order)

    assert verdicts["widget.size"] == docs.ColumnVerdict(
        skip_reason="added in Slice 3 (schema-doc)"
    )


@pytest.mark.parametrize(
    ("latest", "order"),
    [
        (docs.Checkpoint(3, 5), _SLICE_3_OF_5),  # the slice's last checkpoint is committed
        (docs.Checkpoint(4, 1), _SLICE_3_OF_5),  # a later slice has started
        (docs.Checkpoint(4, 1), {}),  # a later slice has started, no table for slice 3
    ],
)
def test_marked_column_is_required_once_its_slice_is_finished(
    latest: docs.Checkpoint, order: docs.CheckpointOrder
) -> None:
    verdicts = _verdicts(_with_marked_size(added_in=3), latest, order)

    assert verdicts["widget.size"] == docs.ColumnVerdict(
        problem="`widget.size` is in docs/schema-doc.md but not in the model (marked `Added in "
        "Slice 3.`, and that slice is finished)"
    )


def test_marked_column_in_the_model_passes_before_its_slice() -> None:
    metadata = _synthetic_metadata()
    metadata.tables["widget"].append_column(Column("size", String))

    checks = docs.column_checks(metadata, _with_marked_size(added_in=3))

    assert [docs.column_verdict(check, _MID_SLICE_2, _SLICE_3_OF_5) for check in checks] == [
        docs.ColumnVerdict()
    ] * 4


def test_undocumented_model_column_fails_even_in_a_table_with_markers() -> None:
    columns = frozenset({"id", "colour", "size"})
    documented = {"widget": docs.DocTable("widget", columns, {}, {"size": 3})}

    verdicts = _verdicts(documented)

    assert verdicts["widget.name"] == docs.ColumnVerdict(
        problem="`widget.name` is in the model but not in docs/schema-doc.md"
    )


@pytest.mark.parametrize(
    ("table", "slice_number", "skipped"),
    [
        ("requirement", 2, {"workstream_id": 3, "search_vector": 6}),
        ("task", 3, {"sprint_id": 4, "milestone_id": 4, "search_vector": 6}),
        ("testcase", 5, {"search_vector": 6}),
    ],
)
def test_schema_doc_marks_columns_from_later_slices(
    table: str, slice_number: int, skipped: dict[str, int]
) -> None:
    """The real schema doc, against a model built at the end of the table's own slice (every
    documented column except the marked ones): exactly the marked columns are skipped."""
    documented = docs.schema_doc_tables()
    metadata = MetaData()
    built = sorted(documented[table].columns - set(skipped))
    Table(table, metadata, *(Column(name, String) for name in built))
    end_of_slice = docs.Checkpoint(slice_number, 2)

    verdicts = {
        check.column: docs.column_verdict(check, end_of_slice, _slice(slice_number, "1", "2"))
        for check in docs.column_checks(metadata, documented)
    }

    assert verdicts == dict.fromkeys(built, docs.ColumnVerdict()) | {
        column: docs.ColumnVerdict(skip_reason=f"added in Slice {n} (schema-doc)")
        for column, n in skipped.items()
    }


@pytest.mark.parametrize(
    "notes",
    [
        "added in Slice 3. Same project",  # wrong case
        "Added in Slice 3 Same project",  # no period
        "Added in Slice three. Same project",  # not a number
        "Same project. Added in Slice 3.",  # not at the start
    ],
)
def test_malformed_added_in_marker_is_a_structure_error(
    monkeypatch: pytest.MonkeyPatch, notes: str
) -> None:
    def fake_read(_path: str) -> str:
        return (
            "### `widget`\n| Field | Type | Notes |\n|---|---|---|\n"
            f"| id | UUID (PK) | |\n| size | varchar | {notes} |\n"
        )

    monkeypatch.setattr(docs, "read", fake_read)

    with pytest.raises(docs.DocsStructureError, match=r"`widget`\.size: malformed marker"):
        docs.schema_doc_tables()


def test_well_formed_added_in_marker_is_parsed() -> None:
    assert docs.schema_doc_tables()["requirement"].added_in == {
        "workstream_id": 3,
        "search_vector": 6,
    }


def test_differing_enum_values_are_reported() -> None:
    problems = docs.enum_mismatches(
        _synthetic_metadata(), _documented({"id", "name", "colour"}, {"red", "green"})
    )

    assert problems == [
        "`widget`.colour: model values ['blue', 'red'] != docs/schema-doc.md values "
        "['green', 'red']"
    ]


def test_schema_doc_parses_combined_rows_and_enum_lists() -> None:
    tables = docs.schema_doc_tables()

    assert {"start_date", "end_date", "created_at", "updated_at"} <= tables["phase"].columns
    assert tables["task"].enums["severity"] == {"s1", "s2", "s3", "s4"}
    assert "status" in tables["activity_log"].enums["field_changed"]


# --- 4: feature map ownership -----------------------------------------------------------------


def test_every_documented_table_has_exactly_one_owner() -> None:
    problems = docs.ownership_problems(
        docs.feature_map_owners(), frozenset(docs.schema_doc_tables())
    )

    assert problems == [], _report(problems)


# --- 5-6: tech-debt log -----------------------------------------------------------------------


def test_tech_debt_entries_are_well_formed() -> None:
    problems = docs.tech_debt_format_problems(docs.tech_debt_entries())

    assert problems == [], _report(problems)


def test_every_tech_debt_reference_exists() -> None:
    known = frozenset(str(entry.number) for entry in docs.tech_debt_entries())

    problems = docs.unresolved_references(
        r"\bTD-(\d+)\b", known, f"has no entry in {docs.TECH_DEBT}"
    )

    assert problems == [], _report(problems)


def test_no_open_tech_debt_is_overdue() -> None:
    problems = docs.overdue_tech_debt(
        docs.tech_debt_entries(), docs.latest_checkpoint(), docs.checkpoint_order()
    )

    assert problems == [], _report(problems)


# --- Audit allowlist ---------------------------------------------------------------------------


def test_every_allowlisted_advisory_names_an_open_tech_debt_entry() -> None:
    problems = docs.allowlist_problems(docs.audit_allowlist_tech_debt(), docs.tech_debt_entries())

    assert problems == [], _report(problems)


def test_allowlist_entries_naming_missing_or_resolved_tech_debt_are_reported() -> None:
    entries = [
        docs.TechDebt(1, {"Status": "open"}),
        docs.TechDebt(2, {"Status": "resolved in S1-C3"}),
    ]

    problems = docs.allowlist_problems(
        {"GHSA-a": "TD-1", "GHSA-b": "TD-2", "GHSA-c": "TD-9"}, entries
    )

    assert problems == [
        "audit-allowlist.toml: GHSA-b names TD-2, which is resolved; fix the advisory's entry "
        "(remove it once the dependency is fixed)",
        "audit-allowlist.toml: GHSA-c names TD-9, which has no entry in docs/tech-debt.md",
    ]


def test_allowlist_entries_are_read_from_both_sections(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        docs,
        "read",
        _reading(
            '[[python]]\nid = "PYSEC-1"\nreason = "r"\ntech_debt = "TD-3"\n'
            '[[npm]]\nid = "GHSA-2"\nreason = "r"\ntech_debt = "TD-4"\n'
        ),
    )

    assert docs.audit_allowlist_tech_debt() == {"PYSEC-1": "TD-3", "GHSA-2": "TD-4"}


@pytest.mark.parametrize("text", ["[[npm]\n", '[[npm]]\nid = "GHSA-2"\n'])
def test_a_malformed_allowlist_is_a_structure_error(
    monkeypatch: pytest.MonkeyPatch, text: str
) -> None:
    monkeypatch.setattr(docs, "read", _reading(text))

    with pytest.raises(docs.DocsStructureError, match=r"audit-allowlist\.toml"):
        docs.audit_allowlist_tech_debt()


# --- Decision log ----------------------------------------------------------------------------


def test_decision_log_entries_are_well_formed() -> None:
    problems = docs.decision_log_format_problems(docs.decision_log_entries())

    assert problems == [], _report(problems)


def test_every_superseded_by_names_an_existing_entry() -> None:
    problems = docs.superseded_by_problems(docs.decision_log_entries())

    assert problems == [], _report(problems)


def test_every_decision_log_reference_exists() -> None:
    known = frozenset(str(entry.number) for entry in docs.decision_log_entries())

    problems = docs.unresolved_references(
        r"\bDL-(\d+)\b", known, f"has no entry in {docs.DECISION_LOG}"
    )

    assert problems == [], _report(problems)


_DL_FIELDS = {
    "Date": "2026-10-08",
    "Decision": "x",
    "Supersedes": "none",
    "Superseded by": "none",
    "Applies to": "x",
    "Source": "chat session",
}


@pytest.mark.parametrize("missing", list(_DL_FIELDS))
def test_decision_log_entry_missing_a_field_is_reported(missing: str) -> None:
    fields = {name: value for name, value in _DL_FIELDS.items() if name != missing}

    problems = docs.decision_log_format_problems([docs.Decision(1, fields)])

    assert problems == [f"docs/decision-log.md DL-1 is missing: {missing}"]


def test_decision_log_numbers_out_of_order_are_reported() -> None:
    entries = [docs.Decision(1, _DL_FIELDS), docs.Decision(3, _DL_FIELDS)]

    problems = docs.decision_log_format_problems(entries)

    assert problems == [
        "docs/decision-log.md: DL numbers must be 1..n in order, unique; got [1, 3]"
    ]


@pytest.mark.parametrize(
    ("superseded_by", "problems"),
    [
        ("none", []),
        ("DL-2", []),
        (
            "DL-7",
            [
                "docs/decision-log.md DL-1: Superseded by names DL-7, which isn't another entry "
                "in the log"
            ],
        ),
        (
            "DL-1",
            [
                "docs/decision-log.md DL-1: Superseded by names DL-1, which isn't another entry "
                "in the log"
            ],
        ),
        (
            "the next one",
            [
                'docs/decision-log.md DL-1: Superseded by must be "none" or name an entry '
                "(DL-<n>), got 'the next one'"
            ],
        ),
    ],
)
def test_superseded_by_must_be_none_or_another_entry(
    superseded_by: str, problems: list[str]
) -> None:
    entries = [
        docs.Decision(1, _DL_FIELDS | {"Superseded by": superseded_by}),
        docs.Decision(2, _DL_FIELDS),
    ]

    assert docs.superseded_by_problems(entries) == problems


def test_decision_log_fields_are_parsed_across_wrapped_lines(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_read(_path: str) -> str:
        return (
            "```\n### DL-<n>: <title>\n- **Date:** <YYYY-MM-DD>\n```\n\n"
            "### DL-1: First\n- **Date:** 2026-09-28\n- **Decision:** one\n  and two\n"
            "- **Superseded by:** DL-2\n"
        )

    monkeypatch.setattr(docs, "read", fake_read)

    assert docs.decision_log_entries() == [
        docs.Decision(1, {"Date": "2026-09-28", "Decision": "one and two", "Superseded by": "DL-2"})
    ]


def test_malformed_decision_log_heading_is_a_structure_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(docs, "read", _reading("### DL-1: ok\n\n### DL 2 wrong form\n"))

    with pytest.raises(docs.DocsStructureError, match="DL 2 wrong form"):
        docs.decision_log_entries()


# --- 7: developer-guide status ----------------------------------------------------------------


def test_status_line_names_the_latest_or_next_checkpoint() -> None:
    latest = docs.latest_checkpoint()
    allowed = {latest} | docs.next_checkpoints(latest, docs.checkpoint_order())

    status = docs.status_line_checkpoint()

    assert status in allowed, (
        f"{docs.DEVELOPER_GUIDE} Status names {status}; the latest checkpoint commit is "
        f"{latest}, so it must name one of {sorted(str(c) for c in allowed)}"
    )


# Slice 1 with a checkpoint inserted after its plan was written (design-change skill), and a
# slice 2 table that hasn't been planned yet.
_WITH_INSERTED = _slice(1, "1", "12", "13", "13a", "14", "17") | _slice(0, "1", "8")


@pytest.mark.parametrize(
    ("latest", "expected"),
    [
        ("S1-C12", {"S1-C13"}),  # mid-slice
        ("S1-C13", {"S1-C13a"}),  # the inserted checkpoint follows the row before it
        ("S1-C13a", {"S1-C14"}),  # and is followed by the next row
        ("S1-C17", {"S2-C1"}),  # the slice's last row: the next slice's first checkpoint
        ("S0-C8", {"S1-C1"}),  # the next slice's table names its first row
        ("S2-C2", {"S2-C3", "S3-C1"}),  # no table for the slice yet
    ],
)
def test_next_checkpoint_is_the_next_row_of_the_slice_table(
    latest: str, expected: set[str]
) -> None:
    following = docs.next_checkpoints(docs.Checkpoint.parse(latest), _WITH_INSERTED)

    assert {str(checkpoint) for checkpoint in following} == expected


def test_latest_checkpoint_missing_from_its_slice_table_is_a_structure_error() -> None:
    with pytest.raises(docs.DocsStructureError, match="S1-C15, is not a row"):
        docs.next_checkpoints(docs.Checkpoint(1, 15), _WITH_INSERTED)


@pytest.mark.parametrize(
    ("latest", "finished"),
    [
        ("S1-C17", False),  # the last planned row has an inserted one after it
        ("S1-C17a", True),  # the inserted last row is committed
    ],
)
def test_slice_is_finished_only_at_its_last_row(latest: str, finished: bool) -> None:
    order = _slice(1, "1", "17", "17a")

    assert docs.slice_finished(1, docs.Checkpoint.parse(latest), order) is finished


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("S1-C13", docs.Checkpoint(1, 13)),
        ("S1-C13a", docs.Checkpoint(1, 13, "a")),
        ("S12-C3b", docs.Checkpoint(12, 3, "b")),
    ],
)
def test_checkpoint_id_with_an_optional_letter_suffix_is_parsed(
    value: str, expected: docs.Checkpoint
) -> None:
    assert docs.Checkpoint.parse(value) == expected
    assert str(expected) == value


@pytest.mark.parametrize("value", ["S1-C13A", "S1-C13ab", "S1-C", "S1C13", "S1-C13-a"])
def test_malformed_checkpoint_id_is_a_structure_error(value: str) -> None:
    with pytest.raises(docs.DocsStructureError, match="is not a checkpoint ID"):
        docs.Checkpoint.parse(value)


def test_an_inserted_checkpoint_sorts_between_its_neighbours() -> None:
    ids = ["S1-C14", "S1-C13a", "S2-C1", "S1-C13", "S1-C9"]

    ordered = sorted(docs.Checkpoint.parse(value) for value in ids)

    assert [str(checkpoint) for checkpoint in ordered] == [
        "S1-C9",
        "S1-C13",
        "S1-C13a",
        "S1-C14",
        "S2-C1",
    ]


def _build_plan_with_slice_1_rows(*numbers: str) -> Callable[[str], str]:
    rows = "".join(f"| {n} | Name | Includes |\n" for n in numbers)

    def fake_read(_path: str) -> str:
        return (
            "## Slice 1 — Auth\n\n### Checkpoints\n\n| # | Checkpoint | Includes |\n"
            f"|---|---|---|\n{rows}\n### Done when\n\n## Slice 2 — notes for planning\n"
        )

    return fake_read


def test_checkpoint_order_comes_from_the_table_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(docs, "read", _build_plan_with_slice_1_rows("1", "2", "2a", "3"))

    order = docs.checkpoint_order()

    assert {s: [str(c) for c in rows] for s, rows in order.items()} == {
        1: ["S1-C1", "S1-C2", "S1-C2a", "S1-C3"]
    }


@pytest.mark.parametrize(
    ("numbers", "message"),
    [
        (("1", "2A"), "'2A' in the # column is not a checkpoint number"),
        (("1", "C2"), "'C2' in the # column is not a checkpoint number"),
        (("1", "3", "2"), "must start at 1 and run in order"),  # out of order
        (("1", "2a", "2"), "must start at 1 and run in order"),  # inserted row before its base
        (("1", "2", "2"), "must start at 1 and run in order"),  # a number twice
        (("2", "3"), "must start at 1 and run in order"),
    ],
)
def test_malformed_checkpoint_table_is_a_structure_error(
    monkeypatch: pytest.MonkeyPatch, numbers: tuple[str, ...], message: str
) -> None:
    monkeypatch.setattr(docs, "read", _build_plan_with_slice_1_rows(*numbers))

    with pytest.raises(docs.DocsStructureError, match=re.escape(message)):
        docs.checkpoint_order()


def test_status_line_names_an_inserted_checkpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        docs, "read", _reading("> **Status:** S1-C13a (Fix) done; next is S1-C14.\n")
    )

    assert docs.status_line_checkpoint() == docs.Checkpoint(1, 13, "a")


def test_status_line_with_a_malformed_checkpoint_is_a_structure_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(docs, "read", _reading("> **Status:** S1-C13A done.\n"))

    with pytest.raises(docs.DocsStructureError, match="'S1-C13A' is not a checkpoint ID"):
        docs.status_line_checkpoint()


def _history(shallow: str, log: str) -> Callable[..., str]:
    def fake_git(*args: str) -> str:
        return shallow if args[0] == "rev-parse" else log

    return fake_git


def test_shallow_history_is_an_error_not_a_skip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(docs, "_git", _history("true", "checkpoint(S0-C5): Model conventions"))

    with pytest.raises(docs.DocsStructureError, match="shallow"):
        docs.latest_checkpoint()


def test_history_without_a_checkpoint_commit_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(docs, "_git", _history("false", "docs: something\nchore: other"))

    with pytest.raises(docs.DocsStructureError, match="no `checkpoint"):
        docs.latest_checkpoint()


def test_latest_checkpoint_is_the_newest_checkpoint_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    log = "docs: x\ncheckpoint(S0-C5): Model conventions\ncheckpoint(S0-C4): Background jobs"
    monkeypatch.setattr(docs, "_git", _history("false", log))

    assert docs.latest_checkpoint() == docs.Checkpoint(0, 5)


def test_latest_checkpoint_can_be_an_inserted_one(monkeypatch: pytest.MonkeyPatch) -> None:
    log = "Merge pull request #9 from o/s1\ncheckpoint(S1-C13a): Fix\ncheckpoint(S1-C13): Class"
    monkeypatch.setattr(docs, "_git", _history("false", log))

    assert docs.latest_checkpoint() == docs.Checkpoint(1, 13, "a")


def test_checkpoint_commit_with_a_malformed_id_is_a_structure_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    log = "checkpoint(S1-C13A): Fix\ncheckpoint(S1-C13): Classification"
    monkeypatch.setattr(docs, "_git", _history("false", log))

    with pytest.raises(docs.DocsStructureError, match="'S1-C13A' is not a checkpoint ID"):
        docs.latest_checkpoint()


# --- 8: design-doc § references ---------------------------------------------------------------


def test_every_section_reference_resolves_to_a_design_doc_heading() -> None:
    problems = docs.unresolved_references(
        r"§(\d+(?:\.\d+)*)", docs.design_doc_sections(), f"is not a heading in {docs.DESIGN_DOC}"
    )

    assert problems == [], _report(problems)


# --- 9: Claude configuration ------------------------------------------------------------------


def test_build_plan_lists_every_agent_and_skill() -> None:
    problems = docs.config_differences(
        docs.claude_config_on_disk(),
        docs.claude_config_in_build_plan(),
        f'{docs.BUILD_PLAN} "Claude configuration"',
    )

    assert problems == [], _report(problems)


def test_developer_guide_lists_every_agent_and_skill() -> None:
    problems = docs.config_differences(
        docs.claude_config_on_disk(),
        docs.claude_config_in_developer_guide(),
        f"{docs.DEVELOPER_GUIDE} section 11",
    )

    assert problems == [], _report(problems)


def test_claude_config_on_disk_is_found() -> None:
    config = docs.claude_config_on_disk()

    assert "checkpoint-reviewer" in config.agents
    assert "checkpoint" in config.skills


def _open_entry(fix_by: str) -> docs.TechDebt:
    fields = {"Added": "S0-C1", "What": "x", "Why": "x", "Fix by": fix_by, "Status": "open"}
    return docs.TechDebt(number=1, fields=fields)


@pytest.mark.parametrize(
    ("latest", "overdue"),
    [
        (docs.Checkpoint(1, 3), False),  # Slice 1 still in progress
        (docs.Checkpoint(1, 8), True),  # Slice 1's last checkpoint is done
        (docs.Checkpoint(2, 1), True),  # a later slice has started
    ],
)
def test_open_entry_due_by_a_slice_is_overdue_once_the_slice_is_done(
    latest: docs.Checkpoint, overdue: bool
) -> None:
    problems = docs.overdue_tech_debt(
        [_open_entry("Slice 1, with the first models")], latest, _slice(1, "1", "3", "8")
    )

    assert bool(problems) is overdue, problems


@pytest.mark.parametrize(
    ("latest", "overdue"),
    [
        (docs.Checkpoint(0, 4), False),  # S0-C5 not reached yet
        (docs.Checkpoint(0, 5), True),  # S0-C5 is done and the entry is still open
    ],
)
def test_open_entry_due_by_a_checkpoint_is_overdue_once_it_is_done(
    latest: docs.Checkpoint, overdue: bool
) -> None:
    problems = docs.overdue_tech_debt(
        [_open_entry("S0-C5 (Model conventions)")], latest, _slice(0, "1", "8")
    )

    assert bool(problems) is overdue, problems


@pytest.mark.parametrize(
    ("latest", "overdue"),
    [
        ("S1-C13", False),  # the row before the inserted checkpoint
        ("S1-C13a", True),  # the inserted checkpoint is done
        ("S1-C14", True),
    ],
)
def test_open_entry_due_by_an_inserted_checkpoint_is_overdue_once_it_is_done(
    latest: str, overdue: bool
) -> None:
    problems = docs.overdue_tech_debt(
        [_open_entry("S1-C13a (Fix)")], docs.Checkpoint.parse(latest), _WITH_INSERTED
    )

    assert bool(problems) is overdue, problems


def test_malformed_fix_by_checkpoint_is_a_structure_error() -> None:
    with pytest.raises(docs.DocsStructureError, match="'S1-C13A' is not a checkpoint ID"):
        docs.fix_by_deadline(_open_entry("S1-C13A (Fix)"))


def test_tech_debt_entry_missing_a_field_is_reported() -> None:
    entry = docs.TechDebt(1, {"Added": "S0-C1", "What": "x", "Fix by": "S0-C7", "Status": "open"})

    assert docs.tech_debt_format_problems([entry]) == ["docs/tech-debt.md TD-1 is missing: Why"]


def test_tech_debt_numbers_with_a_gap_are_reported() -> None:
    fields = {"Added": "S0-C1", "What": "x", "Why": "x", "Fix by": "S0-C7", "Status": "open"}

    problems = docs.tech_debt_format_problems([docs.TechDebt(1, fields), docs.TechDebt(3, fields)])

    assert problems == ["docs/tech-debt.md: TD numbers must be 1..n in order, unique; got [1, 3]"]


def test_malformed_tech_debt_heading_is_a_structure_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_read(_path: str) -> str:
        return "### TD-1: ok\n\n### TD-2 - wrong form\n"

    monkeypatch.setattr(docs, "read", fake_read)

    with pytest.raises(docs.DocsStructureError, match="TD-2 - wrong form"):
        docs.tech_debt_entries()


def test_ownership_reports_missing_duplicate_and_undocumented_tables() -> None:
    owners = {"task": ["task", "subtask"], "sprint": ["subtask", "ghost"]}

    problems = docs.ownership_problems(owners, frozenset({"task", "subtask", "phase"}))

    assert problems == [
        "table `phase` (docs/schema-doc.md) must be in exactly one Owns cell of the "
        "docs/build-plan.md feature map; found 0: none",
        "table `subtask` (docs/schema-doc.md) must be in exactly one Owns cell of the "
        "docs/build-plan.md feature map; found 2: task, sprint",
        "table `ghost` is owned by `sprint` in the docs/build-plan.md feature map but has no "
        "### section in docs/schema-doc.md",
    ]


def test_enum_column_not_documented_as_enum_is_reported() -> None:
    documented = {"widget": docs.DocTable("widget", frozenset({"id", "name", "colour"}), {})}

    problems = docs.enum_mismatches(_synthetic_metadata(), documented)

    assert problems == [
        "`widget`.colour is an enum in the model, but docs/schema-doc.md doesn't document it as "
        "`enum: ...`"
    ]


def test_unresolved_reference_is_reported_with_its_location(tmp_path: Path) -> None:
    doc = tmp_path / "notes.md"
    doc.write_text("See §5 and §99.\n", encoding="utf-8")

    problems = docs.unresolved_references(r"§(\d+)", frozenset({"5"}), "is unknown", [doc])

    assert problems == [f"{doc}:1: §99 is unknown"]


def test_finding_no_reference_at_all_is_a_structure_error(tmp_path: Path) -> None:
    doc = tmp_path / "notes.md"
    doc.write_text("Nothing to see.\n", encoding="utf-8")

    with pytest.raises(docs.DocsStructureError, match="no reference"):
        docs.unresolved_references(r"§(\d+)", frozenset({"5"}), "is unknown", [doc])


def test_config_differences_are_reported_on_both_sides() -> None:
    on_disk = docs.ClaudeConfig(agents=frozenset({"a", "b"}), skills=frozenset({"s"}))
    listed = docs.ClaudeConfig(agents=frozenset({"b", "c"}), skills=frozenset({"s"}))

    assert docs.config_differences(on_disk, listed, "the doc") == [
        "agents in .claude/ but not in the doc: ['a']",
        "agents in the doc but not in .claude/: ['c']",
    ]
