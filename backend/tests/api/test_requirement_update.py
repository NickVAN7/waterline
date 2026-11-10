"""Requirements' update and restriction change beyond who may call them, and the restriction
floor at creation and when a project is raised (design-doc §3.1, §5, §6.1, §10; build plan
S2-C6; DL-143, DL-161, DL-168, DL-207 to DL-211). Who gets 2xx/403/404 is in tests/api/authz/
(spec tests)."""

from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import (
    ActivityAction,
    ActivityEntityType,
    ProjectRole,
    RequirementStatus,
    RestrictionLevel,
)
from app.models.requirement import Requirement, RequirementRevision
from app.models.user import User
from tests.factories.project import ProjectFactory, ProjectMembershipFactory
from tests.factories.requirement import RequirementFactory
from tests.factories.user import UserFactory
from tests.support.activity import activity
from tests.support.authz import Tenancy, persona_user, sign_in_as, tenancy

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("session")]

REQUIREMENTS = "/api/projects/PMT/requirements"
ONE = f"{REQUIREMENTS}/1"
CREATED = ActivityAction.CREATED
UPDATED = ActivityAction.UPDATED
REQUIREMENT = ActivityEntityType.REQUIREMENT
LONG_AGO = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture
async def t() -> Tenancy:
    return await tenancy()


async def signed_in(client: AsyncClient, t: Tenancy, role: ProjectRole) -> User:
    user = await UserFactory.create_async()
    await ProjectMembershipFactory.create_async(project=t.project, user=user, role=role)
    await sign_in_as(client, user)
    return user


@pytest.fixture
async def member(client: AsyncClient, t: Tenancy) -> User:
    return await signed_in(client, t, ProjectRole.MEMBER)


@pytest.fixture
async def admin(client: AsyncClient, t: Tenancy) -> User:
    return await signed_in(client, t, ProjectRole.ADMIN)


async def create(client: AsyncClient, **body: object) -> dict[str, Any]:
    response = await client.post(REQUIREMENTS, json={"title": "Three-way match", **body})
    assert response.status_code == 201
    return response.json()


async def stored(session: AsyncSession, number: int = 1) -> Requirement:
    statement = (
        select(Requirement)
        .where(Requirement.number == number)
        .execution_options(populate_existing=True, include_deleted=True)
    )
    return (await session.execute(statement)).scalar_one()


async def revisions(session: AsyncSession, requirement: Requirement) -> list[tuple[object, ...]]:
    rows = await session.execute(
        select(
            RequirementRevision.revision_number,
            RequirementRevision.title,
            RequirementRevision.description_md,
            RequirementRevision.change_note,
        )
        .where(RequirementRevision.requirement_id == requirement.id)
        .order_by(RequirementRevision.revision_number)
    )
    return [tuple(row) for row in rows]


async def backdate(session: AsyncSession, requirement: Requirement) -> None:
    """Move `updated_at` into the past, so a test can tell whether a write moves it (`now()` is
    the transaction's start, the same instant all test long)."""
    await session.execute(
        update(Requirement).where(Requirement.id == requirement.id).values(updated_at=LONG_AGO)
    )


def fields(body: dict[str, Any]) -> list[tuple[list[object], str]]:
    return [(e["loc"], e["type"]) for e in body["details"]["fields"]]


async def updates(session: AsyncSession) -> list[tuple[object, ...]]:
    """The `updated` rows: `(entity_id, field, old, new, changed_by)`."""
    return [(r[1], *r[3:]) for r in await activity(session) if r[2] == UPDATED]


# --- Create: version 1 and the floor --------------------------------------------------------------


async def test_a_new_requirement_starts_at_version_1(
    client: AsyncClient, session: AsyncSession, member: User
) -> None:
    """Bug: setting the first revision pointer through the ORM bumps `version` to 2 (DL-207)."""
    body = await create(client)

    assert body["version"] == 1
    assert (await stored(session)).version == 1


@pytest.mark.parametrize(
    ("project_level", "level", "status"),
    [
        (RestrictionLevel.CONFIDENTIAL, "internal", 422),
        (RestrictionLevel.CONFIDENTIAL, None, 201),
        (RestrictionLevel.CONFIDENTIAL, "confidential", 201),
        (RestrictionLevel.INTERNAL, "internal", 201),
        (None, "internal", 201),
    ],
    ids=["below", "inherits", "equal", "internal-on-internal", "internal-on-none"],
)
async def test_creating_below_the_projects_level_is_a_422(
    client: AsyncClient,
    session: AsyncSession,
    t: Tenancy,
    member: User,
    project_level: RestrictionLevel | None,
    level: str | None,
    status: int,
) -> None:
    """Bug: a stored level below the project's accepted (DL-208), or a null or equal level
    refused (null inherits; None ranks as Internal)."""
    t.project.restriction_level = project_level
    await session.flush()

    response = await client.post(
        REQUIREMENTS, json={"title": "Payroll", "restriction_level": level}
    )

    assert response.status_code == status


async def test_the_floor_refusal_names_the_level_field_and_takes_no_number(
    client: AsyncClient, session: AsyncSession, t: Tenancy, member: User
) -> None:
    """Bug: the 422 on the wrong field, or the number taken before the check."""
    t.project.restriction_level = RestrictionLevel.CONFIDENTIAL
    await session.flush()

    response = await client.post(
        REQUIREMENTS, json={"title": "Payroll", "restriction_level": "internal"}
    )

    assert fields(response.json()) == [(["body", "restriction_level"], "below_project")]
    assert (await create(client))["number"] == 1


# --- PATCH: content and revisions -----------------------------------------------------------------


async def test_changing_the_title_makes_the_next_revision_with_its_note(
    client: AsyncClient, session: AsyncSession, member: User
) -> None:
    """Bug: no new revision on a content change, the note dropped, or the pointer left on
    revision 1 (design-doc §6.1)."""
    await create(client, description_md="old")

    response = await client.patch(
        ONE, json={"version": 1, "title": " Two-way match ", "change_note": "Scope cut"}
    )

    assert response.status_code == 200
    requirement = await stored(session)
    assert await revisions(session, requirement) == [
        (1, "Three-way match", "old", None),
        (2, "Two-way match", "old", "Scope cut"),
    ]
    current = await session.get(RequirementRevision, requirement.current_revision_id)
    assert current is not None
    assert current.revision_number == 2
    assert (requirement.title, requirement.version) == ("Two-way match", 2)
    assert (response.json()["title"], response.json()["version"]) == ("Two-way match", 2)


async def test_changing_the_description_makes_the_next_revision(
    client: AsyncClient, session: AsyncSession, member: User
) -> None:
    """Bug: only a title change counted as a content change."""
    await create(client, description_md="old")

    await client.patch(ONE, json={"version": 1, "description_md": "new"})

    requirement = await stored(session)
    assert await revisions(session, requirement) == [
        (1, "Three-way match", "old", None),
        (2, "Three-way match", "new", None),
    ]
    assert requirement.description_md == "new"


async def test_a_save_that_changes_nothing_makes_no_revision_and_keeps_the_version(
    client: AsyncClient, session: AsyncSession, member: User
) -> None:
    """Bug: a no-op save makes a revision or bumps `version` (design-doc §6.1: no-op saves
    create no revisions)."""
    await create(client, description_md="same")

    response = await client.patch(
        ONE,
        json={
            "version": 1,
            "title": "Three-way match",
            "description_md": "same",
            "status": "draft",
            "priority": "medium",
        },
    )

    assert response.status_code == 200
    requirement = await stored(session)
    assert [r[0] for r in await revisions(session, requirement)] == [1]
    assert requirement.version == 1
    assert await updates(session) == []


async def test_status_and_priority_are_logged_without_a_revision(
    client: AsyncClient, session: AsyncSession, member: User
) -> None:
    """Bug: a field change not logged, logged with the wrong old value, or making a revision
    (design-doc §10: `status` and `priority` are logged; §6.1: only content makes one)."""
    await create(client)

    response = await client.patch(
        ONE, json={"version": 1, "status": "in_progress", "priority": "high"}
    )

    assert response.status_code == 200
    requirement = await stored(session)
    assert (requirement.status, requirement.priority, requirement.version) == (
        "in_progress",
        "high",
        2,
    )
    assert [r[0] for r in await revisions(session, requirement)] == [1]
    assert await updates(session) == [
        (requirement.id, "status", "draft", "in_progress", member.id),
        (requirement.id, "priority", "medium", "high", member.id),
    ]


@pytest.mark.parametrize(
    "status", [s for s in RequirementStatus if s is not RequirementStatus.APPROVED]
)
async def test_a_member_moves_a_requirement_to_any_status_but_approved(
    client: AsyncClient, session: AsyncSession, member: User, status: RequirementStatus
) -> None:
    """Bug: a transition table where there is none (DL-148): any status to any other."""
    await create(client)
    await client.patch(ONE, json={"version": 1, "status": "rejected"})

    response = await client.patch(ONE, json={"version": 2, "status": status.value})

    assert response.status_code == 200
    assert (await stored(session)).status == status


async def test_a_stale_version_is_a_409_and_changes_nothing(
    client: AsyncClient, session: AsyncSession, member: User
) -> None:
    """Bug: a save based on an older copy overwrites a newer edit (design-doc §3)."""
    await create(client)
    await client.patch(ONE, json={"version": 1, "priority": "high"})

    response = await client.patch(ONE, json={"version": 1, "title": "Lost edit"})

    assert response.status_code == 409
    assert response.json()["code"] == "stale_version"
    requirement = await stored(session)
    assert (requirement.title, requirement.version) == ("Three-way match", 2)
    assert [r[0] for r in await revisions(session, requirement)] == [1]


@pytest.mark.parametrize(
    ("body", "error"),
    [
        ({"title": "   "}, (["body", "title"], "missing")),
        ({"title": "x" * 201}, (["body", "title"], "string_too_long")),
        ({"description_md": "x" * 20_001}, (["body", "description_md"], "string_too_long")),
        ({"title": "New", "change_note": "x" * 501}, (["body", "change_note"], "string_too_long")),
        ({"title": "New"} | {"version": None}, (["body", "version"], "int_type")),
    ],
    ids=["blank-title", "title-201", "description-20001", "note-501", "no-version"],
)
async def test_invalid_input_is_a_422_on_its_field(
    client: AsyncClient,
    session: AsyncSession,
    member: User,
    body: dict[str, object],
    error: tuple[list[object], str],
) -> None:
    """Bug: a limit missing or off by one (DL-143: title 200, description 20,000, note 500), a
    blank title accepted, or a save without `version`."""
    await create(client)

    response = await client.patch(ONE, json={"version": 1, **body})

    assert response.status_code == 422
    assert fields(response.json()) == [error]
    assert (await stored(session)).title == "Three-way match"


async def test_the_limits_themselves_are_accepted(client: AsyncClient, member: User) -> None:
    """Bug: a limit one too low (the other side of the 422 boundaries above)."""
    await create(client)

    response = await client.patch(
        ONE,
        json={
            "version": 1,
            "title": "x" * 200,
            "description_md": "x" * 20_000,
            "change_note": "x" * 500,
        },
    )

    assert response.status_code == 200


async def test_an_admins_approved_is_refused_before_the_version_and_changes_nothing(
    client: AsyncClient, session: AsyncSession, admin: User
) -> None:
    """Bug: the `use_approve` refusal after other fields were applied (DL-161)."""
    await create(client)

    response = await client.patch(ONE, json={"version": 1, "status": "approved", "priority": "low"})

    assert fields(response.json()) == [(["body", "status"], "use_approve")]
    requirement = await stored(session)
    assert (requirement.status, requirement.priority) == ("draft", "medium")


# --- PATCH: the reporter (DL-211) -----------------------------------------------------------------


async def test_reassigning_the_reporter_is_stored_and_logged(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    """Bug: `reporter_id` not logged (design-doc §10)."""
    await create(client)
    dana = await persona_user(t, "project_member")

    response = await client.patch(ONE, json={"version": 1, "reporter_id": str(dana.id)})

    assert response.status_code == 200
    requirement = await stored(session)
    assert requirement.reporter_id == dana.id
    assert await updates(session) == [
        (requirement.id, "reporter_id", str(admin.id), str(dana.id), admin.id)
    ]


@pytest.mark.parametrize("who", ["project_admin", "org_admin", "workspace_admin", "system_admin"])
async def test_the_reporter_may_be_anyone_who_may_create_requirements(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User, who: str
) -> None:
    """Bug: inherited admins refused as reporters (DL-211: who may create requirements)."""
    await create(client)
    user = await persona_user(t, who)

    response = await client.patch(ONE, json={"version": 1, "reporter_id": str(user.id)})

    assert response.status_code == 200
    assert (await stored(session)).reporter_id == user.id


@pytest.mark.parametrize("who", ["project_viewer", "org_member", "other_project_admin"])
async def test_a_reporter_who_may_not_create_requirements_is_not_member(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User, who: str
) -> None:
    """Bug: a viewer or someone outside the project accepted (DL-211)."""
    await create(client)
    user = await persona_user(t, who)

    response = await client.patch(ONE, json={"version": 1, "reporter_id": str(user.id)})

    assert response.status_code == 422
    assert fields(response.json()) == [(["body", "reporter_id"], "not_member")]
    assert (await stored(session)).reporter_id == admin.id


async def test_an_unknown_reporter_is_not_member(
    client: AsyncClient, session: AsyncSession, admin: User
) -> None:
    """Bug: an ID with no user is a 500 or accepted."""
    await create(client)

    response = await client.patch(
        ONE, json={"version": 1, "reporter_id": "00000000-0000-7000-8000-000000000000"}
    )

    assert fields(response.json()) == [(["body", "reporter_id"], "not_member")]


async def test_an_inherited_admin_on_an_ec_project_is_not_a_reporter(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    """Bug: the reporter check skips export control (DL-211: content access needed)."""
    await create(client)
    t.project.restriction_categories = ["export_controlled"]
    await session.flush()
    org_admin = await persona_user(t, "org_admin")

    response = await client.patch(ONE, json={"version": 1, "reporter_id": str(org_admin.id)})

    assert fields(response.json()) == [(["body", "reporter_id"], "not_member")]


async def test_a_deactivated_reporter_is_account_inactive(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    """Bug: a deactivated user accepted, or refused as `not_member` (DL-211)."""
    await create(client)
    dana = await persona_user(t, "project_member")
    dana.is_active = False
    await session.flush()

    response = await client.patch(ONE, json={"version": 1, "reporter_id": str(dana.id)})

    assert fields(response.json()) == [(["body", "reporter_id"], "account_inactive")]


async def test_an_unchanged_deactivated_reporter_never_blocks_a_save(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    """Bug: resending the reporter counts as a reassignment, so a save fails once its reporter
    is deactivated, or needs `reassign_reporter` (DL-211)."""
    dana = await signed_in(client, t, ProjectRole.MEMBER)
    await create(client)
    dana.is_active = False
    await session.flush()
    await sign_in_as(client, await persona_user(t, "project_member"))

    response = await client.patch(
        ONE, json={"version": 1, "reporter_id": str(dana.id), "priority": "high"}
    )

    assert response.status_code == 200
    assert (await stored(session)).priority == "high"


# --- PUT restriction ------------------------------------------------------------------------------


async def test_a_restriction_change_is_logged_without_a_version_bump_and_moves_updated_at(
    client: AsyncClient, session: AsyncSession, member: User
) -> None:
    """Bug: the change bumps `version` (DL-168), doesn't move `updated_at` (DL-210), or isn't
    logged field by field (design-doc §10)."""
    await create(client)
    requirement = await stored(session)
    await backdate(session, requirement)

    response = await client.put(
        f"{ONE}/restriction", json={"level": "confidential", "categories": ["pii", "financial"]}
    )

    assert response.status_code == 200
    requirement = await stored(session)
    assert (
        requirement.restriction_level,
        requirement.restriction_categories,
        requirement.version,
    ) == ("confidential", ["financial", "pii"], 1)
    assert requirement.updated_at > LONG_AGO
    assert await updates(session) == [
        (requirement.id, "restriction_level", None, "confidential", member.id),
        (requirement.id, "restriction_categories", "", "financial,pii", member.id),
    ]
    assert response.json()["version"] == 1


async def test_a_restriction_change_doesnt_stale_an_open_edit(
    client: AsyncClient, session: AsyncSession, member: User
) -> None:
    """Bug: a restriction change makes someone's content save a 409 (DL-168)."""
    await create(client)
    await client.put(f"{ONE}/restriction", json={"level": "confidential", "categories": []})

    response = await client.patch(ONE, json={"version": 1, "title": "Still mine"})

    assert response.status_code == 200


async def test_the_same_restriction_records_nothing(
    client: AsyncClient, session: AsyncSession, member: User
) -> None:
    """Bug: a no-op change logged or `updated_at` moved."""
    await create(client, restriction_level="internal")
    requirement = await stored(session)
    await backdate(session, requirement)

    response = await client.put(f"{ONE}/restriction", json={"level": "internal", "categories": []})

    assert response.status_code == 200
    assert await updates(session) == []
    assert (await stored(session)).updated_at == LONG_AGO


@pytest.mark.parametrize(
    ("body", "error"),
    [
        ({"level": "internal", "categories": []}, (["body", "level"], "below_project")),
        (
            {"level": "confidential", "categories": ["export_controlled"]},
            (["body", "categories"], "project_only"),
        ),
    ],
    ids=["below-project", "export-controlled"],
)
async def test_a_restriction_below_the_project_or_export_controlled_is_a_422(
    client: AsyncClient,
    session: AsyncSession,
    t: Tenancy,
    admin: User,
    body: dict[str, object],
    error: tuple[list[object], str],
) -> None:
    """Bug: an admin's lower goes below the project's (DL-208), or `export_controlled` lands on
    an item (§3.1: project-only)."""
    t.project.restriction_level = RestrictionLevel.CONFIDENTIAL
    await session.flush()
    await create(client, restriction_level="confidential")

    response = await client.put(f"{ONE}/restriction", json=body)

    assert response.status_code == 422
    assert fields(response.json()) == [error]
    assert (await stored(session)).restriction_level == "confidential"


async def test_lowering_to_inherit_is_allowed_on_a_restricted_project(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    """Bug: a null level treated as below the project's (DL-208: null inherits)."""
    t.project.restriction_level = RestrictionLevel.CONFIDENTIAL
    await session.flush()
    await create(client, restriction_level="confidential")

    response = await client.put(f"{ONE}/restriction", json={"level": None, "categories": []})

    assert response.status_code == 200
    assert (await stored(session)).restriction_level is None


# --- A project raise lifts its items (DL-208 to DL-210) -------------------------------------------


async def raise_project(client: AsyncClient, level: str | None) -> int:
    response = await client.put(
        "/api/projects/PMT/restriction", json={"level": level, "categories": []}
    )
    return response.status_code


async def test_raising_a_project_lifts_its_live_items_stored_below_it(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    """Bug: items left below the new floor, the change not logged on each or logged as someone
    else's, `updated_at` or `version` moved (DL-210, DL-168), or items already at or above it
    and inheriting ones touched."""
    internal = await RequirementFactory.create_async(
        project=t.project, number=1, restriction_level=RestrictionLevel.INTERNAL
    )
    await RequirementFactory.create_async(
        project=t.project, number=2, restriction_level=RestrictionLevel.CONFIDENTIAL
    )
    await RequirementFactory.create_async(project=t.project, number=3, restriction_level=None)
    await backdate(session, internal)

    assert await raise_project(client, "confidential") == 200

    lifted = await stored(session, 1)
    assert (lifted.restriction_level, lifted.updated_at, lifted.version) == (
        "confidential",
        LONG_AGO,
        1,
    )
    assert [(await stored(session, n)).restriction_level for n in (2, 3)] == ["confidential", None]
    assert await updates(session) == [
        (internal.id, "restriction_level", "internal", "confidential", admin.id)
    ]


async def test_raising_a_project_skips_items_in_the_trash(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    """Bug: the raise opts in to deleted rows (DL-209: restore raises them instead)."""
    await RequirementFactory.create_async(
        project=t.project,
        number=1,
        restriction_level=RestrictionLevel.INTERNAL,
        deleted_at=LONG_AGO,
    )

    assert await raise_project(client, "confidential") == 200

    assert (await stored(session, 1)).restriction_level == "internal"
    assert await updates(session) == []


@pytest.mark.parametrize(("old", "new"), [(None, "internal"), ("confidential", None)])
async def test_a_change_that_raises_no_floor_lifts_nothing(
    client: AsyncClient,
    session: AsyncSession,
    t: Tenancy,
    admin: User,
    old: str | None,
    new: str | None,
) -> None:
    """Bug: items lifted when the project's floor didn't rise (None and Internal rank the same;
    a lowered project leaves items where they are)."""
    t.project.restriction_level = None if old is None else RestrictionLevel(old)
    await session.flush()
    await RequirementFactory.create_async(
        project=t.project, number=1, restriction_level=RestrictionLevel.INTERNAL
    )

    assert await raise_project(client, new) == 200

    assert (await stored(session, 1)).restriction_level == "internal"
    assert await updates(session) == []


async def test_raising_a_project_leaves_other_projects_items_alone(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    """Bug: the lift query isn't scoped to the project."""
    ledger = await ProjectFactory.create_async(organization=t.org, key="LDG", name="Ledger")
    await RequirementFactory.create_async(
        project=ledger, number=1, restriction_level=RestrictionLevel.INTERNAL
    )

    assert await raise_project(client, "confidential") == 200

    row = (
        await session.scalars(
            select(Requirement)
            .where(Requirement.project_id == ledger.id)
            .execution_options(populate_existing=True)
        )
    ).one()
    assert row.restriction_level == "internal"


# --- Archived and export-controlled projects (security review) -----------------------------------


@pytest.mark.security
@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("PATCH", ONE, {"version": 1, "priority": "high"}),
        ("PUT", f"{ONE}/restriction", {"level": "confidential", "categories": []}),
    ],
    ids=["patch", "restriction"],
)
async def test_nothing_changes_a_requirement_in_an_archived_project(
    client: AsyncClient,
    session: AsyncSession,
    t: Tenancy,
    admin: User,
    method: str,
    path: str,
    body: dict[str, object],
) -> None:
    """Bug: the PUT's write check (in the service, after a `view` load) skipped, or PATCH's
    `update`, so an archived project takes writes (design-doc §5 step 1)."""
    await create(client)
    t.project.archived_at = LONG_AGO
    await session.flush()

    response = await client.request(method, path, json=body)

    assert response.status_code == 403
    requirement = await stored(session)
    assert (requirement.priority, requirement.restriction_level) == ("medium", None)


@pytest.mark.security
@pytest.mark.parametrize(
    "who", ["system_admin", "workspace_owner", "workspace_admin", "org_owner", "org_admin"]
)
async def test_patching_on_an_ec_project_is_404_to_inherited_admins(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User, who: str
) -> None:
    """Bug: the export-control gate skipped on PATCH (design-doc §3.1, §5 step 2)."""
    await create(client)
    t.project.restriction_categories = ["export_controlled"]
    await session.flush()
    await sign_in_as(client, await persona_user(t, who))

    response = await client.patch(ONE, json={"version": 1, "priority": "high"})
    missing = await client.patch("/api/projects/NOPE/requirements/1", json={"version": 1})

    assert (response.status_code, response.json()) == (404, missing.json())
    assert (await stored(session)).priority == "medium"
