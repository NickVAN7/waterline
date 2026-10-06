"""Strict parsers and comparisons for the docs consistency tests (`tests/unit/docs/`).

Each parser raises `DocsStructureError` when a doc no longer has the structure it expects (a
heading, a table header, a field line), so a restructured doc fails loudly instead of letting
a check pass by finding nothing. Comparisons return a list of problems; an empty list is a
pass. Every message names the files involved.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from functools import total_ordering
from pathlib import Path

from sqlalchemy import Enum, MetaData

REPO_ROOT = Path(__file__).resolve().parents[3]

SCHEMA_DOC = "docs/schema-doc.md"
BUILD_PLAN = "docs/build-plan.md"
DESIGN_DOC = "docs/design-doc.md"
DEVELOPER_GUIDE = "docs/developer-guide.md"
TECH_DEBT = "docs/tech-debt.md"


class DocsStructureError(AssertionError):
    """A doc lost the structure a parser relies on. Fix the doc or update the parser."""


def read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


# --- Generic markdown helpers -----------------------------------------------------------------


def section(text: str, heading: str, source: str) -> str:
    """The body under the heading line `heading` (exact text, e.g. "### Feature map"), up to
    the next heading of the same or a higher level."""
    level = len(heading) - len(heading.lstrip("#"))
    lines = text.splitlines()
    try:
        start = lines.index(heading)
    except ValueError:
        raise DocsStructureError(f"{source}: heading {heading!r} not found") from None
    body: list[str] = []
    for line in lines[start + 1 :]:
        match = re.match(r"^(#+) ", line)
        if match and len(match.group(1)) <= level:
            break
        body.append(line)
    return "\n".join(body)


def table_rows(body: str, header: str, source: str) -> list[list[str]]:
    """The cells of each row of the first markdown table in `body` whose header row is exactly
    `header` (e.g. "| Field | Type | Notes |")."""
    lines = body.splitlines()
    try:
        start = lines.index(header)
    except ValueError:
        raise DocsStructureError(f"{source}: table with header {header!r} not found") from None
    rows: list[list[str]] = []
    for line in lines[start + 2 :]:  # skip the |---| separator
        if not line.startswith("|"):
            break
        rows.append([cell.strip() for cell in line.strip().strip("|").split("|")])
    if not rows:
        raise DocsStructureError(f"{source}: table {header!r} has no rows")
    return rows


def _unquote(value: str) -> str:
    return value.strip().strip("`").strip()


def _drop_parentheses(value: str) -> str:
    return re.sub(r"\([^()]*\)", "", value)


# --- schema-doc -------------------------------------------------------------------------------


@dataclass(frozen=True)
class DocTable:
    name: str
    columns: frozenset[str]
    enums: dict[str, frozenset[str]]  # enum column -> documented values
    added_in: dict[str, int] = field(default_factory=dict[str, int])  # marked column -> slice


_TABLE_HEADING = re.compile(r"^### `([a-z_]+)`$", re.MULTILINE)
_FIELD_HEADER = "| Field | Type | Notes |"
# A column built in a later slice than its table (schema-doc conventions): its Notes cell
# starts with exactly this.
_ADDED_IN = re.compile(r"^Added in Slice (\d+)\.(?=\s|$)")


def schema_doc_tables() -> dict[str, DocTable]:
    """Every `### \\`<table>\\`` section of the schema doc, with its field table."""
    text = read(SCHEMA_DOC)
    names = _TABLE_HEADING.findall(text)
    if not names:
        raise DocsStructureError(f"{SCHEMA_DOC}: no `### \\`<table>\\`` sections found")
    tables: dict[str, DocTable] = {}
    for name in names:
        body = section(text, f"### `{name}`", SCHEMA_DOC)
        columns: set[str] = set()
        enums: dict[str, frozenset[str]] = {}
        added_in: dict[str, int] = {}
        for cells in table_rows(body, _FIELD_HEADER, f"{SCHEMA_DOC} `{name}`"):
            field_names = [_unquote(part) for part in cells[0].split(" / ")]
            columns.update(field_names)
            type_cell = cells[1]
            if type_cell.startswith("enum"):
                for field_name in field_names:
                    enums[field_name] = _enum_values(name, field_name, type_cell, body)
            marker_slice = _added_in_slice(name, cells[0], cells[2])
            if marker_slice is not None:
                added_in.update(dict.fromkeys(field_names, marker_slice))
        tables[name] = DocTable(name, frozenset(columns), enums, added_in)
    return tables


def _added_in_slice(table: str, field_cell: str, notes: str) -> int | None:
    """The slice in an `Added in Slice <n>.` marker at the start of a Notes cell; None when
    the cell has no marker. Anything else mentioning "added in slice" is malformed."""
    match = _ADDED_IN.match(notes)
    if match:
        return int(match.group(1))
    if re.search(r"added in slice", notes, re.IGNORECASE):
        raise DocsStructureError(
            f"{SCHEMA_DOC} `{table}`.{_unquote(field_cell)}: malformed marker in {notes!r}; the "
            f"Notes cell must start with exactly `Added in Slice <n>.`"
        )
    return None


def _enum_values(table: str, field: str, type_cell: str, body: str) -> frozenset[str]:
    """`enum: a / b / c` (optionally followed by `, nullable` or a parenthetical), or, for a
    bare `enum`, a "`<field>` values: `a`, `b`." paragraph in the table's section."""
    match = re.match(r"^enum: (.+)$", type_cell)
    if match:
        listed = _drop_parentheses(match.group(1)).split(",")[0]
        return frozenset(_unquote(value) for value in listed.split(" / "))
    paragraph = re.search(rf"`{re.escape(field)}` values: (.+?)\.\n", body, re.DOTALL)
    if paragraph is None:
        raise DocsStructureError(
            f"{SCHEMA_DOC} `{table}`.{field}: enum without values (expected `enum: a / b` or a "
            f'"`{field}` values: ..." paragraph)'
        )
    return frozenset(re.findall(r"`([^`]+)`", paragraph.group(1)))


def deferred_tables() -> frozenset[str]:
    """Table names in the first column of the schema doc's "Deferred tables" table (column
    references such as `session.user_agent` are not tables)."""
    body = section(read(SCHEMA_DOC), "## Deferred tables (not in v1)", SCHEMA_DOC)
    names: set[str] = set()
    for cells in table_rows(body, "| Table | When |", f"{SCHEMA_DOC} Deferred tables"):
        names.update(re.findall(r"`([a-z_]+)`", cells[0]))
    return frozenset(names)


# --- Models vs schema-doc ---------------------------------------------------------------------


def model_tables_missing_from_schema_doc(
    metadata: MetaData, documented: dict[str, DocTable], deferred: frozenset[str]
) -> list[str]:
    problems: list[str] = []
    for name in sorted(metadata.tables):
        if name not in documented:
            problems.append(
                f"table `{name}` is a model (Base.metadata) but has no ### `{name}` section in "
                f"{SCHEMA_DOC}"
            )
        if name in deferred:
            problems.append(
                f"table `{name}` is a model (Base.metadata) but is listed under Deferred tables "
                f"in {SCHEMA_DOC}"
            )
    return problems


@dataclass(frozen=True)
class ColumnCheck:
    """One column of a model table, from either side: the model, the schema doc, or both."""

    table: str
    column: str
    in_model: bool
    documented: bool
    added_in: int | None  # the schema doc's `Added in Slice <n>.` marker, if any

    def __str__(self) -> str:
        return f"{self.table}.{self.column}"


@dataclass(frozen=True)
class ColumnVerdict:
    problem: str | None = None
    skip_reason: str | None = None


def column_checks(metadata: MetaData, documented: dict[str, DocTable]) -> list[ColumnCheck]:
    """Every column of every model table that the schema doc documents, from both sides."""
    checks: list[ColumnCheck] = []
    for name, table in sorted(metadata.tables.items()):
        if name not in documented:
            continue  # reported by model_tables_missing_from_schema_doc
        doc_table = documented[name]
        model_columns = {column.name for column in table.columns}
        for column in sorted(model_columns | doc_table.columns):
            checks.append(
                ColumnCheck(
                    table=name,
                    column=column,
                    in_model=column in model_columns,
                    documented=column in doc_table.columns,
                    added_in=doc_table.added_in.get(column),
                )
            )
    return checks


def column_verdict(check: ColumnCheck, latest: Checkpoint, counts: dict[int, int]) -> ColumnVerdict:
    """A model column must be documented. A documented column must be in the model, unless
    its marker names a slice that isn't finished yet (`slice_finished`)."""
    if not check.documented:
        return ColumnVerdict(problem=f"`{check}` is in the model but not in {SCHEMA_DOC}")
    if check.in_model:
        return ColumnVerdict()
    if check.added_in is not None and not slice_finished(check.added_in, latest, counts):
        return ColumnVerdict(skip_reason=f"added in Slice {check.added_in} (schema-doc)")
    finished = (
        f" (marked `Added in Slice {check.added_in}.`, and that slice is finished)"
        if check.added_in is not None
        else ""
    )
    return ColumnVerdict(problem=f"`{check}` is in {SCHEMA_DOC} but not in the model{finished}")


def enum_mismatches(metadata: MetaData, documented: dict[str, DocTable]) -> list[str]:
    problems: list[str] = []
    for name, table in sorted(metadata.tables.items()):
        if name not in documented:
            continue
        for column in table.columns:
            if not isinstance(column.type, Enum):
                continue
            model_values = frozenset(column.type.enums)
            doc_values = documented[name].enums.get(column.name)
            if doc_values is None:
                problems.append(
                    f"`{name}`.{column.name} is an enum in the model, but {SCHEMA_DOC} doesn't "
                    f"document it as `enum: ...`"
                )
            elif model_values != doc_values:
                problems.append(
                    f"`{name}`.{column.name}: model values {sorted(model_values)} != "
                    f"{SCHEMA_DOC} values {sorted(doc_values)}"
                )
    return problems


# --- build-plan feature map -------------------------------------------------------------------

_FEATURE_MAP_HEADER = "| File name | Owns (tables) | Slice | Calls into (services) |"


def feature_map_owners() -> dict[str, list[str]]:
    """File name -> the tables its "Owns (tables)" cell names. A cell is a `;`/`,`-separated
    list of table names, column references (`task.next_subtask_number`), and parenthetical
    notes, or starts with "none"."""
    body = section(read(BUILD_PLAN), "### Feature map", BUILD_PLAN)
    owners: dict[str, list[str]] = {}
    for cells in table_rows(body, _FEATURE_MAP_HEADER, f"{BUILD_PLAN} Feature map"):
        area_match = re.match(r"^`([a-z_]+)`", cells[0])
        if area_match is None:
            raise DocsStructureError(f"{BUILD_PLAN} Feature map: bad file name cell {cells[0]!r}")
        area = area_match.group(1)
        owns = _drop_parentheses(cells[1]).strip()
        tables: list[str] = []
        if not owns.startswith("none"):
            for item in re.split(r"[;,]", owns):
                value = _unquote(item)
                if re.fullmatch(r"[a-z_]+\.[a-z_]+", value):
                    continue  # a column reference, not a table
                if not re.fullmatch(r"[a-z_]+", value):
                    raise DocsStructureError(
                        f"{BUILD_PLAN} Feature map, `{area}` row: {value!r} in the Owns cell "
                        f"is not a table name (put notes in parentheses)"
                    )
                tables.append(value)
        owners[area] = tables
    return owners


def ownership_problems(owners: dict[str, list[str]], documented: frozenset[str]) -> list[str]:
    problems: list[str] = []
    owned_by: dict[str, list[str]] = {}
    for area, tables in owners.items():
        for table in tables:
            owned_by.setdefault(table, []).append(area)
    for table in sorted(documented):
        areas = owned_by.get(table, [])
        if len(areas) != 1:
            problems.append(
                f"table `{table}` ({SCHEMA_DOC}) must be in exactly one Owns cell of the "
                f"{BUILD_PLAN} feature map; found {len(areas)}: {', '.join(areas) or 'none'}"
            )
    for table in sorted(set(owned_by) - documented):
        problems.append(
            f"table `{table}` is owned by `{owned_by[table][0]}` in the {BUILD_PLAN} feature "
            f"map but has no ### section in {SCHEMA_DOC}"
        )
    return problems


# --- Checkpoints and git history --------------------------------------------------------------


@total_ordering
@dataclass(frozen=True)
class Checkpoint:
    slice: int
    number: int

    @classmethod
    def parse(cls, value: str) -> Checkpoint:
        match = re.fullmatch(r"S(\d+)-C(\d+)", value)
        if match is None:
            raise DocsStructureError(f"{value!r} is not a checkpoint ID (S<slice>-C<n>)")
        return cls(int(match.group(1)), int(match.group(2)))

    def __lt__(self, other: Checkpoint) -> bool:
        return (self.slice, self.number) < (other.slice, other.number)

    def __str__(self) -> str:
        return f"S{self.slice}-C{self.number}"


def latest_checkpoint() -> Checkpoint:
    """The newest `checkpoint(<ID>): ...` commit. Needs full history (CI: fetch-depth 0)."""
    shallow = _git("rev-parse", "--is-shallow-repository")
    if shallow == "true":
        raise DocsStructureError(
            "git history is shallow, so the current checkpoint can't be found; clone with full "
            "history (in CI, actions/checkout with fetch-depth: 0)"
        )
    for subject in _git("log", "--format=%s").splitlines():
        match = re.match(r"^checkpoint\((S\d+-C\d+)\):", subject)
        if match:
            return Checkpoint.parse(match.group(1))
    raise DocsStructureError("git log has no `checkpoint(<ID>): ...` commit")


def _git(*args: str) -> str:
    # A fixed git command with no shell; git comes from PATH, as in the developer CLI.
    result = subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def slice_finished(slice_number: int, latest: Checkpoint, counts: dict[int, int]) -> bool:
    """Whether `slice_number` is done, given the latest `checkpoint(...)` commit: a later slice
    has started, or the latest commit is the slice's last checkpoint (`counts`, from its
    "### Checkpoints" table; a slice without one is finished only once a later slice starts)."""
    return latest.slice > slice_number or latest == Checkpoint(
        slice_number, counts.get(slice_number, -1)
    )


def checkpoints_per_slice() -> dict[int, int]:
    """Slice number -> its checkpoint count, for slices whose build-plan section already has a
    "### Checkpoints" table."""
    text = read(BUILD_PLAN)
    counts: dict[int, int] = {}
    for match in re.finditer(r"^## Slice (\d+) ", text, re.MULTILINE):
        slice_number = int(match.group(1))
        body = section(text, text[match.start() : text.index("\n", match.start())], BUILD_PLAN)
        if "### Checkpoints" not in body.splitlines():
            continue
        rows = table_rows(
            section(body, "### Checkpoints", BUILD_PLAN),
            "| # | Checkpoint | Includes |",
            f"{BUILD_PLAN} Slice {slice_number} checkpoints",
        )
        counts[slice_number] = len(rows)
    if not counts:
        raise DocsStructureError(f"{BUILD_PLAN}: no slice has a ### Checkpoints table")
    return counts


def next_checkpoints(latest: Checkpoint, counts: dict[int, int]) -> frozenset[Checkpoint]:
    """The checkpoint(s) that can follow `latest`: the next in its slice, or the first of the
    next slice once the slice is done. Both, if the slice has no checkpoint table yet."""
    following = Checkpoint(latest.slice, latest.number + 1)
    next_slice = Checkpoint(latest.slice + 1, 1)
    count = counts.get(latest.slice)
    if count is None:
        return frozenset({following, next_slice})
    return frozenset({following if latest.number < count else next_slice})


def status_line_checkpoint() -> Checkpoint:
    """The first checkpoint ID in the developer guide's `> **Status:**` line."""
    text = read(DEVELOPER_GUIDE)
    match = re.search(r"^> \*\*Status:\*\*(.*(?:\n>.*)*)", text, re.MULTILINE)
    if match is None:
        raise DocsStructureError(f"{DEVELOPER_GUIDE}: no `> **Status:**` line")
    checkpoint = re.search(r"S\d+-C\d+", match.group(1))
    if checkpoint is None:
        raise DocsStructureError(
            f"{DEVELOPER_GUIDE}: the Status line names no checkpoint ID (S<slice>-C<n>)"
        )
    return Checkpoint.parse(checkpoint.group(0))


# --- Tech-debt log ----------------------------------------------------------------------------

TD_FIELDS = ("Added", "What", "Why", "Fix by", "Status")


@dataclass(frozen=True)
class TechDebt:
    number: int
    fields: dict[str, str]

    @property
    def is_open(self) -> bool:
        status = self.fields["Status"]
        if status.startswith("open"):
            return True
        if status.startswith("resolved"):
            return False
        raise DocsStructureError(
            f"{TECH_DEBT} TD-{self.number}: Status must start with 'open' or 'resolved', got "
            f"{status!r}"
        )


def tech_debt_entries() -> list[TechDebt]:
    # The entry-format template sits in a fenced code block; it isn't an entry.
    text = re.sub(r"^```.*?^```", "", read(TECH_DEBT), flags=re.MULTILINE | re.DOTALL)
    malformed = [
        line
        for line in re.findall(r"^### TD.*$", text, re.MULTILINE)
        if not re.match(r"^### TD-\d+: ", line)
    ]
    if malformed:
        raise DocsStructureError(f"{TECH_DEBT}: headings not in `### TD-<n>: ` form: {malformed}")
    headings = list(re.finditer(r"^### TD-(\d+): ", text, re.MULTILINE))
    if not headings:
        raise DocsStructureError(f"{TECH_DEBT}: no `### TD-<n>: ` entries")
    entries: list[TechDebt] = []
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        body = text[heading.end() : end]
        fields = {
            match.group(1): " ".join(match.group(2).split())
            for match in re.finditer(r"^- \*\*([^*]+):\*\* (.*(?:\n  .*)*)", body, re.MULTILINE)
        }
        entries.append(TechDebt(int(heading.group(1)), fields))
    return entries


def tech_debt_format_problems(entries: list[TechDebt]) -> list[str]:
    problems: list[str] = []
    for entry in entries:
        missing = [field for field in TD_FIELDS if field not in entry.fields]
        if missing:
            problems.append(f"{TECH_DEBT} TD-{entry.number} is missing: {', '.join(missing)}")
    numbers = [entry.number for entry in entries]
    if numbers != list(range(1, len(numbers) + 1)):
        problems.append(f"{TECH_DEBT}: TD numbers must be 1..n in order, unique; got {numbers}")
    return problems


def fix_by_deadline(entry: TechDebt) -> tuple[Checkpoint | None, int | None]:
    """(checkpoint, None) for `S0-C7 ...`, (None, slice) for `Slice 1 ...`."""
    fix_by = entry.fields["Fix by"]
    checkpoint = re.match(r"^(S\d+-C\d+)\b", fix_by)
    if checkpoint:
        return Checkpoint.parse(checkpoint.group(1)), None
    slice_match = re.match(r"^Slice (\d+)\b", fix_by)
    if slice_match:
        return None, int(slice_match.group(1))
    raise DocsStructureError(
        f"{TECH_DEBT} TD-{entry.number}: Fix by must start with a checkpoint ID (S0-C7) or "
        f"'Slice <n>', got {fix_by!r}"
    )


def overdue_tech_debt(
    entries: list[TechDebt], latest: Checkpoint, counts: dict[int, int]
) -> list[str]:
    """Open entries whose Fix by is already done: a checkpoint at or before the latest
    `checkpoint(...)` commit, or a slice that is finished."""
    problems: list[str] = []
    for entry in entries:
        if not entry.is_open:
            continue
        checkpoint, slice_number = fix_by_deadline(entry)
        if checkpoint is not None and checkpoint <= latest:
            problems.append(
                f"{TECH_DEBT} TD-{entry.number} is open, but its Fix by ({checkpoint}) is done "
                f"(latest checkpoint commit: {latest})"
            )
        if slice_number is not None and slice_finished(slice_number, latest, counts):
            problems.append(
                f"{TECH_DEBT} TD-{entry.number} is open, but its Fix by (Slice {slice_number}) "
                f"is finished (latest checkpoint commit: {latest})"
            )
    return problems


# --- Cross-file references --------------------------------------------------------------------


def reference_files() -> list[Path]:
    """Files whose TD-n and § references must resolve: docs/ (except the historical review
    records in docs/reviews/), the CLAUDE.md files, and .claude/. Listed through git (tracked
    plus untracked-but-not-ignored), so caches, editor backups, and local settings are never
    scanned."""
    listed = _git(
        "ls-files",
        "--cached",
        "--others",
        "--exclude-standard",
        "--",
        "docs",
        "CLAUDE.md",
        "backend/CLAUDE.md",
        "frontend/CLAUDE.md",
        ".claude",
    )
    files = [
        REPO_ROOT / name
        for name in sorted(set(listed.splitlines()))
        if not name.startswith("docs/reviews/") and (REPO_ROOT / name).is_file()
    ]
    if not files:
        raise DocsStructureError("git lists no docs, CLAUDE.md, or .claude files to scan")
    return files


def unresolved_references(
    pattern: str, known: frozenset[str], what: str, files: list[Path] | None = None
) -> list[str]:
    """`pattern`'s first group, anywhere in `files` (default: `reference_files()`), must be in
    `known`. Finding no reference at all is a structure error, not a pass."""
    problems: list[str] = []
    found = 0
    for path in reference_files() if files is None else files:
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for match in re.finditer(pattern, line):
                found += 1
                if match.group(1) not in known:
                    shown = path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path
                    location = f"{shown}:{line_number}"
                    problems.append(f"{location}: {match.group(0)} {what}")
    if not found:
        raise DocsStructureError(f"no reference matching {pattern!r} found; check the pattern")
    return problems


def design_doc_sections() -> frozenset[str]:
    numbers = re.findall(r"^#{2,6} (\d+(?:\.\d+)*)\.? ", read(DESIGN_DOC), re.MULTILINE)
    if not numbers:
        raise DocsStructureError(f"{DESIGN_DOC}: no numbered headings (## 1. …, ### 1.1 …)")
    return frozenset(numbers)


# --- Claude configuration ---------------------------------------------------------------------


@dataclass(frozen=True)
class ClaudeConfig:
    agents: frozenset[str]
    skills: frozenset[str]


def claude_config_on_disk() -> ClaudeConfig:
    return ClaudeConfig(
        agents=frozenset(path.stem for path in (REPO_ROOT / ".claude/agents").glob("*.md")),
        skills=frozenset(
            path.parent.name for path in (REPO_ROOT / ".claude/skills").glob("*/SKILL.md")
        ),
    )


def claude_config_in_build_plan() -> ClaudeConfig:
    body = section(read(BUILD_PLAN), "### Claude configuration (in the repo)", BUILD_PLAN)
    found = re.findall(r"\*\*`([a-z-]+)` (agent|skill)\*\*", body)
    if not found:
        raise DocsStructureError(
            f"{BUILD_PLAN} Claude configuration: no **`<name>` agent** / **`<name>` skill** items"
        )
    return ClaudeConfig(
        agents=frozenset(name for name, kind in found if kind == "agent"),
        skills=frozenset(name for name, kind in found if kind == "skill"),
    )


def claude_config_in_developer_guide() -> ClaudeConfig:
    body = section(read(DEVELOPER_GUIDE), "## 11. Claude Code configuration", DEVELOPER_GUIDE)
    return ClaudeConfig(agents=_bullet_names(body, "Agents"), skills=_bullet_names(body, "Skills"))


def _bullet_names(body: str, label: str) -> frozenset[str]:
    """Backticked names in the `- **<label>** (...): `a`, `b`.` bullet, which may wrap."""
    match = re.search(
        rf"^- \*\*{label}\*\* \([^)]*\): (.*?)(?=^- |\Z)", body, re.MULTILINE | re.DOTALL
    )
    if match is None:
        raise DocsStructureError(f"{DEVELOPER_GUIDE} section 11: no `- **{label}** (...):` bullet")
    names = frozenset(name for name in re.findall(r"`([a-z-]+)`", match.group(1)))
    if not names:
        raise DocsStructureError(f"{DEVELOPER_GUIDE} section 11: the {label} bullet names nothing")
    return names


def config_differences(expected: ClaudeConfig, listed: ClaudeConfig, source: str) -> list[str]:
    problems: list[str] = []
    for kind, on_disk, in_doc in (
        ("agents", expected.agents, listed.agents),
        ("skills", expected.skills, listed.skills),
    ):
        if on_disk - in_doc:
            problems.append(f"{kind} in .claude/ but not in {source}: {sorted(on_disk - in_doc)}")
        if in_doc - on_disk:
            problems.append(f"{kind} in {source} but not in .claude/: {sorted(in_doc - on_disk)}")
    return problems
