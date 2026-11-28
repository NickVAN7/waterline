"""Authorization wiring of S3-C4's workstream endpoints (build plan, Slice 3 row 4 and "API
conventions": invisible is 404, seen but not allowed is 403; design-doc §5, "Role capabilities":
viewers read, members "manage sprints, phases, milestones, workstreams"; §3.1, export-controlled
projects; §9: an archived project is read-only, still browsable). The actions are S3-C2's
`workstream.view` (content, viewers and up, inherited admins) and `workstream.manage` (content,
members and up, inherited admins).

- `POST /api/projects/{key}/workstreams`, `PATCH .../workstreams/{workstream_id}`, and
  `POST .../{workstream_id}/move`, `.../archive`, `.../unarchive` (`workstream.manage`): allowed to
  a project member and an inherited admin; 403, nothing changed, to a project viewer and to a
  member of an archived project; 404, naming nothing, to who can't see the project and to an
  inherited admin on an export-controlled project, where an explicit member is allowed;
- `GET /api/projects/{key}/workstreams` (with and without `?include_archived=true`) and
  `GET .../workstreams/{workstream_id}` (`workstream.view`): 200 to a viewer, a member, and an
  inherited admin, archived project or not; the same 404s;
- a workstream of another project, under PMT's key, is a 404 on every per-workstream endpoint,
  even to a member of both projects;
- the workstream read's `allowed_actions` carry `workstream.manage` for a member, not a viewer.

Only authorization outcomes are asserted, with the stored workstreams re-read; placement of a new
workstream, validation, the lead rule, and activity are the main session's tests. Personas are
relative to workspace "Acme Consulting", org "Bolt Foods" (bolt-foods), and project "Payments"
(PMT) (tests/support/authz.py, `persona_user`), which holds workstreams "Finance" (rank i0),
"Procurement" (i1), and the archived "Data Migration" (i2).
"""

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import ProjectRole
from app.models.user import User
from app.models.workstream import Workstream
from tests.factories.org import OrganizationFactory
from tests.factories.project import ProjectFactory, ProjectMembershipFactory
from tests.factories.workspace import WorkspaceFactory
from tests.factories.workstream import WorkstreamFactory
from tests.support.authz import Tenancy, persona_user, sign_in_as

pytestmark = [pytest.mark.anyio, pytest.mark.security, pytest.mark.usefixtures("session")]

# Another org's owner; and a member of PMT's own org who isn't on PMT.
PROJECT_UNSEEN = ["other_org_owner", "org_member"]
MANAGE = ["create", "update", "move", "archive", "unarchive"]
READ = ["list", "list_archived", "read"]
PER_WORKSTREAM = ["read", "update", "move", "archive", "unarchive"]

ARCHIVED_AT = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
# PMT's workstreams in rank order, each with whether it's archived.
UNCHANGED = [("Finance", False), ("Procurement", False), ("Data Migration", True)]


@dataclass
class Scene:
    t: Tenancy
    user: User
    finance: Workstream
    procurement: Workstream
    migration: Workstream


async def signed_in(client: AsyncClient, who: str, *, export_controlled: bool = False) -> Scene:
    """`who` signed in, relative to "Payments" (PMT) and its three workstreams."""
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
    finance = await WorkstreamFactory.create_async(project=project, name="Finance", rank="i0")
    procurement = await WorkstreamFactory.create_async(
        project=project, name="Procurement", rank="i1"
    )
    migration = await WorkstreamFactory.create_async(
        project=project, name="Data Migration", rank="i2", archived_at=ARCHIVED_AT
    )
    user = await persona_user(t, who)
    await sign_in_as(client, user)
    return Scene(t, user, finance, procurement, migration)


async def archive_project(session: AsyncSession, scene: Scene) -> None:
    scene.t.project.archived_at = ARCHIVED_AT
    await session.flush()


async def send(
    client: AsyncClient,
    endpoint: str,
    scene: Scene,
    *,
    key: str = "PMT",
    workstream: Workstream | None = None,
) -> Response:
    """Call `endpoint` under project `key`. The per-workstream ones act on `workstream`, by default
    "Finance", except unarchive, on the archived "Data Migration"; a move puts it after
    "Procurement"."""
    base = f"/api/projects/{key}/workstreams"
    default = scene.migration if endpoint == "unarchive" else scene.finance
    url = f"{base}/{(workstream or default).id}"
    match endpoint:
        case "create":
            return await client.post(base, json={"name": "Reporting"})
        case "list":
            return await client.get(base)
        case "list_archived":
            return await client.get(base, params={"include_archived": "true"})
        case "read":
            return await client.get(url)
        case "update":
            return await client.patch(url, json={"name": "Record to Report"})
        case "move":
            return await client.post(f"{url}/move", json={"after_id": str(scene.procurement.id)})
        case "archive":
            return await client.post(f"{url}/archive")
        case _:  # "unarchive"
            return await client.post(f"{url}/unarchive")


async def stored(session: AsyncSession, scene: Scene) -> list[tuple[str, bool]]:
    """PMT's workstreams in rank order, each with whether it's archived, re-read."""
    query = (
        select(Workstream.name, Workstream.archived_at.is_not(None))
        .where(Workstream.project_id == scene.t.project.id)
        .order_by(Workstream.rank)
    )
    return [(name, archived) for name, archived in await session.execute(query)]


def assert_hidden(response: Response, missing: Response) -> None:
    """404 `not_found`, the same body as for a project that doesn't exist, naming nothing."""
    assert (response.status_code, response.json()["code"]) == (404, "not_found")
    assert response.json() == missing.json()
    names = ("Bolt Foods", "bolt-foods", "Payments", "PMT", "Finance", "Procurement", "Migration")
    assert [name for name in names if name in response.text] == []


def assert_forbidden(response: Response) -> None:
    assert (response.status_code, response.json()["code"]) == (403, "forbidden")


def assert_read(endpoint: str, response: Response) -> None:
    assert response.status_code == 200
    body = response.json()
    match endpoint:
        case "list":
            names = [i["name"] for i in body["items"]]
            assert (names, body["truncated"]) == (["Finance", "Procurement"], False)
        case "list_archived":
            names = [i["name"] for i in body["items"]]
            assert (names, body["truncated"]) == (
                ["Finance", "Procurement", "Data Migration"],
                False,
            )
        case _:  # "read"
            assert body["name"] == "Finance"


ALLOWED = [("project_member", False), ("org_admin", False), ("project_member", True)]


# --- Manage endpoints (workstream.manage) ------------------------------------------------------


@pytest.mark.parametrize(("who", "export_controlled"), ALLOWED)
async def test_a_member_and_an_inherited_admin_create_a_workstream(
    client: AsyncClient, session: AsyncSession, who: str, export_controlled: bool
) -> None:
    """On an export-controlled project only the explicit member (§3.1)."""
    scene = await signed_in(client, who, export_controlled=export_controlled)

    response = await send(client, "create", scene)

    assert (response.status_code, response.json()["name"]) == (201, "Reporting")
    assert sorted(await stored(session, scene)) == [
        ("Data Migration", True),
        ("Finance", False),
        ("Procurement", False),
        ("Reporting", False),
    ]


@pytest.mark.parametrize(("who", "export_controlled"), ALLOWED)
async def test_a_member_and_an_inherited_admin_rename_a_workstream(
    client: AsyncClient, session: AsyncSession, who: str, export_controlled: bool
) -> None:
    scene = await signed_in(client, who, export_controlled=export_controlled)

    response = await send(client, "update", scene)

    assert (response.status_code, response.json()["name"]) == (200, "Record to Report")
    assert await stored(session, scene) == [
        ("Record to Report", False),
        ("Procurement", False),
        ("Data Migration", True),
    ]


@pytest.mark.parametrize(("who", "export_controlled"), ALLOWED)
async def test_a_member_and_an_inherited_admin_move_a_workstream(
    client: AsyncClient, session: AsyncSession, who: str, export_controlled: bool
) -> None:
    """ "Finance" after "Procurement". Only the live rows' order is asserted: the docs don't say
    where a move puts a row relative to an archived one."""
    scene = await signed_in(client, who, export_controlled=export_controlled)

    response = await send(client, "move", scene)

    assert (response.status_code, response.json()["name"]) == (200, "Finance")
    live = [name for name, archived in await stored(session, scene) if not archived]
    assert live == ["Procurement", "Finance"]


@pytest.mark.parametrize(("who", "export_controlled"), ALLOWED)
async def test_a_member_and_an_inherited_admin_archive_a_workstream(
    client: AsyncClient, session: AsyncSession, who: str, export_controlled: bool
) -> None:
    scene = await signed_in(client, who, export_controlled=export_controlled)

    response = await send(client, "archive", scene)

    assert (response.status_code, response.json()["archived"]) == (200, True)
    assert await stored(session, scene) == [
        ("Finance", True),
        ("Procurement", False),
        ("Data Migration", True),
    ]


@pytest.mark.parametrize(("who", "export_controlled"), ALLOWED)
async def test_a_member_and_an_inherited_admin_unarchive_a_workstream(
    client: AsyncClient, session: AsyncSession, who: str, export_controlled: bool
) -> None:
    scene = await signed_in(client, who, export_controlled=export_controlled)

    response = await send(client, "unarchive", scene)

    assert (response.status_code, response.json()["archived"]) == (200, False)
    assert await stored(session, scene) == [
        ("Finance", False),
        ("Procurement", False),
        ("Data Migration", False),
    ]


@pytest.mark.parametrize("endpoint", MANAGE)
async def test_a_project_viewer_may_not_manage_workstreams(
    client: AsyncClient, session: AsyncSession, endpoint: str
) -> None:
    """The viewer sees the project, so it's a 403 (§5)."""
    scene = await signed_in(client, "project_viewer")

    assert_forbidden(await send(client, endpoint, scene))
    assert await stored(session, scene) == UNCHANGED


@pytest.mark.parametrize("endpoint", MANAGE)
async def test_a_member_may_not_manage_workstreams_in_an_archived_project(
    client: AsyncClient, session: AsyncSession, endpoint: str
) -> None:
    """§5 step 1: every mutation inside an archived project is denied; the member sees it."""
    scene = await signed_in(client, "project_member")
    await archive_project(session, scene)

    assert_forbidden(await send(client, endpoint, scene))
    assert await stored(session, scene) == UNCHANGED


# --- Read endpoints (workstream.view) ----------------------------------------------------------


@pytest.mark.parametrize("endpoint", READ)
@pytest.mark.parametrize("who", ["project_viewer", "project_member", "org_admin"])
async def test_viewers_and_up_and_inherited_admins_read_workstreams(
    client: AsyncClient, who: str, endpoint: str
) -> None:
    scene = await signed_in(client, who)

    assert_read(endpoint, await send(client, endpoint, scene))


@pytest.mark.parametrize("endpoint", READ)
@pytest.mark.parametrize("who", ["project_viewer", "project_member"])
async def test_workstreams_stay_readable_in_an_archived_project(
    client: AsyncClient, session: AsyncSession, who: str, endpoint: str
) -> None:
    """§9: an archived project is still browsable."""
    scene = await signed_in(client, who)
    await archive_project(session, scene)

    assert_read(endpoint, await send(client, endpoint, scene))


@pytest.mark.parametrize("endpoint", READ)
@pytest.mark.parametrize("who", ["project_viewer", "project_member"])
async def test_explicit_members_read_workstreams_on_an_ec_project(
    client: AsyncClient, who: str, endpoint: str
) -> None:
    scene = await signed_in(client, who, export_controlled=True)

    assert_read(endpoint, await send(client, endpoint, scene))


# --- Hidden: 404 everywhere --------------------------------------------------------------------


@pytest.mark.parametrize("endpoint", [*READ, *MANAGE])
@pytest.mark.parametrize("who", PROJECT_UNSEEN)
async def test_workstreams_are_404_to_who_cannot_see_the_project(
    client: AsyncClient, session: AsyncSession, who: str, endpoint: str
) -> None:
    scene = await signed_in(client, who)

    response = await send(client, endpoint, scene)

    assert_hidden(response, await send(client, endpoint, scene, key="NOPE"))
    assert await stored(session, scene) == UNCHANGED


@pytest.mark.parametrize("endpoint", [*READ, *MANAGE])
async def test_workstreams_on_an_ec_project_are_404_to_an_inherited_admin(
    client: AsyncClient, session: AsyncSession, endpoint: str
) -> None:
    """§3.1: "Every content action denied to them, read or mutation, is a 404"."""
    scene = await signed_in(client, "org_admin", export_controlled=True)

    response = await send(client, endpoint, scene)

    assert_hidden(response, await send(client, endpoint, scene, key="NOPE"))
    assert await stored(session, scene) == UNCHANGED


@pytest.mark.parametrize("endpoint", PER_WORKSTREAM)
async def test_another_projects_workstream_under_this_key_is_404(
    client: AsyncClient, session: AsyncSession, endpoint: str
) -> None:
    """The caller is a member of both PMT and Ledger (LDG); LDG's "Treasury" is still not PMT's.
    It's live for archive and archived for unarchive, so either would change it if found."""
    scene = await signed_in(client, "project_member")
    ledger = await ProjectFactory.create_async(organization=scene.t.org, key="LDG", name="Ledger")
    await ProjectMembershipFactory.create_async(
        project=ledger, user=scene.user, role=ProjectRole.MEMBER
    )
    archived_at = ARCHIVED_AT if endpoint == "unarchive" else None
    treasury = await WorkstreamFactory.create_async(
        project=ledger, name="Treasury", rank="a0", archived_at=archived_at
    )

    response = await send(client, endpoint, scene, workstream=treasury)

    assert (response.status_code, response.json()["code"]) == (404, "not_found")
    assert "Treasury" not in response.text
    query = select(Workstream.name, Workstream.rank, Workstream.archived_at).where(
        Workstream.project_id == ledger.id
    )
    assert list(await session.execute(query)) == [("Treasury", "a0", archived_at)]


# --- allowed_actions on the workstream read ----------------------------------------------------


@pytest.mark.parametrize(
    ("who", "may_manage"), [("project_member", True), ("project_viewer", False)]
)
async def test_the_workstream_reads_allowed_actions_carry_manage_only_for_a_member(
    client: AsyncClient, who: str, may_manage: bool
) -> None:
    """design-doc §5, "The UI asks the server": evaluated through `authorize()`."""
    scene = await signed_in(client, who)

    response = await send(client, "read", scene)

    assert response.status_code == 200
    actions = response.json()["allowed_actions"]
    assert ("workstream.manage" in actions, "workstream.view" in actions) == (may_manage, True)
