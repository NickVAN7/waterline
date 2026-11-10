"""Authorization wiring of S2-C6's requirement endpoints (build plan, S2-C6; S2-plan, "Actions per
row"; design-doc §5, "Requirement status" (DL-148), "Requirement approval by hand" (DL-161,
DL-212); §3.1, "Who sets it" and export-controlled projects; DL-211):

- `PATCH /api/projects/{key}/requirements/{number}` (`requirement.update`): 404, naming nothing,
  for who can't see the project; 403 for a project viewer; a member's status change (not to
  `approved`) is stored. `status` `approved`: 403 to a member (no
  `requirement.approve_manually`), 422 `validation_error` of type `use_approve` on `status` to a
  project admin, inherited included. `reporter_id`: 403 to a member (no
  `requirement.reassign_reporter`); a project admin's reassignment to a project member is stored;
- `PUT /api/projects/{key}/requirements/{number}/restriction`: a member's raise is stored; a
  member's lower is 403; a project admin's (inherited included) lower is stored; a viewer is
  403; 404 for who can't see the project, and for an inherited admin on an export-controlled
  project (content, §3.1);
- the requirement read's `allowed_actions` carry `requirement.approve_manually` for a project
  admin and not for a project member (DL-212).

On every denial the requirement is unchanged. Field validation (`below_project`, `not_member`,
`account_inactive`, revisions, 409) is the main session's. Personas are relative to workspace
"Acme Consulting", org "Bolt Foods" (bolt-foods), and project "Payments" (PMT)
(tests/support/authz.py, `persona_user`).
"""

from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import ProjectRole, RequirementStatus, RestrictionLevel
from app.models.requirement import Requirement
from app.models.user import User
from tests.factories.org import OrganizationFactory
from tests.factories.project import ProjectFactory, ProjectMembershipFactory
from tests.factories.requirement import RequirementFactory, RequirementRevisionFactory
from tests.factories.user import UserFactory
from tests.factories.workspace import WorkspaceFactory
from tests.support.authz import Tenancy, persona_user, sign_in_as

pytestmark = [pytest.mark.anyio, pytest.mark.security, pytest.mark.usefixtures("session")]

INHERITED_ADMINS = ["system_admin", "workspace_owner", "workspace_admin", "org_owner", "org_admin"]
PROJECT_ADMINS = [*INHERITED_ADMINS, "project_admin"]
PROJECT_UNSEEN = [
    "org_member",
    "other_project_admin",
    "workspace_member",
    "other_org_owner",
    "other_workspace_owner",
    "nobody",
]

TITLE = "Refunds above the card limit"
URL = "/api/projects/PMT/requirements/7"
MISSING_URL = "/api/projects/NOPE/requirements/7"
RESTRICTION_URL = "/api/projects/PMT/requirements/7/restriction"
MISSING_RESTRICTION_URL = "/api/projects/NOPE/requirements/7/restriction"

RAISE: dict[str, object] = {
    "level": "confidential",
    "categories": ["pii"],
}  # from none, no categories
LOWER: dict[str, object] = {"level": "confidential", "categories": []}  # from confidential with pii


async def signed_in(
    client: AsyncClient,
    who: str,
    *,
    export_controlled: bool = False,
    level: RestrictionLevel | None = None,
    categories: list[str] | None = None,
) -> tuple[Tenancy, Requirement]:
    """`who` signed in, relative to "Payments" (PMT, no restriction of its own), which holds
    RQ-7 ("Refunds above the card limit"), a draft at revision 1 with the given restriction."""
    workspace = await WorkspaceFactory.create_async(name="Acme Consulting", slug="acme")
    org = await OrganizationFactory.create_async(
        workspace=workspace, name="Bolt Foods", slug="bolt-foods"
    )
    project = await ProjectFactory.create_async(
        organization=org,
        key="PMT",
        name="Payments",
        restriction_level=None,
        restriction_categories=["export_controlled"] if export_controlled else [],
    )
    t = Tenancy(workspace, org, project)
    requirement = await RequirementFactory.create_async(
        project=project,
        number=7,
        title=TITLE,
        status=RequirementStatus.DRAFT,
        restriction_level=level,
        restriction_categories=categories or [],
    )
    revision = await RequirementRevisionFactory.create_async(
        requirement=requirement, revision_number=1, title=TITLE
    )
    requirement.current_revision_id = revision.id
    await sign_in_as(client, await persona_user(t, who))
    return t, requirement


async def stored(session: AsyncSession, requirement: Requirement) -> dict[str, Any]:
    """RQ-7's authorization-relevant fields, re-read from the database."""
    row = (
        await session.execute(
            select(
                Requirement.status,
                Requirement.reporter_id,
                Requirement.restriction_level,
                Requirement.restriction_categories,
            ).where(Requirement.id == requirement.id)
        )
    ).one()
    return {
        "status": row[0],
        "reporter_id": row[1],
        "level": row[2],
        "categories": sorted(row[3]),
    }


async def project_member(t: Tenancy) -> User:
    """Ivy Moss, an explicit member (role member) of PMT."""
    person = await UserFactory.create_async(
        email="ivy@bolt.example", name="Ivy Moss", is_system_admin=False
    )
    await ProjectMembershipFactory.create_async(
        project=t.project, user=person, role=ProjectRole.MEMBER
    )
    return person


async def patch(client: AsyncClient, requirement: Requirement, **fields: object) -> Response:
    return await client.patch(URL, json={"version": requirement.version, **fields})


def fields(response: Response) -> list[tuple[list[object], str]]:
    return [(e["loc"], e["type"]) for e in response.json()["details"]["fields"]]


def assert_hidden(response: Response, missing: Response) -> None:
    """404 `not_found`, the same body as for a project that doesn't exist, naming nothing."""
    assert (response.status_code, response.json()["code"]) == (404, "not_found")
    assert response.json() == missing.json()
    for name in ("Bolt Foods", "bolt-foods", "Payments", "PMT", TITLE):
        assert name not in response.text


def assert_forbidden(response: Response) -> None:
    assert (response.status_code, response.json()["code"]) == (403, "forbidden")


# --- PATCH …/requirements/{number} (requirement.update) -----------------------------------------


@pytest.mark.parametrize("who", PROJECT_UNSEEN)
async def test_patching_a_requirement_is_404_to_who_cannot_see_the_project(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    """§5: failures on entities the user can't see return 404, not 403."""
    _, requirement = await signed_in(client, who)

    response = await patch(client, requirement, status="in_progress")

    assert_hidden(
        response, await client.patch(MISSING_URL, json={"version": 1, "status": "in_progress"})
    )
    assert (await stored(session, requirement))["status"] == "draft"


async def test_a_project_viewer_may_not_patch_a_requirement(
    client: AsyncClient, session: AsyncSession
) -> None:
    """§5 "Role capabilities": a viewer views; the viewer sees the project, so a 403."""
    _, requirement = await signed_in(client, "project_viewer")

    response = await patch(client, requirement, status="in_progress")

    assert_forbidden(response)
    assert (await stored(session, requirement))["status"] == "draft"


async def test_a_member_moves_a_requirement_to_another_status(
    client: AsyncClient, session: AsyncSession
) -> None:
    """DL-148: members move a requirement from any status to any other except `approved`."""
    _, requirement = await signed_in(client, "project_member")

    response = await patch(client, requirement, status="in_progress")

    assert (response.status_code, response.json()["status"]) == (200, "in_progress")
    assert (await stored(session, requirement))["status"] == "in_progress"


async def test_a_members_patch_to_approved_is_403(
    client: AsyncClient, session: AsyncSession
) -> None:
    """DL-161: "A `PATCH` setting `status` to `approved` answers 403 to members"."""
    _, requirement = await signed_in(client, "project_member")

    response = await patch(client, requirement, status="approved")

    assert_forbidden(response)
    assert (await stored(session, requirement))["status"] == "draft"


@pytest.mark.parametrize("who", PROJECT_ADMINS)
async def test_an_admins_patch_to_approved_is_422_use_approve(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    """DL-161: "422 `validation_error` on `status`, type `use_approve`, to admins" (inherited
    included, DL-212): approving by hand has one path."""
    _, requirement = await signed_in(client, who)

    response = await patch(client, requirement, status="approved")

    assert (response.status_code, response.json()["code"]) == (422, "validation_error")
    assert fields(response) == [(["body", "status"], "use_approve")]
    assert (await stored(session, requirement))["status"] == "draft"


async def test_a_member_may_not_change_the_reporter(
    client: AsyncClient, session: AsyncSession
) -> None:
    """S2-plan: changing `reporter_id` needs `requirement.reassign_reporter` (project admins)."""
    t, requirement = await signed_in(client, "project_member")
    ivy = await project_member(t)
    reporter = requirement.reporter_id

    response = await patch(client, requirement, reporter_id=str(ivy.id))

    assert_forbidden(response)
    assert (await stored(session, requirement))["reporter_id"] == reporter


@pytest.mark.parametrize("who", ["project_admin", "org_admin"])
async def test_a_project_admin_reassigns_the_reporter_to_a_project_member(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    """DL-211: a project admin may reassign the reporter to a project member."""
    t, requirement = await signed_in(client, who)
    ivy = await project_member(t)

    response = await patch(client, requirement, reporter_id=str(ivy.id))

    assert (response.status_code, response.json()["reporter_id"]) == (200, str(ivy.id))
    assert (await stored(session, requirement))["reporter_id"] == ivy.id


# --- PUT …/requirements/{number}/restriction ------------------------------------------------------


async def test_a_member_raises_a_requirements_restriction(
    client: AsyncClient, session: AsyncSession
) -> None:
    """§3.1: "Members can raise an item's level and add categories"."""
    _, requirement = await signed_in(client, "project_member")

    response = await client.put(RESTRICTION_URL, json=RAISE)

    assert response.status_code == 200
    body = response.json()
    assert (body["restriction_level"], body["restriction_categories"]) == ("confidential", ["pii"])
    stored_row = await stored(session, requirement)
    assert (stored_row["level"], stored_row["categories"]) == ("confidential", ["pii"])


async def test_a_member_may_not_lower_a_requirements_restriction(
    client: AsyncClient, session: AsyncSession
) -> None:
    """§3.1: "Lowering a level or removing a category is project-admin only"."""
    _, requirement = await signed_in(
        client, "project_member", level=RestrictionLevel.CONFIDENTIAL, categories=["pii"]
    )

    response = await client.put(RESTRICTION_URL, json=LOWER)

    assert_forbidden(response)
    stored_row = await stored(session, requirement)
    assert (stored_row["level"], stored_row["categories"]) == ("confidential", ["pii"])


@pytest.mark.parametrize("who", PROJECT_ADMINS)
async def test_a_project_admin_lowers_a_requirements_restriction(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    """§3.1: lowering is project-admin only; "Project admin" includes inherited admin (§5)."""
    _, requirement = await signed_in(
        client, who, level=RestrictionLevel.CONFIDENTIAL, categories=["pii"]
    )

    response = await client.put(RESTRICTION_URL, json=LOWER)

    assert response.status_code == 200
    body = response.json()
    assert (body["restriction_level"], body["restriction_categories"]) == ("confidential", [])
    stored_row = await stored(session, requirement)
    assert (stored_row["level"], stored_row["categories"]) == ("confidential", [])


async def test_a_project_viewer_may_not_raise_a_requirements_restriction(
    client: AsyncClient, session: AsyncSession
) -> None:
    """§5 "Role capabilities": a viewer views; raising is members' and up."""
    _, requirement = await signed_in(client, "project_viewer")

    response = await client.put(RESTRICTION_URL, json=RAISE)

    assert_forbidden(response)
    stored_row = await stored(session, requirement)
    assert (stored_row["level"], stored_row["categories"]) == (None, [])


@pytest.mark.parametrize("who", PROJECT_UNSEEN)
async def test_setting_a_requirements_restriction_is_404_to_who_cannot_see_the_project(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    _, requirement = await signed_in(client, who)

    response = await client.put(RESTRICTION_URL, json=RAISE)

    assert_hidden(response, await client.put(MISSING_RESTRICTION_URL, json=RAISE))
    stored_row = await stored(session, requirement)
    assert (stored_row["level"], stored_row["categories"]) == (None, [])


@pytest.mark.parametrize("who", INHERITED_ADMINS)
async def test_setting_a_requirements_restriction_on_an_ec_project_is_404_to_inherited_admins(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    """§3.1: "Every content action denied to them, read or mutation, is a 404"."""
    _, requirement = await signed_in(client, who, export_controlled=True)

    response = await client.put(RESTRICTION_URL, json=RAISE)

    assert_hidden(response, await client.put(MISSING_RESTRICTION_URL, json=RAISE))
    stored_row = await stored(session, requirement)
    assert (stored_row["level"], stored_row["categories"]) == (None, [])


# --- allowed_actions on the requirement read ---------------------------------------------------


@pytest.mark.parametrize(
    ("who", "offered"), [("project_admin", True), ("org_admin", True), ("project_member", False)]
)
async def test_allowed_actions_offer_approve_manually_only_to_project_admins(
    client: AsyncClient, who: str, offered: bool
) -> None:
    """DL-148, DL-212: `allowed_actions` carries `requirement.approve_manually`, so the status menu
    offers Approved only to those who may use it."""
    await signed_in(client, who)

    response = await client.get(URL)

    assert response.status_code == 200
    assert ("requirement.approve_manually" in response.json()["allowed_actions"]) is offered
