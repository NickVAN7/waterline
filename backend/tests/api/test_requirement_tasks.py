"""A requirement's tasks (build plan S3-C10; DL-196): `GET …/requirements/{number}/tasks` lists
its live tasks as the backlog's rows, in its order, to whoever may view the requirement; 404,
naming nothing, to who can't see it, as for the requirement."""

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from app.enums import ProjectRole, TaskStatus
from app.models.user import User
from app.services import task as task_service
from tests.factories.org import OrganizationFactory
from tests.factories.project import ProjectFactory, ProjectMembershipFactory
from tests.factories.requirement import RequirementFactory
from tests.factories.task import TaskFactory
from tests.factories.user import UserFactory
from tests.factories.workspace import WorkspaceFactory
from tests.support.authz import Tenancy, persona_user, sign_in_as, tenancy

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("session")]

URL = "/api/projects/PMT/requirements/1/tasks"
EARLIER = datetime(2026, 3, 1, tzinfo=UTC)
PROJECT_UNSEEN = ["org_member", "other_project_admin", "workspace_member", "nobody"]
INHERITED_ADMINS = ["system_admin", "workspace_owner", "workspace_admin", "org_owner", "org_admin"]


@pytest.fixture
async def t() -> Tenancy:
    return await tenancy()


async def viewer(client: AsyncClient, t: Tenancy) -> User:
    user = await UserFactory.create_async(name="Vic Viewer")
    await ProjectMembershipFactory.create_async(
        project=t.project, user=user, role=ProjectRole.VIEWER
    )
    await sign_in_as(client, user)
    return user


async def test_a_viewer_lists_the_requirements_live_tasks_in_rank_order(
    client: AsyncClient, t: Tenancy
) -> None:
    """Bug: another requirement's task, a deleted one, or the order not the backlog's (rank);
    a cancelled one left out (only the coverage counts leave it out)."""
    await viewer(client, t)
    rq1 = await RequirementFactory.create_async(project=t.project, number=1)
    rq2 = await RequirementFactory.create_async(project=t.project, number=2)
    assignee = await UserFactory.create_async(name="Ana Assignee")
    await TaskFactory.create_async(
        project=t.project, number=1, rank="i2", requirement_id=rq1.id, assignee_id=assignee.id
    )
    for number, rank, requirement, status, deleted_at in (
        (2, "i0", rq1, TaskStatus.CANCELLED, None),
        (3, "i1", rq2, TaskStatus.TODO, None),
        (4, "i1", rq1, TaskStatus.DONE, EARLIER),
    ):
        await TaskFactory.create_async(
            project=t.project,
            number=number,
            rank=rank,
            requirement_id=requirement.id,
            status=status,
            deleted_at=deleted_at,
        )

    response = await client.get(URL)

    assert response.status_code == 200
    body = response.json()
    assert (
        [(row["number"], row["status"]) for row in body["items"]],
        body["truncated"],
    ) == ([(2, "cancelled"), (1, "todo")], False)
    assert body["items"][1]["assignee_name"] == "Ana Assignee"


@pytest.mark.parametrize(("beyond_the_cap", "truncated"), [(0, False), (1, True)])
async def test_the_list_stops_at_the_cap_and_says_so(
    client: AsyncClient,
    t: Tenancy,
    monkeypatch: pytest.MonkeyPatch,
    beyond_the_cap: int,
    truncated: bool,
) -> None:
    """Bug: an off-by-one at the cap, so a requirement with more tasks than it shows says
    nothing is missing (DL-159, DL-414)."""
    monkeypatch.setattr(task_service, "LIST_CAP", 2)
    await viewer(client, t)
    rq1 = await RequirementFactory.create_async(project=t.project, number=1)
    await TaskFactory.create_async(project=t.project, number=1, rank="i0", requirement_id=rq1.id)
    await TaskFactory.create_async(project=t.project, number=2, rank="i1", requirement_id=rq1.id)
    await TaskFactory.create_batch_async(
        beyond_the_cap, project=t.project, rank="i2", requirement_id=rq1.id
    )

    body = (await client.get(URL)).json()

    assert ([row["number"] for row in body["items"]], body["truncated"]) == ([1, 2], truncated)


async def test_a_requirement_with_no_tasks_lists_none(client: AsyncClient, t: Tenancy) -> None:
    await viewer(client, t)
    await RequirementFactory.create_async(project=t.project, number=1)

    assert (await client.get(URL)).json() == {"items": [], "truncated": False}


async def test_a_deleted_requirements_tasks_are_a_404(client: AsyncClient, t: Tenancy) -> None:
    """Bug: the list read through a requirement in the trash (§9: a deleted item is a 404)."""
    await viewer(client, t)
    await RequirementFactory.create_async(project=t.project, number=1, deleted_at=EARLIER)

    response = await client.get(URL)

    assert (response.status_code, response.json()["code"]) == (404, "not_found")


async def scene(client: AsyncClient, who: str, *, export_controlled: bool = False) -> None:
    """`who` signed in, relative to PMT, whose RQ-1 has TA-1 "Sign-in throttling"."""
    workspace = await WorkspaceFactory.create_async(name="Acme Consulting", slug="acme")
    org = await OrganizationFactory.create_async(workspace=workspace, slug="bolt-foods")
    project = await ProjectFactory.create_async(
        organization=org,
        key="PMT",
        restriction_level=None,
        restriction_categories=["export_controlled"] if export_controlled else [],
    )
    user = await persona_user(Tenancy(workspace, org, project), who)
    rq1 = await RequirementFactory.create_async(project=project, number=1)
    await TaskFactory.create_async(
        project=project, number=1, requirement_id=rq1.id, title="Sign-in throttling"
    )
    await sign_in_as(client, user)


@pytest.mark.security
@pytest.mark.parametrize("who", PROJECT_UNSEEN)
async def test_the_tasks_are_a_404_naming_nothing_to_who_cant_see_the_project(
    client: AsyncClient, who: str
) -> None:
    """§5: an entity the user can't see is a 404, not a 403, and names nothing."""
    await scene(client, who)

    response = await client.get(URL)

    assert (response.status_code, response.json()["code"]) == (404, "not_found")
    assert "Sign-in throttling" not in response.text


@pytest.mark.security
@pytest.mark.parametrize("who", INHERITED_ADMINS)
async def test_inherited_admins_list_them_but_not_on_an_ec_project(
    client: AsyncClient, who: str
) -> None:
    """§3.1: an export-controlled project's content is for explicit members only."""
    await scene(client, who, export_controlled=True)

    response = await client.get(URL)

    assert (response.status_code, response.json()["code"]) == (404, "not_found")
    assert "Sign-in throttling" not in response.text


@pytest.mark.security
@pytest.mark.parametrize("who", INHERITED_ADMINS)
async def test_inherited_admins_list_them(client: AsyncClient, who: str) -> None:
    await scene(client, who)

    response = await client.get(URL)

    assert [row["title"] for row in response.json()["items"]] == ["Sign-in throttling"]
