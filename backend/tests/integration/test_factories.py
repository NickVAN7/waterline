"""Every model factory persists a valid row, building its required parents (testing-strategy.md,
"Test data"; TD-5): a factory that broke a constraint or left a parent out would fail every test
that uses it, far from the cause."""

import re
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.approval import Approval, ApprovalRequest
from app.models.audit import ActivityLog
from app.models.audit_event import AuditEvent
from app.models.auth import UserSession
from app.models.numbering import ProjectCounter
from app.models.org import Membership, Organization
from app.models.project import Project, ProjectMembership
from app.models.requirement import Requirement, RequirementRevision
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMembership
from tests.factories import BaseFactory, fake_slug, reset_factories
from tests.factories.approval import ApprovalFactory, ApprovalRequestFactory
from tests.factories.audit import ActivityLogFactory
from tests.factories.audit_event import AuditEventFactory
from tests.factories.auth import UserSessionFactory
from tests.factories.numbering import ProjectCounterFactory
from tests.factories.org import MembershipFactory, OrganizationFactory
from tests.factories.project import ProjectFactory, ProjectMembershipFactory
from tests.factories.requirement import RequirementFactory, RequirementRevisionFactory
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
        (RequirementFactory, Requirement),
        (RequirementRevisionFactory, RequirementRevision),
        (ApprovalRequestFactory, ApprovalRequest),
        (ApprovalFactory, Approval),
        (ActivityLogFactory, ActivityLog),
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


def test_unique_values_repeat_after_each_reset() -> None:
    """Each test starts from the same values: `unique` doesn't skip what earlier tests drew."""
    reset_factories()
    first = RequirementFactory.build().number
    reset_factories()

    assert RequirementFactory.build().number == first
