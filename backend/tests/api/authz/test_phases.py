"""Authorization wiring of S3-C3's phase endpoints (build plan, Slice 3 row 3 and "API
conventions": invisible is 404, seen but not allowed is 403; design-doc §5, "Role capabilities":
viewers read, members "manage sprints, phases, milestones, workstreams"; §3.1, export-controlled
projects; §9: an archived project is read-only, still browsable). The actions are S3-C2's
`phase.view` (content, viewers and up, inherited admins) and `phase.manage` (content, members and
up, inherited admins); their unit matrix is tests/unit/authz/test_task_actions.py.

- `POST /api/projects/{key}/phases`, `PATCH` and `DELETE .../phases/{phase_id}`, and
  `POST .../phases/{phase_id}/move` (`phase.manage`): allowed to a project member and an inherited
  admin; 403, nothing changed, to a project viewer and to a member of an archived project; 404,
  naming nothing, to who can't see the project and to an inherited admin on an export-controlled
  project, where an explicit member is allowed;
- `GET /api/projects/{key}/phases` and `GET .../phases/{phase_id}` (`phase.view`): 200 to a
  viewer, a member, and an inherited admin, archived or not; the same 404s;
- a phase of another project, under PMT's key, is a 404 on every per-phase endpoint, even to a
  member of both projects;
- the phase read's `allowed_actions` carry `phase.manage` for a member, not for a viewer.

Only authorization outcomes are asserted, with the stored phases re-read; rank placement of a new
phase, validation, and activity are the main session's tests. Personas are relative to workspace
"Acme Consulting", org "Bolt Foods" (bolt-foods), and project "Payments" (PMT)
(tests/support/authz.py, `persona_user`), which holds phases "Design" (rank a0) and "Build" (a1).
"""

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import ProjectRole
from app.models.phase import Phase
from app.models.user import User
from tests.factories.org import OrganizationFactory
from tests.factories.phase import PhaseFactory
from tests.factories.project import ProjectFactory, ProjectMembershipFactory
from tests.factories.workspace import WorkspaceFactory
from tests.support.authz import Tenancy, persona_user, sign_in_as

pytestmark = [pytest.mark.anyio, pytest.mark.security, pytest.mark.usefixtures("session")]

# Another org's owner; and a member of PMT's own org who isn't on PMT.
PROJECT_UNSEEN = ["other_org_owner", "org_member"]
MANAGE = ["create", "update", "delete", "move"]
READ = ["list", "read"]
PER_PHASE = ["read", "update", "delete", "move"]

ARCHIVED_AT = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
UNCHANGED = ["Design", "Build"]


@dataclass
class Scene:
    t: Tenancy
    user: User
    design: Phase
    build: Phase


async def signed_in(client: AsyncClient, who: str, *, export_controlled: bool = False) -> Scene:
    """`who` signed in, relative to "Payments" (PMT), which holds "Design" and "Build"."""
    workspace = await WorkspaceFactory.create_async(name="Acme Consulting", slug="acme")
    org = await OrganizationFactory.create_async(
        workspace=workspace, name="Bolt Foods", slug="bolt-foods"
    )
    project = await ProjectFactory.create_async(
        organization=org,
        key="PMT",
        name="Payments",
        restriction_categories=["export_controlled"] if export_controlled else [],
    )
    t = Tenancy(workspace, org, project)
    design = await PhaseFactory.create_async(project=project, name="Design", rank="a0")
    build = await PhaseFactory.create_async(project=project, name="Build", rank="a1")
    user = await persona_user(t, who)
    await sign_in_as(client, user)
    return Scene(t, user, design, build)


async def archive(session: AsyncSession, scene: Scene) -> None:
    scene.t.project.archived_at = ARCHIVED_AT
    await session.flush()


async def send(
    client: AsyncClient,
    endpoint: str,
    scene: Scene,
    *,
    key: str = "PMT",
    phase: Phase | None = None,
) -> Response:
    """Call `endpoint` under project `key`; the per-phase ones act on `phase` (PMT's "Design" by
    default); a move puts it after "Build"."""
    base = f"/api/projects/{key}/phases"
    url = f"{base}/{(phase or scene.design).id}"
    match endpoint:
        case "create":
            return await client.post(base, json={"name": "Deploy"})
        case "list":
            return await client.get(base)
        case "read":
            return await client.get(url)
        case "update":
            return await client.patch(url, json={"name": "Discovery"})
        case "delete":
            return await client.delete(url)
        case _:  # "move"
            return await client.post(f"{url}/move", json={"after_id": str(scene.build.id)})


async def stored(session: AsyncSession, scene: Scene) -> list[str]:
    """PMT's phase names in rank order, re-read from the database."""
    query = select(Phase.name).where(Phase.project_id == scene.t.project.id).order_by(Phase.rank)
    return list((await session.execute(query)).scalars())


def assert_hidden(response: Response, missing: Response) -> None:
    """404 `not_found`, the same body as for a project that doesn't exist, naming nothing."""
    assert (response.status_code, response.json()["code"]) == (404, "not_found")
    assert response.json() == missing.json()
    for name in ("Bolt Foods", "bolt-foods", "Payments", "PMT", "Design", "Build"):
        assert name not in response.text


def assert_forbidden(response: Response) -> None:
    assert (response.status_code, response.json()["code"]) == (403, "forbidden")


def assert_read(endpoint: str, response: Response) -> None:
    assert response.status_code == 200
    body = response.json()
    match endpoint:
        case "list":
            assert ([i["name"] for i in body["items"]], body["truncated"]) == (UNCHANGED, False)
        case _:  # "read"
            assert body["name"] == "Design"


ALLOWED = [("project_member", False), ("org_admin", False), ("project_member", True)]


# --- Manage endpoints (phase.manage) -----------------------------------------------------------


@pytest.mark.parametrize(("who", "export_controlled"), ALLOWED)
async def test_a_member_and_an_inherited_admin_create_a_phase(
    client: AsyncClient, session: AsyncSession, who: str, export_controlled: bool
) -> None:
    """On an export-controlled project only the explicit member (§3.1)."""
    scene = await signed_in(client, who, export_controlled=export_controlled)

    response = await send(client, "create", scene)

    assert (response.status_code, response.json()["name"]) == (201, "Deploy")
    assert sorted(await stored(session, scene)) == ["Build", "Deploy", "Design"]


@pytest.mark.parametrize(("who", "export_controlled"), ALLOWED)
async def test_a_member_and_an_inherited_admin_rename_a_phase(
    client: AsyncClient, session: AsyncSession, who: str, export_controlled: bool
) -> None:
    scene = await signed_in(client, who, export_controlled=export_controlled)

    response = await send(client, "update", scene)

    assert (response.status_code, response.json()["name"]) == (200, "Discovery")
    assert await stored(session, scene) == ["Discovery", "Build"]


@pytest.mark.parametrize(("who", "export_controlled"), ALLOWED)
async def test_a_member_and_an_inherited_admin_delete_a_phase(
    client: AsyncClient, session: AsyncSession, who: str, export_controlled: bool
) -> None:
    """Nothing references "Design", so it may go (§5, Deletion: phases, while unreferenced)."""
    scene = await signed_in(client, who, export_controlled=export_controlled)

    response = await send(client, "delete", scene)

    assert response.status_code == 204
    assert await stored(session, scene) == ["Build"]


@pytest.mark.parametrize(("who", "export_controlled"), ALLOWED)
async def test_a_member_and_an_inherited_admin_move_a_phase(
    client: AsyncClient, session: AsyncSession, who: str, export_controlled: bool
) -> None:
    scene = await signed_in(client, who, export_controlled=export_controlled)

    response = await send(client, "move", scene)

    assert (response.status_code, response.json()["name"]) == (200, "Design")
    assert await stored(session, scene) == ["Build", "Design"]


@pytest.mark.parametrize("endpoint", MANAGE)
async def test_a_project_viewer_may_not_manage_phases(
    client: AsyncClient, session: AsyncSession, endpoint: str
) -> None:
    """The viewer sees the project, so it's a 403 (§5)."""
    scene = await signed_in(client, "project_viewer")

    assert_forbidden(await send(client, endpoint, scene))
    assert await stored(session, scene) == UNCHANGED


@pytest.mark.parametrize("endpoint", MANAGE)
async def test_a_member_may_not_manage_phases_in_an_archived_project(
    client: AsyncClient, session: AsyncSession, endpoint: str
) -> None:
    """§5 step 1: every mutation inside an archived project is denied; the member sees it."""
    scene = await signed_in(client, "project_member")
    await archive(session, scene)

    assert_forbidden(await send(client, endpoint, scene))
    assert await stored(session, scene) == UNCHANGED


# --- Read endpoints (phase.view) ---------------------------------------------------------------


@pytest.mark.parametrize("endpoint", READ)
@pytest.mark.parametrize("who", ["project_viewer", "project_member", "org_admin"])
async def test_viewers_and_up_and_inherited_admins_read_phases(
    client: AsyncClient, who: str, endpoint: str
) -> None:
    scene = await signed_in(client, who)

    assert_read(endpoint, await send(client, endpoint, scene))


@pytest.mark.parametrize("endpoint", READ)
@pytest.mark.parametrize("who", ["project_viewer", "project_member"])
async def test_phases_stay_readable_in_an_archived_project(
    client: AsyncClient, session: AsyncSession, who: str, endpoint: str
) -> None:
    """§9: an archived project is still browsable."""
    scene = await signed_in(client, who)
    await archive(session, scene)

    assert_read(endpoint, await send(client, endpoint, scene))


@pytest.mark.parametrize("endpoint", READ)
@pytest.mark.parametrize("who", ["project_viewer", "project_member"])
async def test_explicit_members_read_phases_on_an_ec_project(
    client: AsyncClient, who: str, endpoint: str
) -> None:
    scene = await signed_in(client, who, export_controlled=True)

    assert_read(endpoint, await send(client, endpoint, scene))


# --- Hidden: 404 everywhere --------------------------------------------------------------------


@pytest.mark.parametrize("endpoint", [*READ, *MANAGE])
@pytest.mark.parametrize("who", PROJECT_UNSEEN)
async def test_phases_are_404_to_who_cannot_see_the_project(
    client: AsyncClient, session: AsyncSession, who: str, endpoint: str
) -> None:
    scene = await signed_in(client, who)

    response = await send(client, endpoint, scene)

    assert_hidden(response, await send(client, endpoint, scene, key="NOPE"))
    assert await stored(session, scene) == UNCHANGED


@pytest.mark.parametrize("endpoint", [*READ, *MANAGE])
async def test_phases_on_an_ec_project_are_404_to_an_inherited_admin(
    client: AsyncClient, session: AsyncSession, endpoint: str
) -> None:
    """§3.1: "Every content action denied to them, read or mutation, is a 404"."""
    scene = await signed_in(client, "org_admin", export_controlled=True)

    response = await send(client, endpoint, scene)

    assert_hidden(response, await send(client, endpoint, scene, key="NOPE"))
    assert await stored(session, scene) == UNCHANGED


@pytest.mark.parametrize("endpoint", PER_PHASE)
async def test_another_projects_phase_under_this_key_is_404(
    client: AsyncClient, session: AsyncSession, endpoint: str
) -> None:
    """The caller is a member of both PMT and Ledger (LDG); LDG's "Cutover" is still not PMT's."""
    scene = await signed_in(client, "project_member")
    ledger = await ProjectFactory.create_async(organization=scene.t.org, key="LDG", name="Ledger")
    await ProjectMembershipFactory.create_async(
        project=ledger, user=scene.user, role=ProjectRole.MEMBER
    )
    cutover = await PhaseFactory.create_async(project=ledger, name="Cutover", rank="a0")

    response = await send(client, endpoint, scene, phase=cutover)

    assert (response.status_code, response.json()["code"]) == (404, "not_found")
    assert "Cutover" not in response.text
    query = select(Phase.name, Phase.rank).where(Phase.project_id == ledger.id)
    assert list(await session.execute(query)) == [("Cutover", "a0")]


# --- allowed_actions on the phase read ---------------------------------------------------------


@pytest.mark.parametrize(
    ("who", "may_manage"), [("project_member", True), ("project_viewer", False)]
)
async def test_the_phase_reads_allowed_actions_carry_manage_only_for_a_member(
    client: AsyncClient, who: str, may_manage: bool
) -> None:
    """design-doc §5, "The UI asks the server": evaluated through `authorize()`."""
    scene = await signed_in(client, who)

    response = await send(client, "read", scene)

    assert response.status_code == 200
    actions = response.json()["allowed_actions"]
    assert ("phase.manage" in actions, "phase.view" in actions) == (may_manage, True)
