"""Every model factory persists a valid row, building its required parents (testing-strategy.md,
"Test data"; TD-5): a factory that broke a constraint or left a parent out would fail every test
that uses it, far from the cause."""

import re
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_event import AuditEvent
from app.models.auth import UserSession
from app.models.numbering import ProjectCounter
from app.models.org import Membership, Organization
from app.models.project import Project, ProjectMembership
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMembership
from tests.factories import BaseFactory, fake_slug
from tests.factories.audit_event import AuditEventFactory
from tests.factories.auth import UserSessionFactory
from tests.factories.numbering import ProjectCounterFactory
from tests.factories.org import MembershipFactory, OrganizationFactory
from tests.factories.project import ProjectFactory, ProjectMembershipFactory
from tests.factories.user import UserFactory
from tests.factories.workspace import WorkspaceFactory, WorkspaceMembershipFactory

pytestmark = pytest.mark.anyio


@pytest.mark.parametrize(
    ("factory", "model"),
    [
        (UserFactory, User),
        (UserSessionFactory, UserSession),
        (WorkspaceFactory, Workspace),
        (WorkspaceMembershipFactory, WorkspaceMembership),
        (OrganizationFactory, Organization),
        (MembershipFactory, Membership),
        (ProjectFactory, Project),
        (ProjectMembershipFactory, ProjectMembership),
        (ProjectCounterFactory, ProjectCounter),
        (AuditEventFactory, AuditEvent),
    ],
)
async def test_factory_persists_a_valid_row(
    session: AsyncSession, factory: type[BaseFactory[Any]], model: type[Any]
) -> None:
    await factory.create_async()

    assert await session.scalar(select(func.count()).select_from(model)) == 1


async def test_project_factory_builds_its_org_and_workspace(session: AsyncSession) -> None:
    await ProjectFactory.create_async()

    assert await session.scalar(select(func.count()).select_from(Organization)) == 1
    assert await session.scalar(select(func.count()).select_from(Workspace)) == 1


# Identifier formats from design-doc §3.
SLUG = re.compile(r"^[a-z][a-z0-9-]{1,39}$")
PROJECT_KEY = re.compile(r"^[A-Z][A-Z0-9]{2,5}$")


async def test_user_factory_values_have_realistic_forms(session: AsyncSession) -> None:
    user = await UserFactory.create_async()

    assert SLUG.fullmatch(user.username)
    assert re.fullmatch(r"[a-z0-9.-]+@[a-z0-9.-]+\.[a-z]+", user.email)


async def test_tenancy_factory_values_have_realistic_forms(session: AsyncSession) -> None:
    workspace = await WorkspaceFactory.create_async()
    org = await OrganizationFactory.create_async()
    project = await ProjectFactory.create_async()

    assert SLUG.fullmatch(workspace.slug)
    assert SLUG.fullmatch(org.slug)
    assert PROJECT_KEY.fullmatch(project.key)


def test_fake_slug_stays_within_the_slug_format_for_long_names() -> None:
    slug = fake_slug("The Extremely Long Consolidated Holdings Company of Greater Springfield")

    assert SLUG.fullmatch(slug)
