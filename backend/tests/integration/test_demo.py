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
from app.enums import ActivityAction, AuditAction
from app.models.approval import Approval, ApprovalRequest
from app.models.audit import ActivityLog
from app.models.audit_event import AuditEvent
from app.models.auth import UserSession
from app.models.org import Membership, Organization
from app.models.project import Project, ProjectMembership
from app.models.requirement import Requirement, RequirementRevision
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMembership
from tests.factories.workspace import WorkspaceFactory
from tests.integration.test_cli import count

pytestmark = [pytest.mark.anyio, pytest.mark.security]

DEMO = ("seed", "--demo")
MANUAL_PASS = ("seed", "--manual-pass")
BOTH = pytest.mark.parametrize("argv", [DEMO, MANUAL_PASS], ids=["demo", "manual-pass"])


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


@BOTH
async def test_the_demo_is_refused_while_the_setting_is_off(
    sessionmaker: SessionMaker,
    session: AsyncSession,
    settings: Settings,
    capsys: pytest.CaptureFixture[str],
    argv: tuple[str, ...],
) -> None:
    code = await run(args(*argv), sessionmaker, settings=enabled(settings, on=False))

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


@BOTH
def test_main_demo_asks_for_no_seed_values(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], argv: tuple[str, ...]
) -> None:
    """The plain seed fails without a terminal or values; the demo has its own."""
    for key in ("WORKSPACE_NAME", "WORKSPACE_SLUG", "EMAIL", "USERNAME", "NAME", "PASSWORD"):
        monkeypatch.delenv(f"SEED_{key}", raising=False)
    calls: list[tuple[argparse.Namespace, object]] = []

    async def recorded(parsed: argparse.Namespace, _sessionmaker: object, seed: object) -> int:
        calls.append((parsed, seed))
        return 0

    monkeypatch.setattr(app.cli, "run", recorded)

    assert main(list(argv)) == 0  # pytest's stdin isn't a terminal
    assert [(parsed.command, seed) for parsed, seed in calls] == [("seed", {})]
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


async def test_the_demo_projects_have_their_org_type_lead_state_and_restriction(
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
            Project.restriction_level,
            Project.restriction_categories,
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


async def test_the_plain_demo_builds_none_of_the_manual_pass_states(
    built: int, session: AsyncSession
) -> None:
    """The end-to-end tests count what `--demo` builds (S3-C0c)."""
    inactive = await session.scalar(select(func.count()).where(User.is_active.is_(False)))

    assert await count(session, Requirement) == 0
    assert (await count(session, UserSession), inactive) == (0, 0)


# --- the manual pass's states (S3-C0c, DL-320) ------------------------------------------------


@pytest.fixture
async def manual(sessionmaker: SessionMaker, settings: Settings) -> int:
    return await run(args(*MANUAL_PASS), sessionmaker, settings=enabled(settings))


async def test_the_manual_pass_prints_that_it_built_its_states(
    sessionmaker: SessionMaker, settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    assert await run(args(*MANUAL_PASS), sessionmaker, settings=enabled(settings)) == 0
    out = capsys.readouterr().out
    assert "Created the demo workspace harbor with 29 users" in out
    assert "With the manual pass's states" in out


async def test_the_manual_pass_puts_eleven_projects_in_acme(
    manual: int, session: AsyncSession
) -> None:
    lead = aliased(User)
    rows = await session.execute(
        select(Project.key, lead.username, Project.restriction_categories)
        .join(Organization, Project.organization_id == Organization.id)
        .join(lead, Project.lead_id == lead.id)
        .where(Organization.slug == "acme")
    )

    assert {key: rest for key, *rest in rows} == {
        "ERP": ["liam", []],
        "PORTAL": ["lena", []],
        "LEGACY": ["luke", []],
        **{key: ["lena", []] for key in ("CRM", "WMS", "HRS", "BIR", "EDI", "MOB", "SRV")},
        "RADAR": ["liam", ["export_controlled"]],
    }


async def test_the_export_controlled_project_has_its_lead_and_one_member(
    manual: int, session: AsyncSession
) -> None:
    rows = await session.execute(
        select(User.username, ProjectMembership.role)
        .join(Project, ProjectMembership.project_id == Project.id)
        .join(User, ProjectMembership.user_id == User.id)
        .where(Project.key == "RADAR")
    )

    assert set(map(tuple, rows)) == {("liam", "admin"), ("ben", "member")}


async def test_portal_requirements_are_nested_approved_and_in_the_trash(
    manual: int, session: AsyncSession
) -> None:
    parent = aliased(Requirement)
    rows = await session.execute(
        select(
            Requirement.number,
            Requirement.title,
            parent.number,
            Requirement.status,
            Requirement.deleted_at.is_not(None),
        )
        .outerjoin(parent, Requirement.parent_requirement_id == parent.id)
        .execution_options(include_deleted=True)
    )

    assert {number: rest for number, *rest in rows} == {
        1: ["Customer accounts", None, "draft", False],
        2: ["Sign-in", 1, "draft", False],
        3: ["Password reset", 2, "draft", False],
        4: ["Order history", None, "draft", False],
        5: ["Invoice download", None, "approved", False],
        6: ["Saved addresses", None, "approved", False],
        7: ["Gift cards", None, "draft", True],
        8: ["Loyalty points", None, "draft", True],
        9: ["Points balance", 8, "draft", True],
    }


async def test_sign_in_has_three_revisions_ending_with_headings_a_list_and_a_long_url(
    manual: int, session: AsyncSession
) -> None:
    rows = await session.execute(
        select(RequirementRevision.revision_number, RequirementRevision.change_note)
        .join(Requirement, RequirementRevision.requirement_id == Requirement.id)
        .where(Requirement.number == 2)
        .order_by(RequirementRevision.revision_number)
    )
    description = await session.scalar(
        select(Requirement.description_md).where(Requirement.number == 2)
    )

    assert list(map(tuple, rows)) == [
        (1, None),
        (2, "Split into goal and rules."),
        (3, "Added the session rule and a reference."),
    ]
    assert "## Goal" in str(description)
    assert "\n- Signing in again" in str(description)
    assert "https://identity.example.com/guides/customer-sign-in/password-policies/" in str(
        description
    )


async def test_the_approval_requests_are_pending_approved_and_approved_then_modified(
    manual: int, session: AsyncSession
) -> None:
    approver = aliased(User)
    rows = await session.execute(
        select(
            Requirement.number,
            ApprovalRequest.status,
            approver.username,
            Requirement.approved_revision_id == Requirement.current_revision_id,
        )
        .join(ApprovalRequest, ApprovalRequest.entity_id == Requirement.id)
        .join(Approval, Approval.approval_request_id == ApprovalRequest.id)
        .join(approver, Approval.approver_id == approver.id)
    )

    # Approved and edited since: "Approved · modified" (design-doc §6.1).
    assert {number: rest for number, *rest in rows} == {
        4: ["pending", "ella", None],
        5: ["approved", "ella", True],
        6: ["approved", "ella", False],
    }


async def test_each_requirement_step_is_logged_as_the_person_who_would_take_it(
    manual: int, session: AsyncSession
) -> None:
    rows = await session.execute(
        select(Requirement.number, ActivityLog.action, User.username)
        .join(Requirement, ActivityLog.entity_id == Requirement.id)
        .join(User, ActivityLog.changed_by == User.id)
        .where(ActivityLog.action.in_([ActivityAction.CREATED, ActivityAction.DELETED]))
        .execution_options(include_deleted=True)
    )

    assert set(map(tuple, rows)) == {
        *{(n, "created", "finn") for n in range(1, 10)},
        (7, "deleted", "finn"),
        (8, "deleted", "lena"),
        (9, "deleted", "lena"),
    }


async def test_the_workspace_admin_deactivates_one_member(
    manual: int, session: AsyncSession
) -> None:
    actor = aliased(User)
    inactive = await session.execute(select(User.username).where(User.is_active.is_(False)))
    events = await session.execute(
        select(actor.username)
        .select_from(AuditEvent)
        .join(actor, AuditEvent.actor_id == actor.id)
        .where(AuditEvent.action == AuditAction.USER_DEACTIVATED)
    )

    assert list(inactive.scalars()) == ["hana"]
    assert list(events.scalars()) == ["wendy"]


async def test_the_system_admin_has_one_session_from_another_browser(
    manual: int, session: AsyncSession
) -> None:
    rows = await session.execute(
        select(User.username, UserSession.user_agent).join(User, UserSession.user_id == User.id)
    )

    assert list(map(tuple, rows)) == [
        (
            "admin",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
        )
    ]
