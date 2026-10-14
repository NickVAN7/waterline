"""The org's last-owner guard between truly parallel transactions (design-doc §5, "Other targeted
rules"; DL-59, DL-67): the org's own owner locks, sabotage-checked against the code without them.
The shared roster code is otherwise covered by the workspace's concurrency tests."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.context import AuthzContext
from app.core.db import SessionMaker
from app.core.errors import ValidationFailedError
from app.enums import OrgRole
from app.models.org import Membership, Organization
from app.schemas.org import MemberRoleUpdate
from app.services.org import OrgService
from tests.factories.org import MembershipFactory, OrganizationFactory
from tests.factories.user import UserFactory
from tests.support.concurrency import committing_factories, run_in_parallel

pytestmark = [
    pytest.mark.anyio,
    pytest.mark.security,
    pytest.mark.concurrency("audit_event", "membership", "organization", "workspace", "user"),
]


async def test_two_org_owners_demoting_each_other_at_once_leave_one_owner(
    concurrency: SessionMaker,
) -> None:
    async with committing_factories(concurrency):
        org = await OrganizationFactory.create_async()
        ann = await UserFactory.create_async()
        bob = await UserFactory.create_async()
        await MembershipFactory.create_async(organization=org, user=ann, role=OrgRole.OWNER)
        await MembershipFactory.create_async(organization=org, user=bob, role=OrgRole.OWNER)
    # Each demotes the other.
    pairs = [(ann, bob), (bob, ann)]

    async def demote(session: AsyncSession, index: int) -> object:
        actor, target = pairs[index]
        ctx = AuthzContext(user_id=actor.id, org_roles={org.id: OrgRole.OWNER})
        loaded = await session.get_one(Organization, org.id)
        return await OrgService(session).change_member_role(
            ctx, loaded, target.id, MemberRoleUpdate(role=OrgRole.ADMIN)
        )

    # The second waits on the first's row locks, then finds one owner left and is refused.
    with pytest.RaisesGroup(pytest.RaisesExc(ValidationFailedError)):
        await run_in_parallel(concurrency, 2, demote)

    async with concurrency() as check:
        roles = list(
            await check.scalars(select(Membership.role).where(Membership.organization_id == org.id))
        )
    assert sorted(roles) == [OrgRole.ADMIN, OrgRole.OWNER]
