"""Two adds of the same person at once (DL-80, TD-23): the loser gets `already_member` on the field
its request used. A staff add (no lock before its check) reaches the unique constraint, which the
roster reports on `email`; a project add locks the project first, so the second waits and its own
check reports on `user_id`. Each sabotage-checked (see the S1-C12 review record)."""

from typing import cast

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.context import AuthzContext
from app.core.db import SessionMaker
from app.core.errors import ValidationFailedError
from app.enums import OrgRole, ProjectRole, WorkspaceRole
from app.models.project import Project, ProjectMembership
from app.models.workspace import Workspace, WorkspaceMembership
from app.schemas.project import ProjectMemberAdd
from app.services.project import ProjectService
from app.services.workspace import WorkspaceService
from tests.factories.org import MembershipFactory, OrganizationFactory
from tests.factories.project import ProjectFactory
from tests.factories.user import UserFactory
from tests.factories.workspace import WorkspaceFactory
from tests.support.concurrency import committing_factories, run_in_parallel

pytestmark = [pytest.mark.anyio, pytest.mark.security]


def field_errors(error: ValidationFailedError) -> list[tuple[object, object]]:
    fields = cast(list[dict[str, object]], error.details["fields"])
    return [(f["loc"], f["type"]) for f in fields]


def already_member_on(field: str) -> pytest.RaisesGroup[ValidationFailedError]:
    return pytest.RaisesGroup(
        pytest.RaisesExc(
            ValidationFailedError,
            check=lambda e: field_errors(e) == [(["body", field], "already_member")],
        )
    )


@pytest.mark.concurrency("audit_event", "workspace_membership", "workspace", "user")
async def test_two_staff_adds_of_one_person_at_once_leave_one_and_report_on_email(
    concurrency: SessionMaker,
) -> None:
    async with committing_factories(concurrency):
        workspace = await WorkspaceFactory.create_async()
        admin = await UserFactory.create_async(is_system_admin=True)
        await UserFactory.create_async(email="bob@acme.example")
    ctx = AuthzContext(user_id=admin.id, is_system_admin=True)

    async def add(session: AsyncSession, _index: int) -> object:
        loaded = await session.get_one(Workspace, workspace.id)
        return await WorkspaceService(session).add_staff(
            ctx, loaded, "bob@acme.example", WorkspaceRole.MEMBER
        )

    with already_member_on("email"):
        await run_in_parallel(concurrency, 2, add)

    async with concurrency() as check:
        staff = await check.scalar(select(func.count()).select_from(WorkspaceMembership))
    assert staff == 1


@pytest.mark.concurrency(
    "audit_event",
    "project_membership",
    "project",
    "membership",
    "organization",
    "workspace",
    "user",
)
async def test_two_project_adds_by_user_id_at_once_leave_one_and_report_on_user_id(
    concurrency: SessionMaker,
) -> None:
    async with committing_factories(concurrency):
        org = await OrganizationFactory.create_async()
        project = await ProjectFactory.create_async(organization=org)
        admin = await UserFactory.create_async(is_system_admin=True)
        bob = await UserFactory.create_async()
        await MembershipFactory.create_async(organization=org, user=bob, role=OrgRole.MEMBER)
    ctx = AuthzContext(user_id=admin.id, is_system_admin=True)

    async def add(session: AsyncSession, _index: int) -> object:
        loaded = await session.get_one(Project, project.id)
        return await ProjectService(session).add_member(
            ctx, loaded, ProjectMemberAdd(user_id=bob.id, role=ProjectRole.MEMBER)
        )

    with already_member_on("user_id"):
        await run_in_parallel(concurrency, 2, add)

    async with concurrency() as check:
        members = await check.scalar(select(func.count()).select_from(ProjectMembership))
    assert members == 1
