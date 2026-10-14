"""The demo dataset, `wl seed --demo` (build plan, S1-C13a; DL-83, DL-87 to DL-90), built in
the test transaction through `app/cli.py`'s `run`, as the command runs it."""

import argparse

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

import app.cli
from app.cli import main, parser, run
from app.core.db import SessionMaker
from app.core.security import verify_password
from app.core.settings import Settings
from app.enums import AuditAction
from app.models.audit_event import AuditEvent
from app.models.org import Membership, Organization
from app.models.project import Project, ProjectMembership
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMembership
from tests.factories.workspace import WorkspaceFactory
from tests.integration.test_cli import count

pytestmark = [pytest.mark.anyio, pytest.mark.security]

DEMO = ("seed", "--demo")


def args(*argv: str) -> argparse.Namespace:
    return parser().parse_args(argv)


def enabled(settings: Settings, on: bool = True) -> Settings:
    return settings.model_copy(update={"demo_seed_enabled": on})


@pytest.fixture
async def built(sessionmaker: SessionMaker, settings: Settings) -> int:
    return await run(args(*DEMO), sessionmaker, settings=enabled(settings))


# --- where it runs --------------------------------------------------------------------------------


def test_the_demo_setting_is_off_by_default() -> None:
    assert Settings.model_fields["demo_seed_enabled"].default is False


async def test_the_demo_is_refused_while_the_setting_is_off(
    sessionmaker: SessionMaker,
    session: AsyncSession,
    settings: Settings,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = await run(args(*DEMO), sessionmaker, settings=enabled(settings, on=False))

    assert code == 1
    assert "The demo seed is off here" in capsys.readouterr().err
    assert (await count(session, Workspace), await count(session, User)) == (0, 0)
    assert await count(session, AuditEvent) == 0


async def test_the_demo_is_refused_when_a_workspace_exists(
    sessionmaker: SessionMaker,
    session: AsyncSession,
    settings: Settings,
    capsys: pytest.CaptureFixture[str],
) -> None:
    await WorkspaceFactory.create_async()

    code = await run(args(*DEMO), sessionmaker, settings=enabled(settings))

    assert code == 1
    assert "A workspace already exists." in capsys.readouterr().err
    assert (await count(session, Workspace), await count(session, User)) == (1, 0)


def test_main_demo_asks_for_no_seed_values(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The plain seed fails without a terminal or values; the demo has its own."""
    for key in ("WORKSPACE_NAME", "WORKSPACE_SLUG", "EMAIL", "USERNAME", "NAME", "PASSWORD"):
        monkeypatch.delenv(f"SEED_{key}", raising=False)
    calls: list[tuple[argparse.Namespace, object]] = []

    async def recorded(parsed: argparse.Namespace, _sessionmaker: object, seed: object) -> int:
        calls.append((parsed, seed))
        return 0

    monkeypatch.setattr(app.cli, "run", recorded)

    assert main(list(DEMO)) == 0  # pytest's stdin isn't a terminal
    assert [(parsed.demo, seed) for parsed, seed in calls] == [(True, {})]
    assert "Missing" not in capsys.readouterr().err


# --- what it builds -------------------------------------------------------------------------------


async def test_the_demo_prints_the_shared_password(
    sessionmaker: SessionMaker, settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    assert await run(args(*DEMO), sessionmaker, settings=enabled(settings)) == 0
    assert (
        "Created the demo workspace harbor with 29 users, each with the password 'harbor-demo'"
        in capsys.readouterr().out
    )


async def test_the_demo_workspace_has_a_system_admin_owner_and_a_workspace_admin(
    built: int, session: AsyncSession
) -> None:
    staff = await session.execute(
        select(Workspace.slug, User.username, WorkspaceMembership.role)
        .join(Workspace, WorkspaceMembership.workspace_id == Workspace.id)
        .join(User, WorkspaceMembership.user_id == User.id)
    )
    admins = await session.execute(select(User.username).where(User.is_system_admin))

    assert set(map(tuple, staff)) == {("harbor", "admin", "owner"), ("harbor", "wendy", "admin")}
    assert list(admins.scalars()) == ["admin"]


async def test_the_demo_orgs_have_their_owner_and_members(
    built: int, session: AsyncSession
) -> None:
    rows = await session.execute(
        select(Organization.slug, User.username, Membership.role)
        .join(Organization, Membership.organization_id == Organization.id)
        .join(User, Membership.user_id == User.id)
    )

    members = {"liam", "lena", "luke", "amara", "ben", "chloe", "dev", "ella", "finn", "hana"}
    acme = {("acme", u, "member") for u in {*members, "sam", "casey", "fiona", "felix"}}
    globex_members = {"leo", "lucy", "ivan", "jade", "kira", "max", "casey", "noah", "omar"}
    globex = {("globex", u, "member") for u in {*globex_members, "priya", "quinn"}}
    assert set(map(tuple, rows)) == {
        ("acme", "olivia", "owner"),
        ("globex", "oscar", "owner"),
        *acme,
        *globex,
    }


async def test_the_demo_projects_have_their_org_type_lead_state_and_classification(
    built: int, session: AsyncSession
) -> None:
    lead = aliased(User)
    rows = await session.execute(
        select(
            Project.key,
            Organization.slug,
            Project.name,
            Project.type,
            lead.username,
            Project.archived_at.is_not(None),
            Project.classification_level,
            Project.classification_categories,
        )
        .join(Organization, Project.organization_id == Organization.id)
        .join(lead, Project.lead_id == lead.id)
    )

    assert {key: rest for key, *rest in rows} == {
        "ERP": ["acme", "ERP Rollout", "erp", "liam", False, None, []],
        "PORTAL": ["acme", "Customer Portal", "software", "lena", False, None, []],
        "LEGACY": ["acme", "Legacy Cleanup", "general", "luke", True, None, []],
        "INV": ["globex", "Inventory System", "software", "leo", False, None, []],
        "FIN": [
            "globex",
            "Finance Migration",
            "general",
            "lucy",
            False,
            "confidential",
            ["financial"],
        ],
    }


async def test_the_demo_projects_have_their_lead_and_members_with_roles(
    built: int, session: AsyncSession
) -> None:
    rows = await session.execute(
        select(Project.key, User.username, ProjectMembership.role)
        .join(Project, ProjectMembership.project_id == Project.id)
        .join(User, ProjectMembership.user_id == User.id)
    )

    assert set(map(tuple, rows)) == {
        *{("ERP", u, r) for u, r in [("liam", "admin"), ("amara", "admin"), ("ben", "member")]},
        *{("ERP", u, r) for u, r in [("chloe", "member"), ("sam", "member"), ("dev", "viewer")]},
        ("ERP", "fiona", "member"),
        ("ERP", "felix", "member"),
        *{("PORTAL", u, r) for u, r in [("lena", "admin"), ("ella", "admin"), ("finn", "member")]},
        *{
            ("PORTAL", u, r)
            for u, r in [("sam", "member"), ("casey", "member"), ("hana", "viewer")]
        },
        *{("LEGACY", u, r) for u, r in [("luke", "admin"), ("ben", "member"), ("chloe", "member")]},
        *{("INV", u, r) for u, r in [("leo", "admin"), ("ivan", "admin"), ("jade", "member")]},
        *{("INV", u, r) for u, r in [("max", "member"), ("casey", "member"), ("kira", "viewer")]},
        *{("FIN", u, r) for u, r in [("lucy", "admin"), ("noah", "admin"), ("omar", "member")]},
        *{("FIN", u, r) for u, r in [("max", "member"), ("priya", "member"), ("quinn", "viewer")]},
    }


async def test_only_the_two_forced_change_users_must_change_their_password(
    built: int, session: AsyncSession
) -> None:
    flagged = await session.execute(select(User.username).where(User.must_change_password))

    assert await count(session, User) == 29
    assert set(flagged.scalars()) == {"fiona", "felix"}


async def test_the_no_access_user_has_no_memberships(built: int, session: AsyncSession) -> None:
    nora = select(User.id).where(User.username == "nora").scalar_subquery()
    held = [
        await session.scalar(select(func.count()).where(model.user_id == nora))
        for model in (WorkspaceMembership, Membership, ProjectMembership)
    ]

    assert await session.scalar(select(User.email).where(User.username == "nora")) == (
        "nora@harbor.example"
    )
    assert held == [0, 0, 0]


@pytest.mark.parametrize("username", ["admin", "casey", "felix"])
async def test_demo_users_share_the_demo_password(
    built: int, session: AsyncSession, username: str
) -> None:
    """One user from each creation path: the seed's admin, the seeded users, the admin path."""
    hashed = await session.scalar(select(User.hashed_password).where(User.username == username))

    assert await verify_password(str(hashed), "harbor-demo") is True


async def test_each_demo_step_is_recorded_with_the_person_who_would_take_it(
    built: int, session: AsyncSession
) -> None:
    actor = aliased(User)
    rows = await session.execute(
        select(AuditEvent.action, actor.username)
        .outerjoin(actor, AuditEvent.actor_id == actor.id)
        .distinct()
    )
    no_actor_users = await session.scalar(
        select(func.count()).where(
            AuditEvent.action == AuditAction.USER_CREATED, AuditEvent.actor_id.is_(None)
        )
    )

    assert set(map(tuple, rows)) == {
        # the seed itself, and the seeded users (DL-88)
        ("workspace_created", None),
        ("user_created", None),
        ("system_admin_granted", None),
        ("workspace_member_added", None),
        # the system admin: the workspace admin and the orgs with their owners
        ("workspace_member_added", "admin"),
        ("org_created", "admin"),
        ("org_member_added", "admin"),
        # each org's owner: its members and its projects, naming the leads
        ("org_member_added", "olivia"),
        ("org_member_added", "oscar"),
        ("project_created", "olivia"),
        ("project_created", "oscar"),
        ("project_member_added", "olivia"),
        ("project_member_added", "oscar"),
        # each lead: the project's members and the forced-change users
        ("project_member_added", "liam"),
        ("project_member_added", "lena"),
        ("project_member_added", "luke"),
        ("project_member_added", "leo"),
        ("project_member_added", "lucy"),
        ("user_created", "liam"),
        ("org_member_added", "liam"),
        # LEGACY's org owner archives it
        ("project_archived", "olivia"),
    }
    assert no_actor_users == 27
