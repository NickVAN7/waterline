"""The authorization context loaded from real memberships (build plan, "Authorization (§5)",
"Authorization context"), and list scoping applied in a query (design-doc §5, "Reads are
authorized too"; §4, "Visibility")."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.context import AuthzContext, ProjectAccess
from app.authz.scoping import org_scope, project_scope
from app.enums import OrgRole, ProjectRole, WorkspaceRole
from app.models.org import Organization
from app.models.project import Project
from app.models.user import User
from app.models.workspace import Workspace
from app.repositories.user import UserRepository
from tests.factories.org import MembershipFactory, OrganizationFactory
from tests.factories.project import ProjectFactory, ProjectMembershipFactory
from tests.factories.user import UserFactory
from tests.factories.workspace import WorkspaceFactory, WorkspaceMembershipFactory
from tests.support.authz import scope_filter

pytestmark = [pytest.mark.anyio, pytest.mark.security]


async def test_the_context_holds_every_membership_of_the_user_and_no_one_elses(
    session: AsyncSession,
) -> None:
    staff_of = await WorkspaceFactory.create_async()
    other_workspace = await WorkspaceFactory.create_async()
    owned_org = await OrganizationFactory.create_async(workspace=staff_of)
    # The project sits in another workspace's org: its ProjectAccess comes from the project row.
    far_org = await OrganizationFactory.create_async(workspace=other_workspace)
    viewed = await ProjectFactory.create_async(organization=far_org)
    user = await UserFactory.create_async(is_system_admin=False)
    await WorkspaceMembershipFactory.create_async(
        workspace=staff_of, user=user, role=WorkspaceRole.ADMIN
    )
    await MembershipFactory.create_async(organization=owned_org, user=user, role=OrgRole.OWNER)
    await ProjectMembershipFactory.create_async(project=viewed, user=user, role=ProjectRole.VIEWER)
    someone_else = await UserFactory.create_async()
    await WorkspaceMembershipFactory.create_async(
        workspace=other_workspace, user=someone_else, role=WorkspaceRole.OWNER
    )
    await MembershipFactory.create_async(
        organization=far_org, user=someone_else, role=OrgRole.ADMIN
    )
    await ProjectMembershipFactory.create_async(
        project=await ProjectFactory.create_async(organization=owned_org),
        user=someone_else,
        role=ProjectRole.ADMIN,
    )

    ctx = await UserRepository(session).authz_context(user)

    assert ctx == AuthzContext(
        user_id=user.id,
        is_system_admin=False,
        workspace_roles={staff_of.id: WorkspaceRole.ADMIN},
        org_roles={owned_org.id: OrgRole.OWNER},
        projects={viewed.id: ProjectAccess(ProjectRole.VIEWER, far_org.id, other_workspace.id)},
    )


async def test_the_context_carries_the_system_admin_flag(session: AsyncSession) -> None:
    admin = await UserFactory.create_async(is_system_admin=True)

    ctx = await UserRepository(session).authz_context(admin)

    assert ctx == AuthzContext(user_id=admin.id, is_system_admin=True)


async def test_a_user_with_no_membership_has_an_empty_context(session: AsyncSession) -> None:
    await ProjectMembershipFactory.create_async(role=ProjectRole.ADMIN)  # someone else's
    user = await UserFactory.create_async(is_system_admin=False)

    ctx = await UserRepository(session).authz_context(user)

    assert ctx == AuthzContext(user_id=user.id)


# --- Scoping applied in a query -----------------------------------------------------------------


async def visible_project_keys(session: AsyncSession, user: User) -> set[str]:
    scope = project_scope(await UserRepository(session).authz_context(user))
    where = scope_filter(scope, Project.id, Project.workspace_id, Project.organization_id)
    return set(await session.scalars(select(Project.key).where(where)))


async def visible_org_slugs(session: AsyncSession, user: User) -> set[str]:
    scope = org_scope(await UserRepository(session).authz_context(user))
    where = scope_filter(scope, Organization.id, Organization.workspace_id)
    return set(await session.scalars(select(Organization.slug).where(where)))


async def layout() -> tuple[Workspace, Organization, Organization, Organization]:
    """Workspace one: orgs acme (AC1, AC2) and bolt (BO1). Workspace two: org cove (CO1)."""
    one = await WorkspaceFactory.create_async()
    two = await WorkspaceFactory.create_async()
    acme = await OrganizationFactory.create_async(workspace=one, slug="acme")
    bolt = await OrganizationFactory.create_async(workspace=one, slug="bolt")
    cove = await OrganizationFactory.create_async(workspace=two, slug="cove")
    await ProjectFactory.create_async(organization=acme, key="AC1")
    await ProjectFactory.create_async(organization=acme, key="AC2")
    await ProjectFactory.create_async(organization=bolt, key="BO1")
    await ProjectFactory.create_async(organization=cove, key="CO1")
    return one, acme, bolt, cove


async def test_a_list_shows_an_org_admin_their_orgs_projects_and_their_own_memberships(
    session: AsyncSession,
) -> None:
    _, acme, _, cove = await layout()
    user = await UserFactory.create_async(is_system_admin=False)
    await MembershipFactory.create_async(organization=acme, user=user, role=OrgRole.ADMIN)
    await MembershipFactory.create_async(organization=cove, user=user, role=OrgRole.MEMBER)
    bo1 = await session.scalar(select(Project).where(Project.key == "BO1"))
    await ProjectMembershipFactory.create_async(project=bo1, user=user, role=ProjectRole.VIEWER)

    assert await visible_project_keys(session, user) == {"AC1", "AC2", "BO1"}
    assert await visible_org_slugs(session, user) == {"acme", "bolt", "cove"}


async def test_a_list_shows_a_workspace_admin_everything_in_their_workspace_only(
    session: AsyncSession,
) -> None:
    one, *_ = await layout()
    user = await UserFactory.create_async(is_system_admin=False)
    await WorkspaceMembershipFactory.create_async(
        workspace=one, user=user, role=WorkspaceRole.ADMIN
    )

    assert await visible_project_keys(session, user) == {"AC1", "AC2", "BO1"}
    assert await visible_org_slugs(session, user) == {"acme", "bolt"}


async def test_a_list_shows_a_workspace_member_nothing_by_staff_role_alone(
    session: AsyncSession,
) -> None:
    one, *_ = await layout()
    user = await UserFactory.create_async(is_system_admin=False)
    await WorkspaceMembershipFactory.create_async(
        workspace=one, user=user, role=WorkspaceRole.MEMBER
    )

    assert await visible_project_keys(session, user) == set()
    assert await visible_org_slugs(session, user) == set()


async def test_a_list_shows_a_system_admin_everything(session: AsyncSession) -> None:
    await layout()
    admin = await UserFactory.create_async(is_system_admin=True)

    assert await visible_project_keys(session, admin) == {"AC1", "AC2", "BO1", "CO1"}
    assert await visible_org_slugs(session, admin) == {"acme", "bolt", "cove"}
