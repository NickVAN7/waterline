"""The task person and approver pickers' candidates (build plan, S3-C13): whom a task's assignee
or reviewer may be (DL-347: who may update tasks, members and up, inherited admins unless the
project is export-controlled, or, if it is, with a membership of any role, DL-417) and whom an
approval request may name (design-doc §6.2: who may view requirements, viewers and up, the same
inheritance; TD-96), active only, with `?q=` and offset paging. Personas: tests/support/authz.py."""

import pytest
from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.actions import Action
from app.authz.authorize import authorize
from app.authz.target import project_target
from app.enums import ProjectRole, RestrictionCategory
from app.models.user import User
from app.repositories.user import UserRepository
from tests.factories.project import ProjectMembershipFactory
from tests.factories.user import UserFactory
from tests.support.authz import Tenancy, persona_user, sign_in_as, tenancy

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("session")]

TASK_PEOPLE = "/api/projects/PMT/task-person-candidates"
APPROVERS = "/api/projects/PMT/approver-candidates"
EVERYONE = [
    "system_admin",
    "workspace_owner",
    "workspace_admin",
    "workspace_member",
    "org_owner",
    "org_admin",
    "org_member",
    "project_admin",
    "project_member",
    "project_viewer",
    "other_project_admin",
    "other_org_owner",
    "other_workspace_owner",
    "nobody",
]
INHERITED = ["system_admin", "workspace_owner", "workspace_admin", "org_owner", "org_admin"]


async def everyone(t: Tenancy) -> dict[str, User]:
    """One user per persona, by persona."""
    return {who: await persona_user(t, who) for who in EVERYONE}


def names(response: Response) -> list[str]:
    assert response.status_code == 200, response.text
    return [c["name"] for c in response.json()["items"]]


@pytest.mark.security
@pytest.mark.parametrize(
    ("url", "export_controlled", "expected"),
    [
        (TASK_PEOPLE, False, sorted([*INHERITED, "project_admin", "project_member"])),
        (TASK_PEOPLE, True, ["project_admin", "project_member"]),
        (
            APPROVERS,
            False,
            sorted([*INHERITED, "project_admin", "project_member", "project_viewer"]),
        ),
        (APPROVERS, True, ["project_admin", "project_member", "project_viewer"]),
    ],
)
async def test_the_candidates_are_whom_the_action_reaches(
    client: AsyncClient,
    session: AsyncSession,
    url: str,
    export_controlled: bool,
    expected: list[str],
) -> None:
    """DL-347, §6.2, §3.1. Bug: a viewer offered as an assignee, an inherited admin offered on an
    export-controlled project, or someone outside the project offered at all."""
    t = await tenancy()
    if export_controlled:
        t.project.restriction_categories = [RestrictionCategory.EXPORT_CONTROLLED]
        await session.flush()
    people = await everyone(t)
    who = {str(user.id): persona for persona, user in people.items()}
    await sign_in_as(client, people["project_admin"])

    response = await client.get(url, params={"limit": 200})

    assert response.status_code == 200, response.text
    assert sorted(who[c["user_id"]] for c in response.json()["items"]) == expected
    assert response.json()["total"] == len(expected)


@pytest.mark.parametrize("url", [TASK_PEOPLE, APPROVERS])
async def test_a_deactivated_member_is_not_offered(client: AsyncClient, url: str) -> None:
    """DL-347: an active user only (`check_person` refuses the rest, `account_inactive`)."""
    t = await tenancy()
    admin = await UserFactory.create_async(name="Ada Admin")
    gone = await UserFactory.create_async(name="Gus Gone", is_active=False)
    for user, role in ((admin, ProjectRole.ADMIN), (gone, ProjectRole.MEMBER)):
        await ProjectMembershipFactory.create_async(project=t.project, user=user, role=role)
    await sign_in_as(client, admin)

    assert names(await client.get(url)) == ["Ada Admin"]


@pytest.mark.parametrize("url", [TASK_PEOPLE, APPROVERS])
async def test_the_candidates_search_by_name_email_or_username_and_page(
    client: AsyncClient, url: str
) -> None:
    """TD-41's search, as the member picker's. Bug: `?q=` ignored, or the page's total off."""
    t = await tenancy()
    admin = await UserFactory.create_async(name="Ada Admin", username="ada")
    bob = await UserFactory.create_async(name="Bob Baker", username="bbaker")
    cy = await UserFactory.create_async(name="Cy Cole", email="cy@finance.example")
    for user in (admin, bob, cy):
        await ProjectMembershipFactory.create_async(
            project=t.project, user=user, role=ProjectRole.ADMIN
        )
    await sign_in_as(client, admin)

    assert names(await client.get(url, params={"q": "bob"})) == ["Bob Baker"]
    assert names(await client.get(url, params={"q": "BBAK"})) == ["Bob Baker"]
    assert names(await client.get(url, params={"q": "finance"})) == ["Cy Cole"]
    page = await client.get(url, params={"limit": 2, "offset": 1})
    assert (names(page), page.json()["total"]) == (["Bob Baker", "Cy Cole"], 3)


@pytest.mark.security
@pytest.mark.parametrize(
    ("url", "who", "status", "code"),
    [
        # A viewer sees the project but may not update tasks or requirements (§5).
        (TASK_PEOPLE, "project_viewer", 403, "forbidden"),
        (APPROVERS, "project_viewer", 403, "forbidden"),
        (TASK_PEOPLE, "org_member", 404, "not_found"),
        (APPROVERS, "org_member", 404, "not_found"),
    ],
)
async def test_who_may_not_update_cant_list_the_candidates(
    client: AsyncClient, url: str, who: str, status: int, code: str
) -> None:
    """The endpoints' actions: `task.update`, `requirement.update`; unseen is 404, naming
    nothing."""
    t = await tenancy()
    await sign_in_as(client, await persona_user(t, who))

    response = await client.get(url)

    assert (response.status_code, response.json()["code"]) == (status, code)
    assert "Payments" not in response.text


@pytest.mark.security
@pytest.mark.parametrize(
    ("url", "action"),
    [(TASK_PEOPLE, Action.TASK_UPDATE), (APPROVERS, Action.REQUIREMENT_VIEW)],
)
@pytest.mark.parametrize("export_controlled", [False, True])
async def test_a_candidate_is_exactly_who_the_person_check_accepts(
    client: AsyncClient,
    session: AsyncSession,
    url: str,
    action: Action,
    export_controlled: bool,
) -> None:
    """The picker's query and `check_person` (`authorize()` with the user's own context) must
    agree, persona by persona: a candidate the check refuses, or one it accepts left out, is
    the drift this catches."""
    t = await tenancy()
    if export_controlled:
        t.project.restriction_categories = [RestrictionCategory.EXPORT_CONTROLLED]
        await session.flush()
    people = await everyone(t)
    # Inherited admins who also hold a viewer membership: the gate lets them through, so their
    # admin role grants `task.update` on an export-controlled project too.
    for who in ("system_admin", "org_admin", "workspace_admin"):
        people[f"{who}_viewing"] = user = await persona_user(t, who)
        await ProjectMembershipFactory.create_async(
            project=t.project, user=user, role=ProjectRole.VIEWER
        )
    await sign_in_as(client, people["project_admin"])
    users = UserRepository(session)
    target = project_target(t.project)

    response = await client.get(url, params={"limit": 200})

    offered = {c["user_id"] for c in response.json()["items"]}
    accepted = {
        str(user.id)
        for user in people.values()
        if authorize(await users.authz_context(user), action, target)
    }
    assert offered == accepted


async def test_the_approver_candidates_filter_by_user_id(client: AsyncClient) -> None:
    """DL-422: Re-request asks about its earlier approvers by `user_id` (any of). Bug: the filter
    ignored (everyone listed), or it lets someone through who isn't a candidate."""
    t = await tenancy()
    admin = await UserFactory.create_async(name="Ada Admin")
    bob = await UserFactory.create_async(name="Bob Baker")
    gone = await UserFactory.create_async(name="Gus Gone", is_active=False)
    for user in (admin, bob, gone):
        await ProjectMembershipFactory.create_async(
            project=t.project, user=user, role=ProjectRole.MEMBER
        )
    await ProjectMembershipFactory.create_async(
        project=t.project,
        user=await UserFactory.create_async(name="Cy Cole"),
        role=ProjectRole.MEMBER,
    )
    outsider = await UserFactory.create_async(name="Olive Out")
    await sign_in_as(client, admin)

    response = await client.get(
        APPROVERS, params={"user_id": [str(bob.id), str(gone.id), str(outsider.id)]}
    )

    assert names(response) == ["Bob Baker"]
    assert response.json()["total"] == 1


async def test_only_the_approver_candidates_take_a_user_id(client: AsyncClient) -> None:
    """DL-422 adds `user_id` to the approver picker only: elsewhere it's a typo, a 422."""
    t = await tenancy()
    await sign_in_as(client, await persona_user(t, "project_admin"))

    response = await client.get(TASK_PEOPLE, params={"user_id": str(t.project.id)})

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
