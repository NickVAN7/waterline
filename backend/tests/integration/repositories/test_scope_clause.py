"""`scope_clause` (app/repositories/base.py) on real rows, with the org column: the `WHERE` every
project list builds from `project_scope` (design-doc §4, "Visibility"; §5, "Reads are authorized
too"). The spec tests check `Scope` itself; this checks the SQL a repository makes of it."""

from dataclasses import dataclass

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.scoping import project_scope
from app.enums import OrgRole, ProjectRole, WorkspaceRole
from app.models.org import Organization
from app.models.project import Project
from app.models.user import User
from app.models.workspace import Workspace
from app.repositories.base import scope_clause
from app.repositories.user import UserRepository
from tests.factories.org import MembershipFactory, OrganizationFactory
from tests.factories.project import ProjectFactory, ProjectMembershipFactory
from tests.factories.user import UserFactory
from tests.factories.workspace import WorkspaceFactory, WorkspaceMembershipFactory

pytestmark = [pytest.mark.anyio, pytest.mark.security]


@dataclass(frozen=True)
class Tenancy:
    w: Workspace
    a: Organization


@pytest.fixture
async def tenancy(session: AsyncSession) -> Tenancy:
    """Workspace W: org A with projects AAA and AAB, org B with project BBA. Workspace W2: org C
    with project CCA."""
    w = await WorkspaceFactory.create_async()
    w2 = await WorkspaceFactory.create_async()
    a = await OrganizationFactory.create_async(workspace=w)
    b = await OrganizationFactory.create_async(workspace=w)
    c = await OrganizationFactory.create_async(workspace=w2)
    await ProjectFactory.create_async(key="AAA", organization=a, workspace_id=w.id)
    await ProjectFactory.create_async(key="AAB", organization=a, workspace_id=w.id)
    await ProjectFactory.create_async(key="BBA", organization=b, workspace_id=w.id)
    await ProjectFactory.create_async(key="CCA", organization=c, workspace_id=w2.id)
    return Tenancy(w=w, a=a)


async def project(session: AsyncSession, key: str) -> Project:
    return (await session.execute(select(Project).where(Project.key == key))).scalar_one()


async def keys(session: AsyncSession, user: User) -> list[str]:
    ctx = await UserRepository(session).authz_context(user)
    clause = scope_clause(
        project_scope(ctx), Project.id, Project.workspace_id, Project.organization_id
    )
    return list(await session.scalars(select(Project.key).where(clause).order_by(Project.key)))


async def test_an_org_admin_sees_every_project_of_their_org_only(
    session: AsyncSession, tenancy: Tenancy
) -> None:
    user = await UserFactory.create_async()
    await MembershipFactory.create_async(organization=tenancy.a, user=user, role=OrgRole.ADMIN)

    assert await keys(session, user) == ["AAA", "AAB"]


async def test_an_org_member_sees_none_of_its_projects(
    session: AsyncSession, tenancy: Tenancy
) -> None:
    user = await UserFactory.create_async()
    await MembershipFactory.create_async(organization=tenancy.a, user=user, role=OrgRole.MEMBER)

    assert await keys(session, user) == []


async def test_a_workspace_admin_sees_every_project_of_their_workspace_only(
    session: AsyncSession, tenancy: Tenancy
) -> None:
    user = await UserFactory.create_async()
    await WorkspaceMembershipFactory.create_async(
        workspace=tenancy.w, user=user, role=WorkspaceRole.ADMIN
    )

    assert await keys(session, user) == ["AAA", "AAB", "BBA"]


async def test_a_project_viewer_sees_that_project_only(
    session: AsyncSession, tenancy: Tenancy
) -> None:
    user = await UserFactory.create_async()
    await ProjectMembershipFactory.create_async(
        project=await project(session, "BBA"), user=user, role=ProjectRole.VIEWER
    )

    assert await keys(session, user) == ["BBA"]


async def test_someone_with_no_membership_sees_nothing(
    session: AsyncSession, tenancy: Tenancy
) -> None:
    assert await keys(session, await UserFactory.create_async()) == []


async def test_a_system_admin_sees_every_project(session: AsyncSession, tenancy: Tenancy) -> None:
    user = await UserFactory.create_async(is_system_admin=True)

    assert await keys(session, user) == ["AAA", "AAB", "BBA", "CCA"]
