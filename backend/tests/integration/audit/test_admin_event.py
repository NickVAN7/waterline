"""`log_admin_event()` (app/audit/admin_event.py; design-doc §10.1)."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.admin_event import SecretInDetailsError, log_admin_event
from app.enums import AuditAction, AuditEntityType
from app.models.audit_event import AuditEvent
from tests.factories.org import OrganizationFactory
from tests.factories.user import UserFactory

pytestmark = pytest.mark.anyio


async def count_events(session: AsyncSession) -> int:
    return await session.scalar(select(func.count()).select_from(AuditEvent)) or 0


async def test_records_the_event_with_its_scope_and_details(session: AsyncSession) -> None:
    org = await OrganizationFactory.create_async()
    actor, target = await UserFactory.create_batch_async(2)

    log_admin_event(
        session,
        action=AuditAction.ORG_MEMBER_ROLE_CHANGED,
        actor_id=actor.id,
        workspace_id=org.workspace_id,
        organization_id=org.id,
        target_user_id=target.id,
        entity_type=AuditEntityType.ORGANIZATION,
        entity_id=org.id,
        details={"old_role": "member", "new_role": "admin"},
    )
    await session.flush()
    session.expunge_all()

    stored = await session.scalar(select(AuditEvent))
    assert stored is not None
    assert (
        stored.action,
        stored.actor_id,
        stored.workspace_id,
        stored.organization_id,
        stored.project_id,
        stored.target_user_id,
        stored.entity_type,
        stored.entity_id,
        stored.details,
    ) == (
        AuditAction.ORG_MEMBER_ROLE_CHANGED,
        actor.id,
        org.workspace_id,
        org.id,
        None,
        target.id,
        AuditEntityType.ORGANIZATION,
        org.id,
        {"old_role": "member", "new_role": "admin"},
    )


async def test_an_instance_level_event_from_the_cli_has_no_actor_or_workspace(
    session: AsyncSession,
) -> None:
    target = await UserFactory.create_async()

    log_admin_event(
        session,
        action=AuditAction.SYSTEM_ADMIN_GRANTED,
        actor_id=None,
        workspace_id=None,
        target_user_id=target.id,
    )
    await session.flush()

    stored = await session.scalar(select(AuditEvent))
    assert stored is not None
    assert (stored.actor_id, stored.workspace_id, stored.details) == (None, None, {})


async def test_it_neither_flushes_nor_commits(session: AsyncSession) -> None:
    event = log_admin_event(
        session, action=AuditAction.USER_CREATED, actor_id=None, workspace_id=None
    )

    assert event in session.new  # added, not written: it goes with the request's transaction


async def test_it_rolls_back_with_the_change_it_records(session: AsyncSession) -> None:
    savepoint = await session.begin_nested()
    log_admin_event(session, action=AuditAction.USER_CREATED, actor_id=None, workspace_id=None)
    await session.flush()
    await savepoint.rollback()

    assert await count_events(session) == 0


@pytest.mark.parametrize(
    "details",
    [
        {"password": "hunter2-hunter2"},
        {"new_password_hash": "$argon2id$..."},
        {"Token": "abc"},
        {"user": {"api_secret": "x"}},
        {"changes": [{"field": "name"}, {"session_token": "y"}]},
    ],
)
async def test_details_never_hold_passwords_hashes_or_tokens(
    session: AsyncSession, details: dict[str, object]
) -> None:
    with pytest.raises(SecretInDetailsError):
        log_admin_event(
            session,
            action=AuditAction.PASSWORD_RESET,
            actor_id=None,
            workspace_id=None,
            details=details,  # pyright: ignore[reportArgumentType]
        )

    assert not session.new


async def test_details_that_merely_mention_a_password_reset_are_fine(
    session: AsyncSession,
) -> None:
    log_admin_event(
        session,
        action=AuditAction.PASSWORD_RESET,
        actor_id=None,
        workspace_id=None,
        details={"reason": "password reset requested by phone", "fields": ["name", "email"]},
    )
    await session.flush()

    assert await count_events(session) == 1


async def test_a_flag_named_after_a_password_is_fine(session: AsyncSession) -> None:
    # A secret is text; `must_change_password: true` says nothing secret.
    log_admin_event(
        session,
        action=AuditAction.USER_CREATED,
        actor_id=None,
        workspace_id=None,
        details={"must_change_password": True, "password_reset_count": 1},
    )
    await session.flush()

    assert await count_events(session) == 1
