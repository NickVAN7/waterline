"""`scope_clause` with a content scope, on real rows, through `ProjectRepository.visible` (S2-C4;
design-doc §3.1, "Export-controlled projects (who sees content)"; §5, "Reads are authorized
too"; S2-plan, threat model: "Export-controlled content leaking through a list…").

A content scope (`Scope.content`) reaches an export-controlled project only through `ids` (the
explicit memberships); `everything`, an org, or a workspace (inherited admin) reach only the
others. `project_scope` (management: "the project in lists", §3.1) still reaches every project.
"""

import uuid
from dataclasses import dataclass

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.scoping import Scope, content_scope, project_scope
from app.enums import OrgRole, ProjectRole, WorkspaceRole
from app.models.org import Organization
from app.models.project import Project
from app.models.user import User
from app.models.workspace import Workspace
from app.repositories.project import ProjectRepository
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
    projects: dict[str, Project]


@pytest.fixture
async def tenancy(session: AsyncSession) -> Tenancy:
    """Workspace W: org A with AAA (export-controlled), AAB (no categories), AAC (pii), and AAD
    (pii and export-controlled); org B with BBA (export-controlled). Workspace W2: org C with
    CCA (no categories)."""
    w = await WorkspaceFactory.create_async()
    w2 = await WorkspaceFactory.create_async()
    a = await OrganizationFactory.create_async(workspace=w)
    b = await OrganizationFactory.create_async(workspace=w)
    c = await OrganizationFactory.create_async(workspace=w2)
    layout: list[tuple[str, Organization, list[str]]] = [
        ("AAA", a, ["export_controlled"]),
        ("AAB", a, []),
        ("AAC", a, ["pii"]),
        ("AAD", a, ["pii", "export_controlled"]),
        ("BBA", b, ["export_controlled"]),
        ("CCA", c, []),
    ]
    projects = {
        key: await ProjectFactory.create_async(
            key=key, organization=org, workspace_id=org.workspace_id, restriction_categories=cats
        )
        for key, org, cats in layout
    }
    return Tenancy(w=w, a=a, projects=projects)


async def listed(session: AsyncSession, scope: Scope) -> list[str]:
    statement = ProjectRepository(session).visible(scope).order_by(Project.key)
    return [project.key for project in await session.scalars(statement)]


async def content_keys(session: AsyncSession, user: User) -> list[str]:
    ctx = await UserRepository(session).authz_context(user)
    return await listed(session, content_scope(ctx))


async def explicit(t: Tenancy, user: User, key: str) -> None:
    await ProjectMembershipFactory.create_async(
        project=t.projects[key], user=user, role=ProjectRole.VIEWER
    )


def ids(t: Tenancy, *keys: str) -> frozenset[uuid.UUID]:
    return frozenset(t.projects[key].id for key in keys)


# --- content_scope through visible() -----------------------------------------------------------


@pytest.mark.parametrize("role", [OrgRole.ADMIN, OrgRole.OWNER])
async def test_an_org_admins_content_list_leaves_out_export_controlled_projects(
    session: AsyncSession, tenancy: Tenancy, role: OrgRole
) -> None:
    user = await UserFactory.create_async()
    await MembershipFactory.create_async(organization=tenancy.a, user=user, role=role)

    assert await content_keys(session, user) == ["AAB", "AAC"]


async def test_an_org_admin_with_an_explicit_membership_sees_that_projects_content(
    session: AsyncSession, tenancy: Tenancy
) -> None:
    user = await UserFactory.create_async()
    await MembershipFactory.create_async(organization=tenancy.a, user=user, role=OrgRole.ADMIN)
    await explicit(tenancy, user, "AAA")

    assert await content_keys(session, user) == ["AAA", "AAB", "AAC"]


@pytest.mark.parametrize("role", [WorkspaceRole.ADMIN, WorkspaceRole.OWNER])
async def test_a_workspace_admins_content_list_leaves_out_export_controlled_projects(
    session: AsyncSession, tenancy: Tenancy, role: WorkspaceRole
) -> None:
    user = await UserFactory.create_async()
    await WorkspaceMembershipFactory.create_async(workspace=tenancy.w, user=user, role=role)

    assert await content_keys(session, user) == ["AAB", "AAC"]


async def test_a_system_admins_content_list_leaves_out_export_controlled_projects(
    session: AsyncSession, tenancy: Tenancy
) -> None:
    user = await UserFactory.create_async(is_system_admin=True)

    assert await content_keys(session, user) == ["AAB", "AAC", "CCA"]


async def test_a_system_admin_with_an_explicit_membership_sees_that_projects_content(
    session: AsyncSession, tenancy: Tenancy
) -> None:
    user = await UserFactory.create_async(is_system_admin=True)
    await explicit(tenancy, user, "BBA")

    assert await content_keys(session, user) == ["AAB", "AAC", "BBA", "CCA"]


@pytest.mark.parametrize("key", ["AAA", "AAD", "AAB"])
async def test_an_explicit_member_sees_their_projects_content(
    session: AsyncSession, tenancy: Tenancy, key: str
) -> None:
    user = await UserFactory.create_async()
    await explicit(tenancy, user, key)

    assert await content_keys(session, user) == [key]


async def test_the_project_list_still_holds_export_controlled_projects_for_inherited_admins(
    session: AsyncSession, tenancy: Tenancy
) -> None:
    """§3.1: management access keeps "the project in lists" (`project_scope`, no content)."""
    user = await UserFactory.create_async()
    await MembershipFactory.create_async(organization=tenancy.a, user=user, role=OrgRole.ADMIN)
    ctx = await UserRepository(session).authz_context(user)

    assert await listed(session, project_scope(ctx)) == ["AAA", "AAB", "AAC", "AAD"]


# --- scope_clause on hand-built content scopes -------------------------------------------------


async def test_a_content_scope_reaches_export_controlled_projects_only_by_id(
    session: AsyncSession, tenancy: Tenancy
) -> None:
    scope = Scope(content=True, ids=ids(tenancy, "AAA"), organization_ids=frozenset({tenancy.a.id}))

    assert await listed(session, scope) == ["AAA", "AAB", "AAC"]


async def test_a_content_scope_over_a_workspace_leaves_out_export_controlled_projects(
    session: AsyncSession, tenancy: Tenancy
) -> None:
    scope = Scope(content=True, workspace_ids=frozenset({tenancy.w.id}))

    assert await listed(session, scope) == ["AAB", "AAC"]


async def test_a_content_scope_over_everything_leaves_out_export_controlled_projects(
    session: AsyncSession, tenancy: Tenancy
) -> None:
    assert await listed(session, Scope(content=True, everything=True)) == ["AAB", "AAC", "CCA"]


async def test_a_content_scope_over_everything_still_reaches_its_ids(
    session: AsyncSession, tenancy: Tenancy
) -> None:
    scope = Scope(content=True, everything=True, ids=ids(tenancy, "BBA"))

    assert await listed(session, scope) == ["AAB", "AAC", "BBA", "CCA"]


async def test_a_scope_without_content_reaches_export_controlled_projects_through_an_org(
    session: AsyncSession, tenancy: Tenancy
) -> None:
    assert await listed(session, Scope(organization_ids=frozenset({tenancy.a.id}))) == [
        "AAA",
        "AAB",
        "AAC",
        "AAD",
    ]
