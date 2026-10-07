"""`workspace` and `workspace_membership` constraints (schema-doc)."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import WorkspaceRole
from tests.factories.user import UserFactory
from tests.factories.workspace import WorkspaceFactory, WorkspaceMembershipFactory

pytestmark = pytest.mark.anyio


async def test_workspace_slug_is_unique(session: AsyncSession) -> None:
    await WorkspaceFactory.create_async(slug="acme")

    with pytest.raises(IntegrityError, match="uq_workspace_slug"):
        await WorkspaceFactory.create_async(slug="acme")


async def test_user_holds_one_membership_per_workspace(session: AsyncSession) -> None:
    workspace = await WorkspaceFactory.create_async()
    user = await UserFactory.create_async()
    await WorkspaceMembershipFactory.create_async(
        workspace=workspace, user=user, role=WorkspaceRole.MEMBER
    )

    with pytest.raises(IntegrityError, match="uq_workspace_membership_workspace_id_user_id"):
        await WorkspaceMembershipFactory.create_async(
            workspace=workspace, user=user, role=WorkspaceRole.ADMIN
        )


async def test_user_can_be_staff_in_two_workspaces(session: AsyncSession) -> None:
    user = await UserFactory.create_async()
    await WorkspaceMembershipFactory.create_async(user=user)
    await WorkspaceMembershipFactory.create_async(user=user)

    count = await session.scalar(text("SELECT count(*) FROM workspace_membership"))
    assert count == 2


async def test_workspace_role_outside_the_enum_is_rejected(session: AsyncSession) -> None:
    membership = await WorkspaceMembershipFactory.create_async()

    with pytest.raises(IntegrityError, match="ck_workspace_membership_role"):
        await session.execute(
            text("UPDATE workspace_membership SET role = 'viewer' WHERE id = :id"),
            {"id": membership.id},
        )
