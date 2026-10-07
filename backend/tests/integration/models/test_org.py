"""`organization` and `membership` constraints (schema-doc)."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import OrgRole
from tests.factories.org import MembershipFactory, OrganizationFactory
from tests.factories.user import UserFactory
from tests.factories.workspace import WorkspaceFactory

pytestmark = pytest.mark.anyio


async def test_org_slug_is_unique_within_its_workspace(session: AsyncSession) -> None:
    workspace = await WorkspaceFactory.create_async()
    await OrganizationFactory.create_async(workspace=workspace, slug="acme")

    with pytest.raises(IntegrityError, match="uq_organization_workspace_id_slug"):
        await OrganizationFactory.create_async(workspace=workspace, slug="acme")


async def test_org_slug_can_repeat_in_another_workspace(session: AsyncSession) -> None:
    await OrganizationFactory.create_async(slug="acme")
    await OrganizationFactory.create_async(slug="acme")

    count = await session.scalar(text("SELECT count(*) FROM organization WHERE slug = 'acme'"))
    assert count == 2


async def test_user_holds_one_membership_per_org(session: AsyncSession) -> None:
    org = await OrganizationFactory.create_async()
    user = await UserFactory.create_async()
    await MembershipFactory.create_async(organization=org, user=user, role=OrgRole.MEMBER)

    with pytest.raises(IntegrityError, match="uq_membership_user_id_organization_id"):
        await MembershipFactory.create_async(organization=org, user=user, role=OrgRole.ADMIN)


async def test_org_role_outside_the_enum_is_rejected(session: AsyncSession) -> None:
    membership = await MembershipFactory.create_async()

    with pytest.raises(IntegrityError, match="ck_membership_role"):
        await session.execute(
            text("UPDATE membership SET role = 'viewer' WHERE id = :id"), {"id": membership.id}
        )
