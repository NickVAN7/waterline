"""Authorization of the project endpoints (build plan, "The projects API", DL-76; the actions,
DL-77; design-doc §5, "Org roles", §4 "Visibility", §9 archiving, §11 "My work"):

- create and the key check (`project.create`): org members and up, workspace owners/admins,
  system admins; 403 for who sees the org another way (a project membership there), 404 for
  who doesn't; `first_admin_id` also needs `project.assign_first_admin` (403 for a plain org
  member), and naming anyone outside the org's members and the workspace's staff is a 404;
- the org's project list: the org's projects the caller can open (an org membership alone shows
  none; its 404 for who can't see the org comes from the built `org.view`, so it's not a spec
  test here);
- read (`project.view`), update (`project.update`), archive and unarchive: 2xx for who holds the
  action, 403 for who sees the project without it, 404 (the same as a missing project, naming
  nothing) for who doesn't see it; an archived project is still readable, and denies every
  mutation but unarchive (archiving it again included);
- module guidance: any signed-in user;
- My work's organizations section: each org the user can open a project in, with the projects
  they can open there, archived ones hidden (DL-330, DL-359);
- starring and unstarring (`project.favorite`, DL-303, DL-304): whoever sees the project, 204
  and idempotent, only the caller's own row, no audit event or activity entry; 403 on an
  archived project, 404 to who doesn't see it.

On every denial nothing is stored and no audit event is recorded. Personas are relative to
workspace "Acme Consulting", org "Bolt Foods" (bolt-foods), and project "Payments" (PMT)
(tests/support/authz.py, `tenancy`).
"""

import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import OrgRole, ProjectRole, ProjectStatus, WorkspaceRole
from app.models.audit_event import AuditEvent
from app.models.project import Project, ProjectFavorite
from app.models.user import User
from tests.factories.org import MembershipFactory, OrganizationFactory
from tests.factories.project import ProjectFactory, ProjectMembershipFactory
from tests.factories.user import UserFactory
from tests.factories.workspace import WorkspaceFactory, WorkspaceMembershipFactory
from tests.support.activity import activity
from tests.support.authz import Tenancy, persona_user, project_actions, sign_in_as, tenancy

pytestmark = [pytest.mark.anyio, pytest.mark.security, pytest.mark.usefixtures("session")]

INHERITED_ADMINS = ["system_admin", "workspace_owner", "workspace_admin", "org_owner", "org_admin"]
CREATORS = [*INHERITED_ADMINS, "org_member"]
# See the org only through a project membership on one of its projects.
PROJECT_LINKED = ["project_admin", "project_member", "project_viewer", "other_project_admin"]
ORG_UNSEEN = ["workspace_member", "other_org_owner", "other_workspace_owner", "nobody"]
PROJECT_ADMINS = [*INHERITED_ADMINS, "project_admin"]
PROJECT_UNSEEN = ["org_member", "other_project_admin", *ORG_UNSEEN]

ARCHIVED_AT = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
NEW_PROJECT = {"name": "Invoicing", "key": "INV", "type": "general"}


async def signed_in(client: AsyncClient, who: str) -> Tenancy:
    t = await tenancy()
    await sign_in_as(client, await persona_user(t, who))
    return t


async def archive(session: AsyncSession, t: Tenancy) -> None:
    t.project.archived_at = ARCHIVED_AT
    await session.flush()


async def stored_keys(session: AsyncSession, t: Tenancy) -> list[str]:
    return list(
        await session.scalars(
            select(Project.key).where(Project.organization_id == t.org.id).order_by(Project.key)
        )
    )


async def stored_project(session: AsyncSession, t: Tenancy) -> tuple[str, datetime | None]:
    row = (
        await session.execute(
            select(Project.name, Project.archived_at)
            .where(Project.id == t.project.id)
            .execution_options(populate_existing=True)
        )
    ).one()
    return (row.name, row.archived_at)


async def audit_actions(session: AsyncSession) -> list[str]:
    return list(await session.scalars(select(AuditEvent.action).order_by(AuditEvent.id)))


def assert_forbidden(response: Response) -> None:
    assert (response.status_code, response.json()["code"]) == (403, "forbidden")


def assert_hidden(response: Response, missing: Response) -> None:
    """404 `not_found`, the same body as for one that doesn't exist, naming nothing."""
    assert (response.status_code, response.json()["code"]) == (404, "not_found")
    assert response.json() == missing.json()
    for name in ("Bolt Foods", "bolt-foods", "Payments", "PMT"):
        assert name not in response.text


async def org_member(t: Tenancy, email: str) -> User:
    user = await UserFactory.create_async(email=email, name="Nia Okafor", is_system_admin=False)
    await MembershipFactory.create_async(organization=t.org, user=user, role=OrgRole.MEMBER)
    return user


# --- POST /api/orgs/{org_id}/projects (project.create) -----------------------------------------


@pytest.mark.parametrize("who", CREATORS)
async def test_org_members_and_the_admins_above_create_a_project(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t = await signed_in(client, who)

    response = await client.post(f"/api/orgs/{t.org.id}/projects", json=NEW_PROJECT)

    assert (response.status_code, response.json()["key"]) == (201, "INV")
    assert await stored_keys(session, t) == ["INV", "PMT"]


@pytest.mark.parametrize("who", PROJECT_LINKED)
async def test_a_project_only_link_to_the_org_may_not_create_a_project_there(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t = await signed_in(client, who)
    before = await stored_keys(session, t)

    response = await client.post(f"/api/orgs/{t.org.id}/projects", json=NEW_PROJECT)

    assert_forbidden(response)
    assert await stored_keys(session, t) == before
    assert await audit_actions(session) == []


@pytest.mark.parametrize("who", ORG_UNSEEN)
async def test_creating_a_project_in_an_org_the_user_cannot_see_is_404(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t = await signed_in(client, who)

    response = await client.post(f"/api/orgs/{t.org.id}/projects", json=NEW_PROJECT)

    missing = await client.post(f"/api/orgs/{uuid.uuid4()}/projects", json=NEW_PROJECT)
    assert_hidden(response, missing)
    assert await stored_keys(session, t) == ["PMT"]
    assert await audit_actions(session) == []


# --- first_admin_id (project.assign_first_admin) ------------------------------------------------


@pytest.mark.parametrize("who", INHERITED_ADMINS)
async def test_org_admins_and_above_may_name_an_org_member_as_first_admin(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t = await signed_in(client, who)
    nia = await org_member(t, "nia@boltfoods.example")

    response = await client.post(
        f"/api/orgs/{t.org.id}/projects", json={**NEW_PROJECT, "first_admin_id": str(nia.id)}
    )

    assert (response.status_code, response.json()["key"]) == (201, "INV")
    assert await stored_keys(session, t) == ["INV", "PMT"]


async def test_an_org_admin_may_name_workspace_staff_as_first_admin(
    client: AsyncClient, session: AsyncSession
) -> None:
    t = await signed_in(client, "org_admin")
    staff = await UserFactory.create_async(is_system_admin=False)
    await WorkspaceMembershipFactory.create_async(
        workspace=t.workspace, user=staff, role=WorkspaceRole.MEMBER
    )

    response = await client.post(
        f"/api/orgs/{t.org.id}/projects", json={**NEW_PROJECT, "first_admin_id": str(staff.id)}
    )

    assert response.status_code == 201
    assert await stored_keys(session, t) == ["INV", "PMT"]


async def test_a_plain_org_member_may_not_name_a_first_admin(
    client: AsyncClient, session: AsyncSession
) -> None:
    t = await signed_in(client, "org_member")
    nia = await org_member(t, "nia@boltfoods.example")

    response = await client.post(
        f"/api/orgs/{t.org.id}/projects", json={**NEW_PROJECT, "first_admin_id": str(nia.id)}
    )

    assert_forbidden(response)
    assert await stored_keys(session, t) == ["PMT"]
    assert await audit_actions(session) == []


async def _no_memberships(_t: Tenancy) -> User:
    return await UserFactory.create_async(
        email="zed@elsewhere.example", name="Zed Quill", is_system_admin=False
    )


async def _project_only(t: Tenancy) -> User:
    """A project membership in the org is neither an org membership nor staff."""
    user = await _no_memberships(t)
    await ProjectMembershipFactory.create_async(
        project=t.project, user=user, role=ProjectRole.ADMIN
    )
    return user


async def _other_workspace_staff(t: Tenancy) -> User:
    user = await _no_memberships(t)
    other = await WorkspaceFactory.create_async(name="Delta Partners", slug="delta")
    await WorkspaceMembershipFactory.create_async(
        workspace=other, user=user, role=WorkspaceRole.ADMIN
    )
    return user


async def _other_org_member(t: Tenancy) -> User:
    user = await _no_memberships(t)
    other = await OrganizationFactory.create_async(
        workspace=t.workspace, name="Cove Retail", slug="cove-retail"
    )
    await MembershipFactory.create_async(organization=other, user=user, role=OrgRole.OWNER)
    return user


@pytest.mark.parametrize(
    "outsider", [_no_memberships, _project_only, _other_workspace_staff, _other_org_member]
)
async def test_naming_a_first_admin_outside_the_org_and_staff_is_404(
    client: AsyncClient,
    session: AsyncSession,
    outsider: Callable[[Tenancy], Awaitable[User]],
) -> None:
    """design-doc §5, "Org roles": anyone else is a 404, as in the member picker."""
    t = await signed_in(client, "org_admin")
    user = await outsider(t)

    response = await client.post(
        f"/api/orgs/{t.org.id}/projects", json={**NEW_PROJECT, "first_admin_id": str(user.id)}
    )

    assert (response.status_code, response.json()["code"]) == (404, "not_found")
    assert "zed@elsewhere.example" not in response.text
    assert "Zed Quill" not in response.text
    assert await stored_keys(session, t) == ["PMT"]
    assert await audit_actions(session) == []


async def test_naming_a_first_admin_who_does_not_exist_is_404(
    client: AsyncClient, session: AsyncSession
) -> None:
    t = await signed_in(client, "org_admin")

    response = await client.post(
        f"/api/orgs/{t.org.id}/projects",
        json={**NEW_PROJECT, "first_admin_id": str(uuid.uuid4())},
    )

    assert (response.status_code, response.json()["code"]) == (404, "not_found")
    assert await stored_keys(session, t) == ["PMT"]


# --- GET /api/orgs/{org_id}/project-key-availability (project.create) ---------------------------


@pytest.mark.parametrize("who", CREATORS)
async def test_whoever_may_create_a_project_checks_a_key(client: AsyncClient, who: str) -> None:
    t = await signed_in(client, who)

    response = await client.get(f"/api/orgs/{t.org.id}/project-key-availability?key=INV")

    assert response.status_code == 200
    assert response.json() == {"available": True, "problem": None}


@pytest.mark.parametrize("who", PROJECT_LINKED)
async def test_a_project_only_link_may_not_check_a_key(client: AsyncClient, who: str) -> None:
    t = await signed_in(client, who)

    response = await client.get(f"/api/orgs/{t.org.id}/project-key-availability?key=INV")

    assert_forbidden(response)


@pytest.mark.parametrize("who", ORG_UNSEEN)
async def test_a_key_check_is_404_to_whoever_cannot_see_the_org(
    client: AsyncClient, who: str
) -> None:
    t = await signed_in(client, who)

    response = await client.get(f"/api/orgs/{t.org.id}/project-key-availability?key=INV")

    missing = await client.get(f"/api/orgs/{uuid.uuid4()}/project-key-availability?key=INV")
    assert_hidden(response, missing)


# --- GET /api/orgs/{org_id}/projects (org.view; scoped to the projects the caller can open) ---


@pytest.mark.parametrize(
    ("who", "expected"),
    [
        ("system_admin", ["OPS", "PMT"]),
        ("workspace_owner", ["OPS", "PMT"]),
        ("workspace_admin", ["OPS", "PMT"]),
        ("org_owner", ["OPS", "PMT"]),
        ("org_admin", ["OPS", "PMT"]),
        # An org membership alone (role member) shows the org, not its projects (§4).
        ("org_member", []),
        ("project_admin", ["PMT"]),
        ("project_member", ["PMT"]),
        ("project_viewer", ["PMT"]),
        # Their own project in the org ("Ledger", made with the persona), not the others.
        ("other_project_admin", ["LDG"]),
    ],
)
async def test_the_org_list_holds_only_the_projects_the_caller_can_open(
    client: AsyncClient, who: str, expected: list[str]
) -> None:
    t = await signed_in(client, who)
    await ProjectFactory.create_async(organization=t.org, key="OPS", name="Operations")

    response = await client.get(f"/api/orgs/{t.org.id}/projects")

    assert response.status_code == 200
    body = response.json()
    assert ([item["key"] for item in body["items"]], body["total"]) == (expected, len(expected))


# --- GET /api/projects/{key} (project.view) -----------------------------------------------------


@pytest.mark.parametrize(
    ("who", "expected"),
    [
        ("system_admin", project_actions(inherited=True)),
        ("workspace_owner", project_actions(inherited=True)),
        ("workspace_admin", project_actions(inherited=True)),
        ("org_owner", project_actions(inherited=True)),
        ("org_admin", project_actions(inherited=True)),
        ("project_admin", project_actions(ProjectRole.ADMIN)),
        ("project_member", project_actions(ProjectRole.MEMBER)),
        ("project_viewer", project_actions(ProjectRole.VIEWER)),
    ],
)
async def test_the_project_is_returned_with_the_callers_actions(
    client: AsyncClient, who: str, expected: list[str]
) -> None:
    t = await signed_in(client, who)

    response = await client.get("/api/projects/PMT")

    assert response.status_code == 200
    body = response.json()
    assert (body["id"], body["key"], body["name"], body["archived"]) == (
        str(t.project.id),
        "PMT",
        "Payments",
        False,
    )
    assert body["allowed_actions"] == expected


@pytest.mark.parametrize("who", PROJECT_UNSEEN)
async def test_the_project_is_404_to_whoever_cannot_see_it(client: AsyncClient, who: str) -> None:
    await signed_in(client, who)

    response = await client.get("/api/projects/PMT")

    assert_hidden(response, await client.get("/api/projects/ZZZ"))


@pytest.mark.parametrize(
    ("who", "expected"),
    [
        (
            "system_admin",
            ["project.unarchive", "project.view", "project.view_access", "requirement.view"],
        ),
        (
            "workspace_admin",
            ["project.unarchive", "project.view", "project.view_access", "requirement.view"],
        ),
        (
            "org_admin",
            ["project.unarchive", "project.view", "project.view_access", "requirement.view"],
        ),
        ("project_admin", ["project.view", "project.view_access", "requirement.view"]),
        ("project_viewer", ["project.view", "requirement.view"]),
    ],
)
async def test_an_archived_project_is_still_readable_with_only_unarchive_left(
    client: AsyncClient, session: AsyncSession, who: str, expected: list[str]
) -> None:
    """design-doc §9: archived is read-only, still browsable."""
    t = await signed_in(client, who)
    await archive(session, t)

    response = await client.get("/api/projects/PMT")

    assert response.status_code == 200
    assert (response.json()["archived"], response.json()["allowed_actions"]) == (True, expected)


async def test_an_archived_project_is_still_404_to_whoever_cannot_see_it(
    client: AsyncClient, session: AsyncSession
) -> None:
    t = await signed_in(client, "org_member")
    await archive(session, t)

    response = await client.get("/api/projects/PMT")

    assert_hidden(response, await client.get("/api/projects/ZZZ"))


# --- PATCH /api/projects/{key} (project.update) -------------------------------------------------


@pytest.mark.parametrize("who", PROJECT_ADMINS)
async def test_project_admins_inherited_included_update_the_project(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t = await signed_in(client, who)

    response = await client.patch("/api/projects/PMT", json={"name": "Payments Hub"})

    assert (response.status_code, response.json()["name"]) == (200, "Payments Hub")
    assert await stored_project(session, t) == ("Payments Hub", None)


@pytest.mark.parametrize("who", ["project_member", "project_viewer"])
async def test_project_members_and_viewers_may_not_update_the_project(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t = await signed_in(client, who)

    response = await client.patch("/api/projects/PMT", json={"name": "Payments Hub"})

    assert_forbidden(response)
    assert await stored_project(session, t) == ("Payments", None)
    assert await audit_actions(session) == []


@pytest.mark.parametrize("who", PROJECT_UNSEEN)
async def test_updating_a_project_the_user_cannot_see_is_404_and_changes_nothing(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t = await signed_in(client, who)

    response = await client.patch("/api/projects/PMT", json={"name": "Payments Hub"})

    missing = await client.patch("/api/projects/ZZZ", json={"name": "Payments Hub"})
    assert_hidden(response, missing)
    assert await stored_project(session, t) == ("Payments", None)
    assert await audit_actions(session) == []


@pytest.mark.parametrize("who", PROJECT_ADMINS)
async def test_an_archived_project_cannot_be_updated_by_anyone(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    """System admins included (design-doc §5, step 1)."""
    t = await signed_in(client, who)
    await archive(session, t)

    response = await client.patch("/api/projects/PMT", json={"name": "Payments Hub"})

    assert_forbidden(response)
    assert await stored_project(session, t) == ("Payments", ARCHIVED_AT)
    assert await audit_actions(session) == []


# --- POST /api/projects/{key}/archive (project.archive) -----------------------------------------


@pytest.mark.parametrize("who", INHERITED_ADMINS)
async def test_org_admins_and_above_archive_the_project(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t = await signed_in(client, who)

    response = await client.post("/api/projects/PMT/archive")

    assert response.status_code == 204
    _name, archived_at = await stored_project(session, t)
    assert archived_at is not None


@pytest.mark.parametrize("who", ["project_admin", "project_member", "project_viewer"])
async def test_project_roles_may_not_archive_the_project(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    """Archiving is an org admin's (design-doc §5, "Org roles"), not a project admin's."""
    t = await signed_in(client, who)

    response = await client.post("/api/projects/PMT/archive")

    assert_forbidden(response)
    assert await stored_project(session, t) == ("Payments", None)
    assert await audit_actions(session) == []


@pytest.mark.parametrize("who", PROJECT_UNSEEN)
async def test_archiving_a_project_the_user_cannot_see_is_404_and_changes_nothing(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t = await signed_in(client, who)

    response = await client.post("/api/projects/PMT/archive")

    assert_hidden(response, await client.post("/api/projects/ZZZ/archive"))
    assert await stored_project(session, t) == ("Payments", None)
    assert await audit_actions(session) == []


@pytest.mark.parametrize("who", INHERITED_ADMINS)
async def test_archiving_an_archived_project_is_denied(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    """Build plan, "The projects API": denied with the other mutations on it (403)."""
    t = await signed_in(client, who)
    await archive(session, t)

    response = await client.post("/api/projects/PMT/archive")

    assert_forbidden(response)
    assert await stored_project(session, t) == ("Payments", ARCHIVED_AT)
    assert await audit_actions(session) == []


# --- POST /api/projects/{key}/unarchive (project.unarchive, archive-exempt) ---------------------


@pytest.mark.parametrize("who", INHERITED_ADMINS)
async def test_org_admins_and_above_unarchive_an_archived_project(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t = await signed_in(client, who)
    await archive(session, t)

    response = await client.post("/api/projects/PMT/unarchive")

    assert response.status_code == 204
    assert await stored_project(session, t) == ("Payments", None)


@pytest.mark.parametrize("who", INHERITED_ADMINS)
async def test_unarchiving_a_project_that_is_not_archived_is_allowed(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    """Build plan: already unarchived changes nothing; 204."""
    t = await signed_in(client, who)

    response = await client.post("/api/projects/PMT/unarchive")

    assert response.status_code == 204
    assert await stored_project(session, t) == ("Payments", None)


@pytest.mark.parametrize("who", ["project_admin", "project_member", "project_viewer"])
async def test_project_roles_may_not_unarchive_the_project(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t = await signed_in(client, who)
    await archive(session, t)

    response = await client.post("/api/projects/PMT/unarchive")

    assert_forbidden(response)
    assert await stored_project(session, t) == ("Payments", ARCHIVED_AT)
    assert await audit_actions(session) == []


@pytest.mark.parametrize("who", PROJECT_UNSEEN)
async def test_unarchiving_a_project_the_user_cannot_see_is_404_and_changes_nothing(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t = await signed_in(client, who)
    await archive(session, t)

    response = await client.post("/api/projects/PMT/unarchive")

    assert_hidden(response, await client.post("/api/projects/ZZZ/unarchive"))
    assert await stored_project(session, t) == ("Payments", ARCHIVED_AT)
    assert await audit_actions(session) == []


# --- GET /api/module-guidance (signed in) -------------------------------------------------------


async def test_any_signed_in_user_gets_the_module_guidance(client: AsyncClient) -> None:
    """A user with no memberships at all, too: the guidance is static (DL-76)."""
    await signed_in(client, "nobody")

    response = await client.get("/api/module-guidance")

    assert response.status_code == 200
    assert sorted(note["module"] for note in response.json()["modules"]) == [
        "budget",
        "cutover",
        "data_migration",
        "github",
        "raid",
        "sprints",
        "status_reports",
    ]


# --- My work's organizations section (design-doc §11 from S3-C0f; DL-329, DL-330, DL-349, DL-359,
# DL-368). One item per org the caller can open a project in, by org name: its first 5 open
# projects (Active, Planning, On hold, each by name) with `total`, the first 5 hidden ones
# (Completed, Cancelled, each by name, then the archived by name alone) with `hidden_total`, and
# `listed_total` (all but the archived). The projects are those the caller can open (§5, §3.1),
# archived included.


async def my_work_layout(session: AsyncSession, t: Tenancy) -> None:
    """Besides PMT: OPS in the same org, XCT export-controlled in it, ARC archived in it, DUN in
    another org of the workspace, ECH in another workspace. Every one is Planning."""
    await ProjectFactory.create_async(organization=t.org, key="OPS", name="Operations")
    await ProjectFactory.create_async(
        organization=t.org,
        key="XCT",
        name="Exports",
        restriction_categories=["export_controlled"],
    )
    await ProjectFactory.create_async(
        organization=t.org, key="ARC", name="Archive", archived_at=ARCHIVED_AT
    )
    dune = await OrganizationFactory.create_async(
        workspace=t.workspace, name="Dune Labs", slug="dune-labs"
    )
    await ProjectFactory.create_async(organization=dune, key="DUN", name="Dunes")
    echo = await WorkspaceFactory.create_async(name="Echo Group", slug="echo")
    echo_org = await OrganizationFactory.create_async(
        workspace=echo, name="Echo Org", slug="echo-org"
    )
    await ProjectFactory.create_async(organization=echo_org, key="ECH", name="Echoes")
    await session.flush()


# (slug, name, open keys, total, hidden keys, hidden_total, listed_total)
OrgRow = tuple[str, str, list[str], int, list[str], int, int]

BOLT_ALL: OrgRow = ("bolt-foods", "Bolt Foods", ["XCT", "OPS", "PMT"], 3, ["ARC"], 1, 3)
BOLT_PMT: OrgRow = ("bolt-foods", "Bolt Foods", ["PMT"], 1, [], 0, 1)
BOLT_LDG: OrgRow = ("bolt-foods", "Bolt Foods", ["LDG"], 1, [], 0, 1)
DUNE: OrgRow = ("dune-labs", "Dune Labs", ["DUN"], 1, [], 0, 1)
ECHO: OrgRow = ("echo-org", "Echo Org", ["ECH"], 1, [], 0, 1)

# Inherited admins keep export-controlled projects in lists (management, §3.1); an org
# membership alone opens none of the org's projects (§5, "Org roles").
MY_ORGS: list[tuple[str, list[OrgRow]]] = [
    ("system_admin", [BOLT_ALL, DUNE, ECHO]),
    ("workspace_owner", [BOLT_ALL, DUNE]),
    ("workspace_admin", [BOLT_ALL, DUNE]),
    ("org_owner", [BOLT_ALL]),
    ("org_admin", [BOLT_ALL]),
    ("org_member", []),
    ("project_admin", [BOLT_PMT]),
    ("project_member", [BOLT_PMT]),
    ("project_viewer", [BOLT_PMT]),
    ("other_project_admin", [BOLT_LDG]),
    ("workspace_member", []),
    ("other_org_owner", []),
    ("other_workspace_owner", []),
    ("nobody", []),
]


def org_rows(section: dict[str, Any]) -> list[OrgRow]:
    return [
        (
            org["slug"],
            org["name"],
            [p["key"] for p in org["projects"]],
            org["total"],
            [p["key"] for p in org["hidden"]],
            org["hidden_total"],
            org["listed_total"],
        )
        for org in section["items"]
    ]


@pytest.mark.parametrize(("who", "expected"), MY_ORGS)
async def test_my_work_lists_each_org_with_the_projects_the_user_can_open(
    client: AsyncClient, session: AsyncSession, who: str, expected: list[OrgRow]
) -> None:
    t = await signed_in(client, who)
    await my_work_layout(session, t)

    response = await client.get("/api/me/work")

    assert response.status_code == 200
    section = response.json()["sections"]["organizations"]
    assert (section["available"], org_rows(section), section["total"]) == (
        True,
        expected,
        len(expected),
    )


async def test_my_work_lists_an_archived_project_the_user_is_a_member_of_as_hidden(
    client: AsyncClient, session: AsyncSession
) -> None:
    """DL-330: archived projects come onto My work's org lists, behind the toggle, with no star
    (starring is a mutation); the org's list doesn't show them, so `listed_total` leaves it out."""
    t = await signed_in(client, "project_admin")
    await archive(session, t)

    response = await client.get("/api/me/work")

    assert response.status_code == 200
    section = response.json()["sections"]["organizations"]
    assert org_rows(section) == [("bolt-foods", "Bolt Foods", [], 0, ["PMT"], 1, 0)]
    row = section["items"][0]["hidden"][0]
    assert (row["archived"], "project.favorite" in row["allowed_actions"]) == (True, False)


async def test_my_work_shows_a_favorite_in_its_orgs_section_too(
    client: AsyncClient, session: AsyncSession
) -> None:
    """DL-332: favorites also appear in their org's section, starred; the user's other project
    there is not."""
    t = await tenancy()
    user = await persona_user(t, "project_viewer")
    ops = await ProjectFactory.create_async(organization=t.org, key="OPS", name="Operations")
    await ProjectMembershipFactory.create_async(project=ops, user=user, role=ProjectRole.VIEWER)
    await sign_in_as(client, user)
    await star(session, user, t.project)

    response = await client.get("/api/me/work")

    assert response.status_code == 200
    projects = response.json()["sections"]["organizations"]["items"][0]["projects"]
    assert [(p["key"], p["is_favorite"], p["archived"]) for p in projects] == [
        ("OPS", False, False),
        ("PMT", True, False),
    ]


async def ordering_layout(t: Tenancy) -> None:
    """Bolt Foods gets 5 more open projects (6 with PMT "Payments", Planning) and 6 hidden ones,
    each list one past the 5 shown, the first 5 of each crossing every status; another org,
    "Alpine Dairy", created after it but first by name, gets one."""
    for status, projects in [
        ("active", [("WIL", "Willow"), ("ASP", "Aspen")]),
        ("planning", [("BIR", "Birch")]),
        ("on_hold", [("YEW", "Yew"), ("ALD", "Alder")]),
        ("completed", [("ROW", "Rowan"), ("ASH", "Ash")]),
        ("cancelled", [("BEE", "Beech")]),
    ]:
        for key, name in projects:
            await ProjectFactory.create_async(
                organization=t.org, key=key, name=name, status=ProjectStatus(status)
            )
    # Archived, whatever their status: by status, Teak would lead them and Ebony sit among the
    # completed.
    for key, name, status in [
        ("TEA", "Teak", "active"),
        ("EBO", "Ebony", "completed"),
        ("ACA", "Acacia", "on_hold"),
    ]:
        await ProjectFactory.create_async(
            organization=t.org,
            key=key,
            name=name,
            status=ProjectStatus(status),
            archived_at=ARCHIVED_AT,
        )
    alpine = await OrganizationFactory.create_async(
        workspace=t.workspace, name="Alpine Dairy", slug="the-dairy"
    )
    await ProjectFactory.create_async(organization=alpine, key="MLK", name="Milk")


async def test_my_work_orders_orgs_by_name_and_projects_by_status_then_name(
    client: AsyncClient, session: AsyncSession
) -> None:
    """DL-330, DL-359, DL-368: each org's first 5 open and first 5 hidden projects, in order,
    with their totals and the count its org list shows (all but the archived)."""
    t = await signed_in(client, "workspace_admin")
    await ordering_layout(t)
    await session.flush()

    response = await client.get("/api/me/work")

    assert response.status_code == 200
    section = response.json()["sections"]["organizations"]
    assert (section["total"], org_rows(section)) == (
        2,
        [
            ("the-dairy", "Alpine Dairy", ["MLK"], 1, [], 0, 1),
            (
                "bolt-foods",
                "Bolt Foods",
                ["ASP", "WIL", "BIR", "PMT", "ALD"],
                6,
                ["ASH", "ROW", "BEE", "ACA", "EBO"],
                6,
                9,
            ),
        ],
    )
    bolt = section["items"][1]
    assert bolt["id"] == str(t.org.id)
    assert [p["archived"] for p in bolt["hidden"]] == [False] * 3 + [True] * 2


# --- PUT / DELETE /api/projects/{key}/favorite (project.favorite; DL-303, DL-304) ---------------
# Whoever sees the project stars and unstars it for themself, 204 and idempotent; an archived
# project denies both (403 to who sees it); 404 naming nothing to who doesn't. The star is the
# caller's own `project_favorite` row; no audit event or activity entry is recorded.

SEES_THE_PROJECT = [*PROJECT_ADMINS, "project_member", "project_viewer"]


async def favorites(session: AsyncSession) -> set[tuple[uuid.UUID, uuid.UUID]]:
    """Every `project_favorite` row, re-read: `(user_id, project_id)`."""
    rows = await session.execute(select(ProjectFavorite.user_id, ProjectFavorite.project_id))
    return {(row.user_id, row.project_id) for row in rows.all()}


async def star(session: AsyncSession, user: User, project: Project) -> None:
    session.add(ProjectFavorite(user_id=user.id, project_id=project.id))
    await session.flush()


async def favorite_signed_in(client: AsyncClient, who: str) -> tuple[Tenancy, User]:
    t = await tenancy()
    user = await persona_user(t, who)
    await sign_in_as(client, user)
    return t, user


@pytest.mark.parametrize("who", SEES_THE_PROJECT)
async def test_whoever_sees_the_project_stars_it(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t, user = await favorite_signed_in(client, who)

    response = await client.put("/api/projects/PMT/favorite")

    assert response.status_code == 204
    assert await favorites(session) == {(user.id, t.project.id)}


@pytest.mark.parametrize("who", SEES_THE_PROJECT)
async def test_whoever_sees_the_project_unstars_it(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t, user = await favorite_signed_in(client, who)
    await star(session, user, t.project)

    response = await client.delete("/api/projects/PMT/favorite")

    assert response.status_code == 204
    assert await favorites(session) == set()


@pytest.mark.parametrize("who", INHERITED_ADMINS)
async def test_inherited_admins_star_an_export_controlled_project(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    """A management action passes the export-control gate (DL-303; design-doc §3.1)."""
    t, user = await favorite_signed_in(client, who)
    t.project.restriction_categories = ["export_controlled"]
    await session.flush()

    response = await client.put("/api/projects/PMT/favorite")

    assert response.status_code == 204
    assert await favorites(session) == {(user.id, t.project.id)}


async def test_starring_a_favorite_again_leaves_one_row(
    client: AsyncClient, session: AsyncSession
) -> None:
    """DL-304: idempotent; starring a favorite changes nothing."""
    t, user = await favorite_signed_in(client, "project_viewer")

    first = await client.put("/api/projects/PMT/favorite")
    second = await client.put("/api/projects/PMT/favorite")

    assert (first.status_code, second.status_code) == (204, 204)
    assert await favorites(session) == {(user.id, t.project.id)}


async def test_unstarring_a_project_that_is_not_a_favorite_is_204(
    client: AsyncClient, session: AsyncSession
) -> None:
    """DL-304: idempotent; unstarring one that isn't a favorite changes nothing."""
    await favorite_signed_in(client, "project_member")

    response = await client.delete("/api/projects/PMT/favorite")

    assert response.status_code == 204
    assert await favorites(session) == set()


async def test_starring_leaves_another_users_star_alone(
    client: AsyncClient, session: AsyncSession
) -> None:
    t, user = await favorite_signed_in(client, "project_member")
    other = await persona_user(t, "project_viewer")
    await star(session, other, t.project)

    response = await client.put("/api/projects/PMT/favorite")

    assert response.status_code == 204
    assert await favorites(session) == {(other.id, t.project.id), (user.id, t.project.id)}


async def test_unstarring_removes_only_the_callers_star(
    client: AsyncClient, session: AsyncSession
) -> None:
    t, user = await favorite_signed_in(client, "project_member")
    other = await persona_user(t, "project_viewer")
    await star(session, other, t.project)
    await star(session, user, t.project)

    response = await client.delete("/api/projects/PMT/favorite")

    assert response.status_code == 204
    assert await favorites(session) == {(other.id, t.project.id)}


async def test_unstarring_one_project_leaves_the_callers_other_favorites(
    client: AsyncClient, session: AsyncSession
) -> None:
    t, user = await favorite_signed_in(client, "org_admin")
    ledger = await ProjectFactory.create_async(organization=t.org, key="LDG", name="Ledger")
    await star(session, user, ledger)
    await star(session, user, t.project)

    response = await client.delete("/api/projects/PMT/favorite")

    assert response.status_code == 204
    assert await favorites(session) == {(user.id, ledger.id)}


@pytest.mark.parametrize("method", ["PUT", "DELETE"])
async def test_a_favorite_change_records_no_audit_event_or_activity(
    client: AsyncClient, session: AsyncSession, method: str
) -> None:
    """DL-304: a favorite is the user's own view, not a change to the project."""
    await favorite_signed_in(client, "project_admin")

    response = await client.request(method, "/api/projects/PMT/favorite")

    assert response.status_code == 204
    assert await audit_actions(session) == []
    assert await activity(session) == []


@pytest.mark.parametrize("who", PROJECT_UNSEEN)
async def test_starring_a_project_the_user_cannot_see_is_404_and_stores_nothing(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    await favorite_signed_in(client, who)

    response = await client.put("/api/projects/PMT/favorite")

    assert_hidden(response, await client.put("/api/projects/ZZZ/favorite"))
    assert await favorites(session) == set()
    assert await audit_actions(session) == []


@pytest.mark.parametrize("who", PROJECT_UNSEEN)
async def test_unstarring_a_project_the_user_cannot_see_is_404_and_keeps_the_star(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    """A favorite of a project the user can no longer open stays (schema-doc
    `project_favorite`)."""
    t, user = await favorite_signed_in(client, who)
    await star(session, user, t.project)

    response = await client.delete("/api/projects/PMT/favorite")

    assert_hidden(response, await client.delete("/api/projects/ZZZ/favorite"))
    assert await favorites(session) == {(user.id, t.project.id)}


@pytest.mark.parametrize("who", SEES_THE_PROJECT)
async def test_an_archived_project_cannot_be_starred(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    """DL-303: a mutation, denied on an archived project to everyone, system admins included."""
    t, _user = await favorite_signed_in(client, who)
    await archive(session, t)

    response = await client.put("/api/projects/PMT/favorite")

    assert_forbidden(response)
    assert await favorites(session) == set()


@pytest.mark.parametrize("who", SEES_THE_PROJECT)
async def test_an_archived_project_cannot_be_unstarred(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    """DL-303; the star of an archived project stays (schema-doc `project_favorite`)."""
    t, user = await favorite_signed_in(client, who)
    await star(session, user, t.project)
    await archive(session, t)

    response = await client.delete("/api/projects/PMT/favorite")

    assert_forbidden(response)
    assert await favorites(session) == {(user.id, t.project.id)}
