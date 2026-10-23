"""The S2-C0d migration's data (DL-134, DL-136): `restricted` becomes `confidential`, the audit
events' action is renamed past the append-only trigger, and no project keeps `sprints` or `github`;
the downgrade brings the names back. Drift and the round trip are in test_migrations.py."""

import uuid

import pytest
from sqlalchemy import URL, text

from app.core.db import create_engine
from tests.integration.test_migrations import migrate

pytestmark = pytest.mark.anyio

BEFORE, THIS = "950169fd7ea9", "a24383c924aa"
WS, ORG = uuid.uuid4(), uuid.uuid4()
SECRET, PLAIN = uuid.uuid4(), uuid.uuid4()

SEED = [
    "INSERT INTO workspace (id, name, slug) VALUES (:ws, 'W', 'w')",
    "INSERT INTO organization (id, workspace_id, name, slug) VALUES (:org, :ws, 'O', 'o')",
    "INSERT INTO project (id, workspace_id, organization_id, key, name, type, enabled_modules,"
    " classification_level) VALUES (:secret, :ws, :org, 'SEC', 'S', 'software',"
    " '{sprints,github}', 'restricted'),"
    " (:plain, :ws, :org, 'PLN', 'P', 'software', '{github}', 'internal')",
    "INSERT INTO audit_event (id, action, details) VALUES"
    " (gen_random_uuid(), 'project_classification_changed', '{}'),"
    " (gen_random_uuid(), 'project_created', '{}')",
]
IDS = {"ws": WS, "org": ORG, "secret": SECRET, "plain": PLAIN}


async def rows(url: URL, sql: str) -> list[tuple[object, ...]]:
    engine = create_engine(url)
    try:
        async with engine.connect() as connection:
            return [tuple(row) for row in await connection.execute(text(sql))]
    finally:
        await engine.dispose()


async def seed(url: URL) -> None:
    engine = create_engine(url)
    try:
        async with engine.begin() as connection:
            for statement in SEED:
                await connection.execute(text(statement), IDS)
    finally:
        await engine.dispose()


async def test_the_upgrade_maps_restricted_renames_the_audit_action_and_drops_the_modules(
    scratch_database: URL,
) -> None:
    await migrate(scratch_database, BEFORE)
    await seed(scratch_database)

    await migrate(scratch_database, THIS)

    assert await rows(
        scratch_database, "SELECT key, restriction_level, enabled_modules FROM project ORDER BY key"
    ) == [("PLN", "internal", []), ("SEC", "confidential", [])]
    assert await rows(scratch_database, "SELECT action FROM audit_event ORDER BY action") == [
        ("project_created",),
        ("project_restriction_changed",),
    ]


async def test_the_upgrade_leaves_audit_event_append_only(scratch_database: URL) -> None:
    """The trigger is switched off for the rename only; left off, audit rows could be edited."""
    await migrate(scratch_database, THIS)

    assert await rows(
        scratch_database,
        "SELECT tgenabled FROM pg_trigger WHERE tgname = 'tr_audit_event_append_only'",
    ) == [("O",)]


async def test_the_downgrade_brings_the_old_names_back(scratch_database: URL) -> None:
    await migrate(scratch_database, BEFORE)
    await seed(scratch_database)
    await migrate(scratch_database, THIS)

    await migrate(scratch_database, "-1", down=True)

    assert await rows(
        scratch_database, "SELECT key, classification_level FROM project ORDER BY key"
    ) == [("PLN", "internal"), ("SEC", "confidential")]
    assert await rows(scratch_database, "SELECT action FROM audit_event ORDER BY action") == [
        ("project_classification_changed",),
        ("project_created",),
    ]
