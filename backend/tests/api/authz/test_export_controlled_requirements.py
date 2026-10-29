"""The export-control gate on the real endpoints (S2-C4; design-doc §3.1, "Export-controlled
projects (who sees content)"; §5, "The choke point", step 2; S2-plan, "Actions per row"):

- `GET /api/projects/{key}/requirements/{number}/activity` (`requirement.view`, content; its
  export-control rows were left to S2-C4): on an export-controlled project, 404 to inherited
  admins without an explicit membership (the same body as a missing project, naming nothing),
  200 to explicit members, live and archived;
- `GET /api/projects/{key}` (`project.view`, management: "the project's own record"): still 200
  to inherited admins, and its `allowed_actions` carry no content action (`requirement.view`) for
  them without an explicit membership (build plan, "API conventions": evaluated through
  `authorize()`).

Personas are relative to the export-controlled project "Payments" (PMT) of org "Bolt Foods"
(bolt-foods) in workspace "Acme Consulting" (tests/support/authz.py, `persona_user`).
"""

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import ProjectRole
from app.models.user import User
from tests.factories.org import OrganizationFactory
from tests.factories.project import ProjectFactory, ProjectMembershipFactory
from tests.factories.requirement import RequirementFactory
from tests.factories.workspace import WorkspaceFactory
from tests.support.authz import Tenancy, persona_user, sign_in_as

pytestmark = [pytest.mark.anyio, pytest.mark.security, pytest.mark.usefixtures("session")]

INHERITED_ADMINS = ["system_admin", "workspace_owner", "workspace_admin", "org_owner", "org_admin"]
EXPLICIT_MEMBERS = ["project_admin", "project_member", "project_viewer"]
ARCHIVED_AT = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
TITLE = "Refunds above the card limit"
EMPTY_FEED: dict[str, object] = {"items": [], "next_cursor": None}
HISTORY = "/api/projects/PMT/requirements/7/activity"


async def signed_in(client: AsyncClient, who: str) -> tuple[Tenancy, User]:
    workspace = await WorkspaceFactory.create_async(name="Acme Consulting", slug="acme")
    org = await OrganizationFactory.create_async(
        workspace=workspace, name="Bolt Foods", slug="bolt-foods"
    )
    project = await ProjectFactory.create_async(
        organization=org, key="PMT", name="Payments", restriction_categories=["export_controlled"]
    )
    t = Tenancy(workspace, org, project)
    await RequirementFactory.create_async(project=project, number=7, title=TITLE)
    user = await persona_user(t, who)
    await sign_in_as(client, user)
    return t, user


async def archive(session: AsyncSession, t: Tenancy) -> None:
    t.project.archived_at = ARCHIVED_AT
    await session.flush()


async def with_viewer_membership(t: Tenancy, user: User) -> None:
    await ProjectMembershipFactory.create_async(
        project=t.project, user=user, role=ProjectRole.VIEWER
    )


def assert_hidden(response: Response, missing: Response) -> None:
    """404 `not_found`, the same body as for a project that doesn't exist, naming nothing."""
    assert (response.status_code, response.json()["code"]) == (404, "not_found")
    assert response.json() == missing.json()
    for name in ("Bolt Foods", "bolt-foods", "Payments", "PMT", TITLE):
        assert name not in response.text


# --- A requirement's history (requirement.view, content) ---------------------------------------


@pytest.mark.parametrize("who", INHERITED_ADMINS)
async def test_a_requirements_history_is_404_to_inherited_admins_on_an_ec_project(
    client: AsyncClient, who: str
) -> None:
    await signed_in(client, who)

    response = await client.get(HISTORY)

    assert_hidden(response, await client.get("/api/projects/NOPE/requirements/7/activity"))


@pytest.mark.parametrize("who", INHERITED_ADMINS)
async def test_an_archived_ec_projects_requirement_history_is_404_to_inherited_admins(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t, _ = await signed_in(client, who)
    await archive(session, t)

    response = await client.get(HISTORY)

    assert_hidden(response, await client.get("/api/projects/NOPE/requirements/7/activity"))


@pytest.mark.parametrize("who", EXPLICIT_MEMBERS)
async def test_explicit_members_read_a_requirements_history_on_an_ec_project(
    client: AsyncClient, who: str
) -> None:
    await signed_in(client, who)

    response = await client.get(HISTORY)

    assert (response.status_code, response.json()) == (200, EMPTY_FEED)


@pytest.mark.parametrize("who", EXPLICIT_MEMBERS)
async def test_explicit_members_read_a_requirements_history_on_an_archived_ec_project(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t, _ = await signed_in(client, who)
    await archive(session, t)

    response = await client.get(HISTORY)

    assert (response.status_code, response.json()) == (200, EMPTY_FEED)


@pytest.mark.parametrize("who", INHERITED_ADMINS)
async def test_an_inherited_admin_with_an_explicit_membership_reads_the_history(
    client: AsyncClient, who: str
) -> None:
    t, user = await signed_in(client, who)
    await with_viewer_membership(t, user)

    response = await client.get(HISTORY)

    assert (response.status_code, response.json()) == (200, EMPTY_FEED)


# --- The project read (project.view, management) -----------------------------------------------

INHERITED_ON_AN_EC_PROJECT = [
    "project.archive",
    "project.raise_restriction",
    "project.unarchive",
    "project.update",
    "project.view",
    "project.view_access",
    "project_member.manage",
]


@pytest.mark.parametrize(
    ("who", "expected"),
    [
        ("system_admin", INHERITED_ON_AN_EC_PROJECT),
        ("workspace_owner", INHERITED_ON_AN_EC_PROJECT),
        ("workspace_admin", INHERITED_ON_AN_EC_PROJECT),
        ("org_owner", INHERITED_ON_AN_EC_PROJECT),
        ("org_admin", INHERITED_ON_AN_EC_PROJECT),
        (
            "project_admin",
            [
                "approval_request.cancel",
                "approval_request.create",
                "project.lower_restriction",
                "project.raise_restriction",
                "project.update",
                "project.view",
                "project.view_access",
                "project_member.manage",
                "requirement.approve_manually",
                "requirement.create",
                "requirement.delete",
                "requirement.lower_restriction",
                "requirement.raise_restriction",
                "requirement.reassign_reporter",
                "requirement.restore",
                "requirement.update",
                "requirement.view",
            ],
        ),
        (
            "project_member",
            [
                "project.view",
                "requirement.create",
                "requirement.raise_restriction",
                "requirement.update",
                "requirement.view",
            ],
        ),
        ("project_viewer", ["project.view", "requirement.view"]),
    ],
)
async def test_an_ec_projects_actions_carry_content_only_for_explicit_members(
    client: AsyncClient, who: str, expected: list[str]
) -> None:
    """§3.1: the project's own record is management (200 to inherited admins); content
    (`requirement.view`) needs an explicit membership; lowering needs an explicit project admin
    there (DL-82)."""
    t, _ = await signed_in(client, who)

    response = await client.get("/api/projects/PMT")

    assert response.status_code == 200
    body = response.json()
    assert (body["id"], body["key"], body["name"]) == (str(t.project.id), "PMT", "Payments")
    assert body["allowed_actions"] == expected


@pytest.mark.parametrize("who", ["system_admin", "workspace_admin", "org_admin"])
async def test_an_inherited_admin_with_a_viewer_membership_gets_content_actions_back(
    client: AsyncClient, who: str
) -> None:
    t, user = await signed_in(client, who)
    await with_viewer_membership(t, user)

    response = await client.get("/api/projects/PMT")

    assert response.status_code == 200
    assert response.json()["allowed_actions"] == [
        "approval_request.cancel",
        "approval_request.create",
        *INHERITED_ON_AN_EC_PROJECT,
        "requirement.approve_manually",
        "requirement.create",
        "requirement.delete",
        "requirement.raise_restriction",
        "requirement.reassign_reporter",
        "requirement.restore",
        "requirement.update",
        "requirement.view",
    ]


@pytest.mark.parametrize("who", ["system_admin", "workspace_admin", "org_admin"])
async def test_an_archived_ec_projects_actions_for_an_inherited_admin_carry_no_content(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t, _ = await signed_in(client, who)
    await archive(session, t)

    response = await client.get("/api/projects/PMT")

    assert response.status_code == 200
    assert response.json()["allowed_actions"] == [
        "project.unarchive",
        "project.view",
        "project.view_access",
    ]
