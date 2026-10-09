"""The load-and-authorize dependency and module gating over HTTP (design-doc §5, "Reads are
authorized too", "Module gating"; build plan, "Authorization (§5)"), through the test-only
router in tests/support/authz.py.

Each persona is a real user with real memberships, relative to project "Payments" (key PMT,
org Bolt Foods, workspace Acme Consulting).
"""

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionMaker
from app.core.settings import Settings
from app.enums import OrgRole, ProjectModule, ProjectRole, WorkspaceRole
from app.main import create_app
from app.models.org import Organization
from app.models.project import Project
from app.models.user import User
from app.models.workspace import Workspace
from tests.factories.org import MembershipFactory, OrganizationFactory
from tests.factories.project import ProjectFactory, ProjectMembershipFactory
from tests.factories.user import UserFactory
from tests.factories.workspace import WorkspaceFactory, WorkspaceMembershipFactory
from tests.support.api import api_client
from tests.support.authz import register_test_actions, router, sign_in_as

pytestmark = [pytest.mark.anyio, pytest.mark.security, pytest.mark.usefixtures("session")]

NOT_FOUND = "not_found"


@pytest.fixture
async def client(
    settings: Settings, sessionmaker: SessionMaker, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[AsyncClient]:
    register_test_actions(monkeypatch)
    app = create_app(settings, sessionmaker=sessionmaker)
    app.include_router(router)
    async with api_client(app) as c:
        yield c


@dataclass
class World:
    workspace: Workspace
    org: Organization
    project: Project


async def world(*, modules: list[str] | None = None, archived: bool = False) -> World:
    workspace = await WorkspaceFactory.create_async(name="Acme Consulting", slug="acme")
    org = await OrganizationFactory.create_async(workspace=workspace, name="Bolt Foods")
    project = await ProjectFactory.create_async(
        organization=org,
        key="PMT",
        name="Payments",
        enabled_modules=[ProjectModule.SPRINTS.value] if modules is None else modules,
        archived_at=datetime(2026, 10, 1, tzinfo=UTC) if archived else None,
    )
    return World(workspace, org, project)


async def persona(w: World, who: str) -> User:
    """A user who is `who` relative to `w`."""
    user = await UserFactory.create_async(is_system_admin=who == "system_admin")
    match who:
        case "workspace_owner" | "workspace_admin" | "workspace_member":
            role = WorkspaceRole(who.removeprefix("workspace_"))
            await WorkspaceMembershipFactory.create_async(
                workspace=w.workspace, user=user, role=role
            )
        case "org_owner" | "org_admin" | "org_member":
            role = OrgRole(who.removeprefix("org_"))
            await MembershipFactory.create_async(organization=w.org, user=user, role=role)
        case "project_admin" | "project_member" | "project_viewer":
            role = ProjectRole(who.removeprefix("project_"))
            await ProjectMembershipFactory.create_async(project=w.project, user=user, role=role)
        case "other_project_admin":
            other = await ProjectFactory.create_async(organization=w.org, name="Ledger")
            await ProjectMembershipFactory.create_async(
                project=other, user=user, role=ProjectRole.ADMIN
            )
        case "other_org_admin":
            other = await OrganizationFactory.create_async(workspace=w.workspace)
            await MembershipFactory.create_async(organization=other, user=user, role=OrgRole.ADMIN)
        case "other_workspace_owner":
            await WorkspaceMembershipFactory.create_async(
                workspace=await WorkspaceFactory.create_async(), user=user, role=WorkspaceRole.OWNER
            )
        case _:  # "system_admin", "nobody"
            pass
    return user


async def as_(client: AsyncClient, w: World, who: str) -> AsyncClient:
    await sign_in_as(client, await persona(w, who))
    return client


async def stored(session: AsyncSession, project: Project) -> Project:
    found = await session.scalar(
        select(Project).where(Project.id == project.id).execution_options(populate_existing=True)
    )
    assert found is not None
    return found


# --- Reads: 404 for what the user can't see ------------------------------------------------------


@pytest.mark.parametrize(
    "who",
    ["project_viewer", "system_admin", "workspace_owner", "workspace_admin", "org_owner",
     "org_admin"],
)  # fmt: skip
async def test_a_project_member_or_inherited_admin_gets_the_project(
    client: AsyncClient, who: str
) -> None:
    w = await world()
    await as_(client, w, who)

    response = await client.get(f"/test/authz/projects/{w.project.id}")

    assert response.status_code == 200
    assert response.json() == {"id": str(w.project.id), "name": "Payments"}


@pytest.mark.parametrize(
    "who",
    ["org_member", "workspace_member", "other_project_admin", "other_org_admin",
     "other_workspace_owner", "nobody"],
)  # fmt: skip
async def test_a_project_the_user_cannot_see_is_the_same_404_as_a_missing_one(
    client: AsyncClient, who: str
) -> None:
    w = await world()
    await as_(client, w, who)

    unseen = await client.get(f"/test/authz/projects/{w.project.id}")
    missing = await client.get(f"/test/authz/projects/{uuid.uuid4()}")

    assert (unseen.status_code, unseen.json()["code"]) == (404, NOT_FOUND)
    assert "Payments" not in unseen.text
    assert "PMT" not in unseen.text
    assert unseen.json() == missing.json()
    assert missing.status_code == 404


# --- Mutations: 403 for what the user sees but may not do ---------------------------------------


@pytest.mark.parametrize("who", ["project_member", "project_admin", "org_admin"])
async def test_a_member_level_mutation_is_allowed_and_applied(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    w = await world()
    await as_(client, w, who)

    response = await client.post(
        f"/test/authz/projects/{w.project.id}/rename", json={"name": "Billing"}
    )

    assert (response.status_code, response.json()["name"]) == (200, "Billing")
    assert (await stored(session, w.project)).name == "Billing"


@pytest.mark.parametrize(
    ("who", "status", "code"),
    [
        ("project_viewer", 403, "forbidden"),
        ("org_member", 404, NOT_FOUND),
        ("workspace_member", 404, NOT_FOUND),
        ("nobody", 404, NOT_FOUND),
    ],
)
async def test_a_denied_mutation_changes_nothing(
    client: AsyncClient, session: AsyncSession, who: str, status: int, code: str
) -> None:
    w = await world()
    await as_(client, w, who)

    response = await client.post(
        f"/test/authz/projects/{w.project.id}/rename", json={"name": "Billing"}
    )

    assert (response.status_code, response.json()["code"]) == (status, code)
    assert (await stored(session, w.project)).name == "Payments"


async def test_an_unregistered_action_is_denied_even_to_a_system_admin(
    client: AsyncClient,
) -> None:
    w = await world()
    await as_(client, w, "system_admin")

    response = await client.post(f"/test/authz/projects/{w.project.id}/unregistered")

    assert (response.status_code, response.json()["code"]) == (403, "forbidden")


# --- The archived project -----------------------------------------------------------------------


@pytest.mark.parametrize("who", ["project_admin", "system_admin"])
async def test_a_mutation_in_an_archived_project_is_403_and_changes_nothing(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    w = await world(archived=True)
    await as_(client, w, who)

    response = await client.post(
        f"/test/authz/projects/{w.project.id}/rename", json={"name": "Billing"}
    )

    assert (response.status_code, response.json()["code"]) == (403, "forbidden")
    assert (await stored(session, w.project)).name == "Payments"


async def test_a_project_admin_can_unarchive_an_archived_project(
    client: AsyncClient, session: AsyncSession
) -> None:
    w = await world(archived=True)
    await as_(client, w, "project_admin")

    response = await client.post(f"/test/authz/projects/{w.project.id}/unarchive")

    assert response.status_code == 200
    assert (await stored(session, w.project)).archived_at is None


async def test_a_project_member_cannot_unarchive(
    client: AsyncClient, session: AsyncSession
) -> None:
    w = await world(archived=True)
    await as_(client, w, "project_member")

    response = await client.post(f"/test/authz/projects/{w.project.id}/unarchive")

    assert (response.status_code, response.json()["code"]) == (403, "forbidden")
    assert (await stored(session, w.project)).archived_at == datetime(2026, 10, 1, tzinfo=UTC)


async def test_an_archived_project_can_still_be_read(client: AsyncClient) -> None:
    w = await world(archived=True)
    await as_(client, w, "project_viewer")

    response = await client.get(f"/test/authz/projects/{w.project.id}")

    assert (response.status_code, response.json()["name"]) == (200, "Payments")


# --- Module gating (design-doc §5; F7) ----------------------------------------------------------


async def test_a_disabled_module_is_404_even_for_a_project_admin(client: AsyncClient) -> None:
    w = await world(modules=[ProjectModule.GITHUB.value])
    await as_(client, w, "project_admin")

    response = await client.get(f"/test/authz/projects/{w.project.id}/sprints")

    assert (response.status_code, response.json()["code"]) == (404, NOT_FOUND)
    assert "Payments" not in response.text


async def test_an_enabled_module_is_reachable(client: AsyncClient) -> None:
    w = await world(modules=[ProjectModule.SPRINTS.value])
    await as_(client, w, "project_viewer")

    response = await client.get(f"/test/authz/projects/{w.project.id}/sprints")

    assert (response.status_code, response.json()["name"]) == (200, "Payments")


@pytest.mark.parametrize(
    ("modules", "status", "code"),
    [
        ([ProjectModule.GITHUB.value], 404, NOT_FOUND),  # gated first: never reaches authorize()
        ([ProjectModule.SPRINTS.value], 403, "forbidden"),  # enabled: authorize() denies
    ],
)
async def test_module_gating_runs_before_authorize(
    client: AsyncClient, modules: list[str], status: int, code: str
) -> None:
    w = await world(modules=modules)
    await as_(client, w, "project_viewer")

    response = await client.post(f"/test/authz/projects/{w.project.id}/sprints")

    assert (response.status_code, response.json()["code"]) == (status, code)


async def test_module_gating_hides_a_project_the_user_cannot_see_the_same_way(
    client: AsyncClient,
) -> None:
    w = await world(modules=[ProjectModule.SPRINTS.value])
    await as_(client, w, "nobody")

    response = await client.get(f"/test/authz/projects/{w.project.id}/sprints")

    assert (response.status_code, response.json()["code"]) == (404, NOT_FOUND)
    assert "Payments" not in response.text


# --- Org level: creating a project (design-doc §5, "Org roles") --------------------------------


@pytest.mark.parametrize("who", ["org_member", "org_owner", "workspace_admin", "system_admin"])
async def test_an_org_member_or_admin_above_may_create_a_project(
    client: AsyncClient, who: str
) -> None:
    w = await world()
    await as_(client, w, who)

    response = await client.post(f"/test/authz/orgs/{w.org.id}/create-project")

    assert (response.status_code, response.json()["name"]) == (200, "Bolt Foods")


async def test_a_user_linked_to_the_org_only_by_a_project_may_not_create_one(
    client: AsyncClient,
) -> None:
    w = await world()
    await as_(client, w, "project_admin")

    response = await client.post(f"/test/authz/orgs/{w.org.id}/create-project")

    assert (response.status_code, response.json()["code"]) == (403, "forbidden")


@pytest.mark.parametrize("who", ["other_org_admin", "other_workspace_owner", "nobody"])
async def test_a_user_of_another_org_gets_404_for_the_org(client: AsyncClient, who: str) -> None:
    w = await world()
    await as_(client, w, who)

    response = await client.post(f"/test/authz/orgs/{w.org.id}/create-project")

    assert (response.status_code, response.json()["code"]) == (404, NOT_FOUND)
    assert "Bolt Foods" not in response.text


# --- Workspace pages (workspace.view, DL-45) ----------------------------------------------------


@pytest.mark.parametrize("who", ["workspace_owner", "workspace_admin", "system_admin"])
async def test_the_workspace_pages_are_for_its_owners_admins_and_system_admins(
    client: AsyncClient, who: str
) -> None:
    w = await world()
    await as_(client, w, who)

    response = await client.get(f"/test/authz/workspaces/{w.workspace.id}")

    assert (response.status_code, response.json()["name"]) == (200, "Acme Consulting")


@pytest.mark.parametrize(
    "who", ["workspace_member", "org_owner", "project_admin", "other_workspace_owner", "nobody"]
)
async def test_the_workspace_pages_are_404_to_everyone_else(client: AsyncClient, who: str) -> None:
    w = await world()
    await as_(client, w, who)

    response = await client.get(f"/test/authz/workspaces/{w.workspace.id}")

    assert (response.status_code, response.json()["code"]) == (404, NOT_FOUND)
    assert "Acme Consulting" not in response.text
