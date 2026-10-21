"""Authorization of `PUT /api/projects/{key}/classification` (build plan, "The classification API",
DL-81, its action column; the actions, DL-82; design-doc §3.1 "Who sets it"; §5):

- a higher level or an added category needs `project.raise_classification`; a lower level or a
  removed category `project.lower_classification`; both for a change that does both; either for
  a change that does neither, the classification already held included. Unclassified ranks as
  Internal, so a change between them is neither;
- both are project admins', inherited included; 403 for a project member or viewer; 404, the
  same as a missing project and naming nothing, for whoever can't see the project; 403 on an
  archived project, to everyone (a mutation);
- on an export-controlled project an inherited admin may still raise, but lowering the level or
  removing any category, `export_controlled` included, needs an explicit project admin (403
  otherwise);
- an allowed change returns 200 with the project's new `classification_level` and
  `classification_categories`, and stores them.

On every denial the classification is unchanged and no audit event is recorded. The confirmation
fields' validation and the audit-event details are tested elsewhere (the main session). Personas
are relative to workspace "Acme Consulting", org "Bolt Foods" (bolt-foods), and project "Payments"
(PMT) (tests/support/authz.py, `tenancy`).
"""

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import ClassificationLevel, ProjectRole
from app.models.audit_event import AuditEvent
from app.models.project import Project, ProjectMembership
from app.models.user import User
from tests.factories.project import ProjectMembershipFactory
from tests.factories.user import UserFactory
from tests.support.authz import Tenancy, persona_user, sign_in_as, tenancy

pytestmark = [pytest.mark.anyio, pytest.mark.security, pytest.mark.usefixtures("session")]

INHERITED_ADMINS = ["system_admin", "workspace_owner", "workspace_admin", "org_owner", "org_admin"]
INHERITED_NON_SYSTEM = ["workspace_owner", "workspace_admin", "org_owner", "org_admin"]
PROJECT_ADMINS = [*INHERITED_ADMINS, "project_admin"]
SEE_ONLY = ["project_member", "project_viewer"]
PROJECT_UNSEEN = [
    "org_member",
    "other_project_admin",
    "workspace_member",
    "other_org_owner",
    "other_workspace_owner",
    "nobody",
]

URL = "/api/projects/PMT/classification"
MISSING_URL = "/api/projects/ZZZ/classification"
ARCHIVED_AT = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
IVY = "ivy@bolt.example"

NONE: list[str] = []  # no categories
INTERNAL = ClassificationLevel.INTERNAL
CONFIDENTIAL = ClassificationLevel.CONFIDENTIAL
RESTRICTED = ClassificationLevel.RESTRICTED

# (starting level, starting categories) → (body level, body categories), on a project that isn't
# export-controlled.
RAISES = [
    pytest.param((INTERNAL, NONE), ("confidential", NONE), id="level-up"),
    pytest.param(
        (CONFIDENTIAL, ["pii"]), ("confidential", ["pii", "financial"]), id="add-category"
    ),
    pytest.param((None, NONE), ("restricted", ["proprietary"]), id="unclassified-to-restricted"),
]
LOWERS = [
    pytest.param((RESTRICTED, NONE), ("confidential", NONE), id="level-down"),
    pytest.param((CONFIDENTIAL, ["pii", "financial"]), ("confidential", ["pii"]), id="remove-one"),
    pytest.param((CONFIDENTIAL, NONE), (None, NONE), id="confidential-to-unclassified"),
]
BOTH_WAYS = [
    pytest.param((CONFIDENTIAL, ["pii"]), ("confidential", ["financial"]), id="swap-category"),
    pytest.param((INTERNAL, ["pii"]), ("restricted", NONE), id="up-and-remove"),
]
NEITHER = [
    pytest.param((CONFIDENTIAL, ["pii"]), ("confidential", ["pii"]), id="already-held"),
    pytest.param((None, NONE), ("internal", NONE), id="unclassified-to-internal"),
    pytest.param((INTERNAL, NONE), (None, NONE), id="internal-to-unclassified"),
]

Start = tuple[ClassificationLevel | None, list[str]]
Body = tuple[str | None, list[str]]


async def signed_in(client: AsyncClient, who: str) -> tuple[Tenancy, User]:
    t = await tenancy()
    user = await persona_user(t, who)
    await sign_in_as(client, user)
    return t, user


async def classify(
    session: AsyncSession, t: Tenancy, level: ClassificationLevel | None, categories: list[str]
) -> None:
    t.project.classification_level = level
    t.project.classification_categories = categories
    await session.flush()


async def archive(session: AsyncSession, t: Tenancy) -> None:
    t.project.archived_at = ARCHIVED_AT
    await session.flush()


async def ivy(t: Tenancy) -> User:
    """An explicit member of PMT (role member) with no other membership."""
    person = await UserFactory.create_async(email=IVY, name="Ivy Moss", is_system_admin=False)
    await ProjectMembershipFactory.create_async(
        project=t.project, user=person, role=ProjectRole.MEMBER
    )
    return person


async def stored(session: AsyncSession, t: Tenancy) -> tuple[str | None, set[str]]:
    row = (
        await session.execute(
            select(Project.classification_level, Project.classification_categories).where(
                Project.id == t.project.id
            )
        )
    ).one()
    return (row[0], set(row[1]))


async def audit_events(session: AsyncSession) -> int | None:
    return await session.scalar(select(func.count()).select_from(AuditEvent))


def body(level: str | None, categories: list[str], **extra: Any) -> dict[str, Any]:
    return {"level": level, "categories": categories, **extra}


def confirmation(*member_ids: uuid.UUID) -> dict[str, Any]:
    """Build plan: adding `export_controlled` needs `export_control_confirmed: true` and
    `confirmed_member_ids`, the project's current explicit members."""
    return {
        "export_control_confirmed": True,
        "confirmed_member_ids": [str(member_id) for member_id in member_ids],
    }


def assert_forbidden(response: Response) -> None:
    assert (response.status_code, response.json().get("code")) == (403, "forbidden")


def assert_classified(response: Response, level: str | None, categories: set[str]) -> None:
    assert response.status_code == 200
    data = response.json()
    assert (data["classification_level"], set(data["classification_categories"])) == (
        level,
        categories,
    )


# --- Who may raise, lower, both, or neither (a project that isn't export-controlled) -------------


@pytest.mark.parametrize(("start", "change"), RAISES)
@pytest.mark.parametrize("who", PROJECT_ADMINS)
async def test_project_admins_inherited_included_may_raise(
    client: AsyncClient, session: AsyncSession, who: str, start: Start, change: Body
) -> None:
    """§3.1: "Project admins (including inherited) set and raise them"."""
    t, _ = await signed_in(client, who)
    await classify(session, t, *start)

    response = await client.put(URL, json=body(*change))

    assert_classified(response, change[0], set(change[1]))
    assert await stored(session, t) == (change[0], set(change[1]))


@pytest.mark.parametrize(("start", "change"), LOWERS)
@pytest.mark.parametrize("who", PROJECT_ADMINS)
async def test_project_admins_inherited_included_may_lower(
    client: AsyncClient, session: AsyncSession, who: str, start: Start, change: Body
) -> None:
    """§3.1: "Lowering a level or removing a category is project-admin only" (inherited
    included, on a project that isn't export-controlled; DL-82)."""
    t, _ = await signed_in(client, who)
    await classify(session, t, *start)

    response = await client.put(URL, json=body(*change))

    assert_classified(response, change[0], set(change[1]))
    assert await stored(session, t) == (change[0], set(change[1]))


@pytest.mark.parametrize(("start", "change"), BOTH_WAYS)
@pytest.mark.parametrize("who", PROJECT_ADMINS)
async def test_project_admins_may_make_a_change_that_both_raises_and_lowers(
    client: AsyncClient, session: AsyncSession, who: str, start: Start, change: Body
) -> None:
    """DL-81: "both for a change that does both"."""
    t, _ = await signed_in(client, who)
    await classify(session, t, *start)

    response = await client.put(URL, json=body(*change))

    assert_classified(response, change[0], set(change[1]))
    assert await stored(session, t) == (change[0], set(change[1]))


@pytest.mark.parametrize(("start", "change"), NEITHER)
@pytest.mark.parametrize("who", [*INHERITED_NON_SYSTEM, "project_admin"])
async def test_project_admins_may_make_a_change_that_neither_raises_nor_lowers(
    client: AsyncClient, session: AsyncSession, who: str, start: Start, change: Body
) -> None:
    """DL-81, DL-82: "either for a change that does neither, including the classification
    already held"; unclassified ranks as Internal, so a change between them is neither."""
    t, _ = await signed_in(client, who)
    await classify(session, t, *start)

    response = await client.put(URL, json=body(*change))

    assert_classified(response, change[0], set(change[1]))
    assert await stored(session, t) == (change[0], set(change[1]))


@pytest.mark.parametrize("who", PROJECT_ADMINS)
async def test_project_admins_may_mark_a_project_export_controlled_with_the_confirmation(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    """§3.1 and DL-82: adding `export_controlled` is a raise, so inherited admins may too; the
    request carries the confirmation, listing the current explicit members (build plan)."""
    t, _ = await signed_in(client, who)
    await classify(session, t, INTERNAL, [])
    await ivy(t)
    explicit = await session.scalars(
        select(ProjectMembership.user_id).where(ProjectMembership.project_id == t.project.id)
    )

    response = await client.put(
        URL, json=body("internal", ["export_controlled"], **confirmation(*explicit))
    )

    assert_classified(response, "internal", {"export_controlled"})
    assert await stored(session, t) == ("internal", {"export_controlled"})


@pytest.mark.parametrize(
    ("start", "change"),
    [*RAISES, *LOWERS, *BOTH_WAYS, *NEITHER],
)
@pytest.mark.parametrize("who", SEE_ONLY)
async def test_a_project_member_or_viewer_gets_403_for_any_change(
    client: AsyncClient, session: AsyncSession, who: str, start: Start, change: Body
) -> None:
    """§5, "Project roles": classification is not a member's or viewer's to set on the project;
    a no-op needs either action too (DL-82). "A change the caller lacks the action for is a
    403" (build plan)."""
    t, _ = await signed_in(client, who)
    await classify(session, t, *start)
    before = await audit_events(session)

    response = await client.put(URL, json=body(*change))

    assert_forbidden(response)
    assert await stored(session, t) == (start[0], set(start[1]))
    assert await audit_events(session) == before


# --- Whoever can't see the project: 404 ---------------------------------------------------------


@pytest.mark.parametrize("who", PROJECT_UNSEEN)
async def test_the_change_is_404_naming_nothing_to_who_cannot_see_the_project(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    """§5: failures on entities the user can't see return 404, not 403, so existence isn't
    leaked; the body reads the same as for a project that doesn't exist."""
    t, _ = await signed_in(client, who)
    await classify(session, t, INTERNAL, ["pii"])
    await ivy(t)
    before = await audit_events(session)

    response = await client.put(URL, json=body("restricted", ["pii", "financial"]))
    missing = await client.put(MISSING_URL, json=body("restricted", ["pii", "financial"]))

    assert (response.status_code, response.json()["code"]) == (404, "not_found")
    assert response.json() == missing.json()
    for name in ("Bolt Foods", "bolt-foods", "Payments", "PMT", IVY, "Ivy Moss"):
        assert name not in response.text
    assert await stored(session, t) == ("internal", {"pii"})
    assert await audit_events(session) == before


# --- An archived project: 403 to everyone (§5, step 1) ------------------------------------------


@pytest.mark.parametrize(
    ("start", "change"),
    [RAISES[0], LOWERS[0], NEITHER[0]],
)
@pytest.mark.parametrize("who", [*PROJECT_ADMINS, *SEE_ONLY])
async def test_an_archived_project_refuses_every_change_with_403(
    client: AsyncClient, session: AsyncSession, who: str, start: Start, change: Body
) -> None:
    """DL-82: both actions are project-level mutations, so an archived project denies them to
    everyone, system admins included."""
    t, _ = await signed_in(client, who)
    await classify(session, t, *start)
    await archive(session, t)
    before = await audit_events(session)

    response = await client.put(URL, json=body(*change))

    assert_forbidden(response)
    assert await stored(session, t) == (start[0], set(start[1]))
    assert await audit_events(session) == before


# --- An export-controlled project (§3.1; DL-82) -------------------------------------------------

# Changes from (confidential, [export_controlled, pii]).
EC_START: Start = (CONFIDENTIAL, ["export_controlled", "pii"])
EC_RAISES = [
    pytest.param(("restricted", ["export_controlled", "pii"]), id="level-up"),
    pytest.param(("confidential", ["export_controlled", "pii", "financial"]), id="add-category"),
]
EC_LOWERS = [
    pytest.param(("internal", ["export_controlled", "pii"]), id="level-down"),
    pytest.param((None, ["export_controlled", "pii"]), id="to-unclassified"),
    pytest.param(("confidential", ["export_controlled"]), id="remove-other-category"),
    pytest.param(("confidential", ["pii"]), id="remove-export-controlled"),
    pytest.param(("restricted", ["pii"]), id="up-and-remove-export-controlled"),
    pytest.param(("confidential", ["export_controlled", "financial"]), id="swap-category"),
]


@pytest.mark.parametrize("change", EC_RAISES)
@pytest.mark.parametrize("who", PROJECT_ADMINS)
async def test_every_project_admin_may_still_raise_an_export_controlled_project(
    client: AsyncClient, session: AsyncSession, who: str, change: Body
) -> None:
    """§3.1: inherited admins keep management access, "raising its classification" included."""
    t, _ = await signed_in(client, who)
    await classify(session, t, *EC_START)

    response = await client.put(URL, json=body(*change))

    assert_classified(response, change[0], set(change[1]))
    assert await stored(session, t) == (change[0], set(change[1]))


@pytest.mark.parametrize("change", EC_LOWERS)
@pytest.mark.parametrize("who", INHERITED_ADMINS)
async def test_an_inherited_admin_gets_403_lowering_an_export_controlled_project(
    client: AsyncClient, session: AsyncSession, who: str, change: Body
) -> None:
    """§3.1: "On an export-controlled project, inherited admins without an explicit membership
    may only raise"; "Inherited admins can't remove [`export_controlled`]"."""
    t, _ = await signed_in(client, who)
    await classify(session, t, *EC_START)
    before = await audit_events(session)

    response = await client.put(URL, json=body(*change))

    assert_forbidden(response)
    assert await stored(session, t) == ("confidential", {"export_controlled", "pii"})
    assert await audit_events(session) == before


@pytest.mark.parametrize("change", EC_LOWERS)
async def test_an_explicit_project_admin_may_lower_an_export_controlled_project(
    client: AsyncClient, session: AsyncSession, change: Body
) -> None:
    """§3.1: lowering, or removing any category or `export_controlled`, "needs an explicit
    project admin" (a `project_membership` with role admin)."""
    t, _ = await signed_in(client, "project_admin")
    await classify(session, t, *EC_START)

    response = await client.put(URL, json=body(*change))

    assert_classified(response, change[0], set(change[1]))
    assert await stored(session, t) == (change[0], set(change[1]))


@pytest.mark.parametrize("who", INHERITED_ADMINS)
async def test_an_inherited_admin_who_is_also_an_explicit_admin_may_remove_export_controlled(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    """§3.1: the explicit admin membership is what counts, whatever else the user holds."""
    t, user = await signed_in(client, who)
    await ProjectMembershipFactory.create_async(
        project=t.project, user=user, role=ProjectRole.ADMIN
    )
    await classify(session, t, *EC_START)

    response = await client.put(URL, json=body("internal", ["pii"]))

    assert_classified(response, "internal", {"pii"})
    assert await stored(session, t) == ("internal", {"pii"})


@pytest.mark.parametrize("who", INHERITED_ADMINS)
async def test_an_inherited_admin_with_a_member_role_still_gets_403_lowering(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    """§3.1: "an explicit project admin (a `project_membership` with role admin)"; a member row
    is not one."""
    t, user = await signed_in(client, who)
    await ProjectMembershipFactory.create_async(
        project=t.project, user=user, role=ProjectRole.MEMBER
    )
    await classify(session, t, *EC_START)

    response = await client.put(URL, json=body("confidential", ["pii"]))

    assert_forbidden(response)
    assert await stored(session, t) == ("confidential", {"export_controlled", "pii"})


@pytest.mark.parametrize(
    ("start", "change"),
    [
        pytest.param(
            (CONFIDENTIAL, ["export_controlled"]),
            ("confidential", ["export_controlled"]),
            id="already-held",
        ),
        pytest.param(
            (INTERNAL, ["export_controlled"]), (None, ["export_controlled"]), id="to-unclassified"
        ),
        pytest.param(
            (None, ["export_controlled"]), ("internal", ["export_controlled"]), id="to-internal"
        ),
    ],
)
@pytest.mark.parametrize("who", INHERITED_NON_SYSTEM)
async def test_an_inherited_admin_may_make_a_change_that_neither_raises_nor_lowers_there(
    client: AsyncClient, session: AsyncSession, who: str, start: Start, change: Body
) -> None:
    """DL-82: a change that neither raises nor lowers needs either action, and the raise is
    theirs; Internal ↔ unclassified is neither (unclassified ranks as Internal), not a lower."""
    t, _ = await signed_in(client, who)
    await classify(session, t, *start)

    response = await client.put(URL, json=body(*change))

    assert_classified(response, change[0], set(change[1]))
    assert await stored(session, t) == (change[0], set(change[1]))


@pytest.mark.parametrize("who", SEE_ONLY)
async def test_a_member_or_viewer_gets_403_raising_an_export_controlled_project(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t, _ = await signed_in(client, who)
    await classify(session, t, *EC_START)

    response = await client.put(URL, json=body("restricted", ["export_controlled", "pii"]))

    assert_forbidden(response)
    assert await stored(session, t) == ("confidential", {"export_controlled", "pii"})


# --- The project read's allowed_actions (wiring: the target from the stored categories) ---------


@pytest.mark.parametrize(
    ("who", "categories", "raise_listed", "lower_listed"),
    [
        ("org_admin", [], True, True),
        ("org_admin", ["export_controlled"], True, False),
        ("workspace_owner", ["pii", "export_controlled"], True, False),
        ("system_admin", ["export_controlled"], True, False),
        ("org_admin", ["pii"], True, True),
        ("project_admin", ["export_controlled"], True, True),
        ("project_member", ["export_controlled"], False, False),
        ("project_viewer", [], False, False),
    ],
)
async def test_the_project_reads_allowed_actions_follow_the_stored_categories(
    client: AsyncClient,
    session: AsyncSession,
    who: str,
    categories: list[str],
    raise_listed: bool,
    lower_listed: bool,
) -> None:
    """Build plan, "The classification actions": the project read's `allowed_actions` carries
    them, reflecting the export-controlled rule (S1-C13 row)."""
    t, _ = await signed_in(client, who)
    await classify(session, t, INTERNAL, categories)

    response = await client.get("/api/projects/PMT")

    assert response.status_code == 200
    actions = response.json()["allowed_actions"]
    assert ("project.raise_classification" in actions) is raise_listed
    assert ("project.lower_classification" in actions) is lower_listed
