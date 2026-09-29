"""The docs agree with the code and with each other (build-plan, "Verification").

Mechanical checks only; the `docs-consistency` agent reviews what needs judgment. Each test
reads files (and `Base.metadata`), never the database. Parsers are strict: a doc whose
structure changes fails with `DocsStructureError` instead of passing by finding nothing.
"""

from collections.abc import Callable
from enum import StrEnum
from pathlib import Path

import pytest
from sqlalchemy import Column, MetaData, String, Table

import app.models  # noqa: F401  # pyright: ignore[reportUnusedImport] -- registers every model
from app.core.base_model import Base
from app.core.enums import enum_type
from tests.support import docs


def _report(problems: list[str]) -> str:
    return "\n" + "\n".join(problems)


# --- 1-3: models vs schema-doc ----------------------------------------------------------------


def test_every_model_table_is_documented_and_not_deferred() -> None:
    problems = docs.model_tables_missing_from_schema_doc(
        Base.metadata, docs.schema_doc_tables(), docs.deferred_tables()
    )

    assert problems == [], _report(problems)


def test_model_columns_match_schema_doc() -> None:
    problems = docs.column_mismatches(Base.metadata, docs.schema_doc_tables())

    assert problems == [], _report(problems)


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


def test_missing_and_extra_columns_are_reported_separately() -> None:
    problems = docs.column_mismatches(
        _synthetic_metadata(), _documented({"id", "colour", "size"}, {"red", "blue"})
    )

    assert problems == [
        "`widget`: columns in the model but not in docs/schema-doc.md: name",
        "`widget`: columns in docs/schema-doc.md but not in the model: size",
    ]


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
        docs.tech_debt_entries(), docs.latest_checkpoint(), docs.checkpoints_per_slice()
    )

    assert problems == [], _report(problems)


# --- 7: developer-guide status ----------------------------------------------------------------


def test_status_line_names_the_latest_or_next_checkpoint() -> None:
    latest = docs.latest_checkpoint()
    allowed = {latest} | docs.next_checkpoints(latest, docs.checkpoints_per_slice())

    status = docs.status_line_checkpoint()

    assert status in allowed, (
        f"{docs.DEVELOPER_GUIDE} Status names {status}; the latest checkpoint commit is "
        f"{latest}, so it must name one of {sorted(str(c) for c in allowed)}"
    )


@pytest.mark.parametrize(
    ("latest", "expected"),
    [
        (docs.Checkpoint(0, 5), {docs.Checkpoint(0, 6)}),  # mid-slice
        (docs.Checkpoint(0, 8), {docs.Checkpoint(1, 1)}),  # the slice's last checkpoint
        (docs.Checkpoint(1, 2), {docs.Checkpoint(1, 3), docs.Checkpoint(2, 1)}),  # no table yet
    ],
)
def test_next_checkpoint_follows_the_slice_table(
    latest: docs.Checkpoint, expected: set[docs.Checkpoint]
) -> None:
    assert docs.next_checkpoints(latest, {0: 8}) == expected


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
        f"{docs.DEVELOPER_GUIDE} §10",
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
        [_open_entry("Slice 1, with the first models")], latest, {1: 8}
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
    problems = docs.overdue_tech_debt([_open_entry("S0-C5 (Model conventions)")], latest, {0: 8})

    assert bool(problems) is overdue, problems


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
