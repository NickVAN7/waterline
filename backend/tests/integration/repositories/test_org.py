"""`OrgRepository.visible` with the user's `org_scope`: the orgs `/me` lists for the org
switcher (design-doc §4, "Visibility")."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.scoping import org_scope
from app.enums import OrgRole, WorkspaceRole
from app.models.org import Organization
from app.models.user import User
from app.models.workspace import Workspace
from app.repositories.org import OrgRepository
from app.repositories.user import UserRepository
from tests.factories.org import MembershipFactory, OrganizationFactory
from tests.factories.project import ProjectFactory, ProjectMembershipFactory
from tests.factories.user import UserFactory
from tests.factories.workspace import WorkspaceFactory, WorkspaceMembershipFactory

pytestmark = [pytest.mark.anyio, pytest.mark.security]


async def visible(session: AsyncSession, user: User) -> list[tuple[str, OrgRole | None]]:
    """The orgs listed for `user`, through the user's real authorization context and org scope."""
    ctx = await UserRepository(session).authz_context(user)
    rows = await OrgRepository(session).visible(org_scope(ctx), user.id)
    return [(org.name, role) for org, role in rows]


async def org_in(workspace: Workspace, name: str) -> Organization:
    return await OrganizationFactory.create_async(workspace=workspace, name=name)


@pytest.fixture
async def acme(session: AsyncSession) -> Workspace:
    """A workspace with orgs Bolt and Cove, beside another workspace with org Dune."""
    workspace = await WorkspaceFactory.create_async()
    await org_in(workspace, "Cove")
    await org_in(workspace, "Bolt")
    await org_in(await WorkspaceFactory.create_async(), "Dune")
    return workspace


async def test_an_org_member_sees_their_org_with_their_role(
    session: AsyncSession, acme: Workspace
) -> None:
    user = await UserFactory.create_async()
    bolt = await org_in(acme, "Bolt 2")
    await MembershipFactory.create_async(organization=bolt, user=user, role=OrgRole.OWNER)

    assert await visible(session, user) == [("Bolt 2", OrgRole.OWNER)]


async def test_a_project_member_sees_the_projects_org_with_no_role(
    session: AsyncSession, acme: Workspace
) -> None:
    user = await UserFactory.create_async()
    eden = await org_in(acme, "Eden")
    project = await ProjectFactory.create_async(organization=eden, workspace_id=acme.id)
    await ProjectMembershipFactory.create_async(project=project, user=user)

    assert await visible(session, user) == [("Eden", None)]


@pytest.mark.parametrize("role", [WorkspaceRole.OWNER, WorkspaceRole.ADMIN])
async def test_a_workspace_owner_or_admin_sees_every_org_in_it(
    session: AsyncSession, acme: Workspace, role: WorkspaceRole
) -> None:
    user = await UserFactory.create_async()
    await WorkspaceMembershipFactory.create_async(workspace=acme, user=user, role=role)

    assert await visible(session, user) == [("Bolt", None), ("Cove", None)]


async def test_a_workspace_member_sees_only_the_orgs_they_are_assigned_to(
    session: AsyncSession, acme: Workspace
) -> None:
    user = await UserFactory.create_async()
    await WorkspaceMembershipFactory.create_async(
        workspace=acme, user=user, role=WorkspaceRole.MEMBER
    )

    assert await visible(session, user) == []


async def test_a_system_admin_sees_every_org_in_every_workspace(
    session: AsyncSession, acme: Workspace
) -> None:
    user = await UserFactory.create_async(is_system_admin=True)

    assert await visible(session, user) == [("Bolt", None), ("Cove", None), ("Dune", None)]


async def test_a_role_shown_is_only_the_users_own(session: AsyncSession, acme: Workspace) -> None:
    """Another user's membership in an org doesn't show it, or lend its role."""
    user = await UserFactory.create_async()
    eden = await org_in(acme, "Eden")
    await MembershipFactory.create_async(organization=eden, role=OrgRole.OWNER)
    await WorkspaceMembershipFactory.create_async(
        workspace=acme, user=user, role=WorkspaceRole.ADMIN
    )

    assert await visible(session, user) == [("Bolt", None), ("Cove", None), ("Eden", None)]


async def test_another_users_project_membership_shows_nothing(
    session: AsyncSession, acme: Workspace
) -> None:
    user = await UserFactory.create_async()
    eden = await org_in(acme, "Eden")
    project = await ProjectFactory.create_async(organization=eden, workspace_id=acme.id)
    await ProjectMembershipFactory.create_async(project=project)

    assert await visible(session, user) == []
