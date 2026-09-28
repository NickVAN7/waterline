"""add procrastinate schema

Revision ID: 65cb8ec68b54
Revises:
Create Date: 2026-09-28 15:57:24.064677

"""

from collections.abc import Sequence
from pathlib import Path

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "65cb8ec68b54"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# procrastinate's own schema for the pinned version, vendored so this migration never changes
# when procrastinate is upgraded. An upgrade adds a new migration applying procrastinate's
# migration files for the versions in between (docs/developer-guide.md, "Background jobs").
SCHEMA_SQL = Path(__file__).resolve().parents[1] / "sql" / "procrastinate-3.10.0-schema.sql"

# procrastinate ships no uninstall script. Dropping the tables removes their indexes and
# triggers; then every procrastinate function (their names all share the prefix), then the
# types the functions' signatures used.
DROP_SQL = """
DROP TABLE IF EXISTS procrastinate_events, procrastinate_periodic_defers, procrastinate_jobs,
    procrastinate_workers CASCADE;
DO $$
DECLARE func record;
BEGIN
    FOR func IN
        SELECT p.oid::regprocedure AS signature
        FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = current_schema() AND p.proname LIKE 'procrastinate\\_%'
    LOOP
        EXECUTE 'DROP FUNCTION ' || func.signature;
    END LOOP;
END $$;
DROP TYPE IF EXISTS procrastinate_job_to_defer_v1, procrastinate_job_status,
    procrastinate_job_event_type;
"""


def run_sql(sql: str) -> None:
    """Send SQL to the driver exactly as written: no bind-parameter parsing and no `%`
    escaping (procrastinate's PL/pgSQL uses `%` placeholders in RAISE)."""
    op.get_bind().exec_driver_sql(sql, execution_options={"no_parameters": True})


def upgrade() -> None:
    """Install procrastinate's job queue schema (tables, functions, triggers, types)."""
    run_sql(SCHEMA_SQL.read_text())


def downgrade() -> None:
    """Remove every procrastinate object, including any queued jobs."""
    run_sql(DROP_SQL)
