"""The demo dataset, `wl seed --demo` (build plan, S1-C13a; DL-83, DL-87 to DL-90): a fixed
workspace to look at in the browser, and the data the end-to-end tests run on. It is built
through the services, so every audit event is recorded, and each step acts as the person who
would take it for real, under the action its endpoint checks (`ensure`), so a step the app would
refuse fails here too: the system admin adds the workspace admin and creates the orgs, each org's
owner adds its members, creates its projects naming their leads, and archives `LEGACY`, and each
lead adds the project's members.

`wl seed --manual-pass` (S3-C0c, DL-320) builds the same data plus every state the owner's
manual pass needs, the same way: more projects in `acme`, an export-controlled one, `PORTAL`'s
requirements (nested, revised, in approval, and in the Trash), a deactivated member, and a second
session for `admin`. `--demo` stays as it was: the end-to-end tests count what it builds.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.actions import Action
from app.authz.authorize import ensure
from app.authz.context import AuthzContext
from app.authz.target import Target, org_target, project_target, workspace_target
from app.core.settings import Settings
from app.enums import (
    ApprovalDecision,
    DeletedChildren,
    OrgRole,
    ProjectRole,
    ProjectType,
    RestrictionCategory,
    RestrictionLevel,
    WorkspaceRole,
)
from app.models.approval import ApprovalRequest
from app.models.org import Organization
from app.models.project import Project
from app.models.requirement import Requirement
from app.models.user import User
from app.schemas.approval import ApprovalDecisionCreate, ApprovalRequestCreate
from app.schemas.org import OrgCreate
from app.schemas.project import ProjectCreate, ProjectMemberAdd, ProjectMemberCreate
from app.schemas.requirement import RequirementCreate, RequirementUpdate
from app.services.auth import AuthService
from app.services.org import OrgService
from app.services.project import ProjectService
from app.services.requirement import RequirementService
from app.services.user import AccountSubject, UserService
from app.services.workspace import WorkspaceService

# Every demo account's password: public, which is why the command runs only where
# `demo_seed_enabled` is on (DL-90).
DEMO_PASSWORD = "harbor-demo"  # noqa: S105 -- public by design, see above
WORKSPACE = ("Harbor Consulting", "harbor")
DOMAIN = "harbor.example"

SYSTEM_ADMIN = "admin"
WORKSPACE_ADMIN = "wendy"
NO_MEMBERSHIPS = "nora"
# Created by the ERP project's lead, so they must change their password: one for each theme's
# run of the forced-change flow (DL-87).
FORCED_CHANGE = ("fiona", "felix")
FORCED_CHANGE_PROJECT = "ERP"

PEOPLE: dict[str, str] = {
    "admin": "Ada Admin",
    "wendy": "Wendy Walsh",
    "olivia": "Olivia Ortiz",
    "oscar": "Oscar Osei",
    "liam": "Liam Lewis",
    "lena": "Lena Lindqvist",
    "luke": "Luke Lambert",
    "leo": "Leo Laurent",
    "lucy": "Lucy Lam",
    "amara": "Amara Adeyemi",
    "ben": "Ben Brooks",
    "chloe": "Chloe Chen",
    "dev": "Dev Desai",
    "ella": "Ella Evans",
    "finn": "Finn Fischer",
    "hana": "Hana Hayashi",
    "sam": "Sam Silva",
    "casey": "Casey Cole",
    "ivan": "Ivan Ivanov",
    "jade": "Jade Jensen",
    "kira": "Kira Kowalski",
    "noah": "Noah Nguyen",
    "omar": "Omar Okafor",
    "priya": "Priya Patel",
    "quinn": "Quinn Quigley",
    "max": "Max Meyer",
    "nora": "Nora Novak",
    "fiona": "Fiona Flores",
    "felix": "Felix Fournier",
}

# Org slug → (name, its owner).
ORGS = {"acme": ("Acme Manufacturing", "olivia"), "globex": ("Globex Retail", "oscar")}

ADMIN, MEMBER, VIEWER = ProjectRole.ADMIN, ProjectRole.MEMBER, ProjectRole.VIEWER


@dataclass(frozen=True)
class DemoProject:
    org: str
    key: str
    name: str
    type: ProjectType
    lead: str
    members: tuple[tuple[str, ProjectRole], ...]
    level: RestrictionLevel | None = None
    categories: tuple[RestrictionCategory, ...] = ()
    archived: bool = False


# Five people on each live project; `sam` (Acme) and `max` (Globex) are on both of their org's
# projects, and `casey` is in both orgs, on a project in each (the org menu).
PROJECTS = (
    DemoProject(
        "acme",
        "ERP",
        "ERP Rollout",
        ProjectType.ERP,
        "liam",
        (("amara", ADMIN), ("ben", MEMBER), ("chloe", MEMBER), ("sam", MEMBER), ("dev", VIEWER)),
    ),
    DemoProject(
        "acme",
        "PORTAL",
        "Customer Portal",
        ProjectType.SOFTWARE,
        "lena",
        (("ella", ADMIN), ("finn", MEMBER), ("sam", MEMBER), ("casey", MEMBER), ("hana", VIEWER)),
    ),
    DemoProject(
        "acme",
        "LEGACY",
        "Legacy Cleanup",
        ProjectType.GENERAL,
        "luke",
        (("ben", MEMBER), ("chloe", MEMBER)),
        archived=True,
    ),
    DemoProject(
        "globex",
        "INV",
        "Inventory System",
        ProjectType.SOFTWARE,
        "leo",
        (("ivan", ADMIN), ("jade", MEMBER), ("max", MEMBER), ("casey", MEMBER), ("kira", VIEWER)),
    ),
    DemoProject(
        "globex",
        "FIN",
        "Finance Migration",
        ProjectType.GENERAL,
        "lucy",
        (("noah", ADMIN), ("omar", MEMBER), ("max", MEMBER), ("priya", MEMBER), ("quinn", VIEWER)),
        level=RestrictionLevel.CONFIDENTIAL,
        categories=(RestrictionCategory.FINANCIAL,),
    ),
)


# --manual-pass only. Eight more in `acme`, eleven in all: past My work's ten per org (DL-349)
# for `olivia`, and nine for `sam`, past the project selector's filter (UI-SHL-6).
MANUAL_PASS_PROJECTS = (
    *(
        DemoProject("acme", key, name, ProjectType.SOFTWARE, "lena", (("sam", MEMBER),))
        for key, name in (
            ("CRM", "Sales CRM"),
            ("WMS", "Warehouse Scanning"),
            ("HRS", "HR Self-Service"),
            ("BIR", "Reporting Dashboards"),
            ("EDI", "Supplier EDI"),
            ("MOB", "Field Mobile App"),
            ("SRV", "Field Service"),
        )
    ),
    DemoProject(
        "acme",
        "RADAR",
        "Radar Controls",
        ProjectType.SOFTWARE,
        "liam",
        (("ben", MEMBER),),
        categories=(RestrictionCategory.EXPORT_CONTROLLED,),
    ),
)
REQUIREMENTS_PROJECT = "PORTAL"
DEACTIVATED = "hana"
# A browser's user agent, so the session list labels the session's device.
SECOND_SESSION_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0"
)
SIGN_IN_DESCRIPTIONS = (
    "Customers sign in with their email and password.",
    "## Goal\n\nCustomers sign in with their email and password.\n\n"
    "## Rules\n\n- Five wrong passwords in a row lock the account for 15 minutes.\n"
    "- A locked account can still reset its password.\n",
    "## Goal\n\nCustomers sign in with their email and password.\n\n"
    "## Rules\n\n- Five wrong passwords in a row lock the account for 15 minutes.\n"
    "- A locked account can still reset its password.\n"
    "- Signing in again from the same browser ends the old session.\n\n"
    "## References\n\nThe identity provider's guidance: "
    "https://identity.example.com/guides/customer-sign-in/password-policies/lockout-thresholds"
    "-and-recovery-flows-for-consumer-accounts?section=rate-limiting&version=2026-10\n",
)


def email(username: str) -> str:
    return f"{username}@{DOMAIN}"


async def build_demo(
    session: AsyncSession, settings: Settings, *, manual_pass: bool = False
) -> str:
    """Build the dataset in an empty database (`WorkspaceService.seed` refuses otherwise), with
    the manual pass's states when `manual_pass`, and return the command's summary."""
    all_projects = PROJECTS + (MANUAL_PASS_PROJECTS if manual_pass else ())
    workspace, admin = await WorkspaceService(session).seed(
        workspace_name=WORKSPACE[0],
        workspace_slug=WORKSPACE[1],
        email=email(SYSTEM_ADMIN),
        username=SYSTEM_ADMIN,
        name=PEOPLE[SYSTEM_ADMIN],
        password=DEMO_PASSWORD,
    )
    users: dict[str, User] = {SYSTEM_ADMIN: admin}
    for username, name in PEOPLE.items():
        if username in users or username in FORCED_CHANGE:
            continue
        users[username] = await UserService(session).create_seeded(
            workspace.id,
            email=email(username),
            username=username,
            name=name,
            password=DEMO_PASSWORD,
        )

    auth = AuthService(session, settings)

    async def acting(username: str) -> AuthzContext:
        # Loaded when needed, so it holds the memberships the earlier steps gave them.
        return await auth.authz_context(users[username])

    admin_ctx = await acting(SYSTEM_ADMIN)
    ensure(admin_ctx, Action.WORKSPACE_STAFF_MANAGE, workspace_target(workspace))
    await WorkspaceService(session).add_staff(
        admin_ctx, workspace, email(WORKSPACE_ADMIN), WorkspaceRole.ADMIN
    )

    orgs = OrgService(session)
    org_of: dict[str, tuple[Organization, AuthzContext]] = {}
    for slug, (name, owner) in ORGS.items():
        ensure(admin_ctx, Action.ORG_CREATE, workspace_target(workspace))
        created = await orgs.create(
            admin_ctx, workspace, OrgCreate(name=name, slug=slug, owner_id=users[owner].id)
        )
        org = cast(Organization, await orgs.get(created.id))
        owner_ctx = await acting(owner)
        ensure(owner_ctx, Action.ORG_MEMBER_MANAGE, org_target(org))
        people = {p.lead for p in all_projects if p.org == slug} | {
            username for p in all_projects if p.org == slug for username, _ in p.members
        }
        for username in sorted(people):
            await orgs.add_member(owner_ctx, org, email(username), OrgRole.MEMBER)
        org_of[slug] = (org, owner_ctx)

    projects = ProjectService(session)
    for spec in all_projects:
        org, owner_ctx = org_of[spec.org]
        ensure(owner_ctx, Action.PROJECT_CREATE, org_target(org))
        # Sent only where it's needed: the API refuses it anywhere else (DL-81).
        exported = RestrictionCategory.EXPORT_CONTROLLED in spec.categories
        confirmed: dict[str, Any] = {"export_control_confirmed": True} if exported else {}
        members: dict[str, Any] = (
            {"confirmed_member_ids": [users[spec.lead].id]} if exported else {}
        )
        await projects.create(
            owner_ctx,
            org,
            ProjectCreate(
                name=spec.name,
                key=spec.key,
                type=spec.type,
                first_admin_id=users[spec.lead].id,
                restriction_level=spec.level,
                restriction_categories=list(spec.categories),
                **confirmed,
                **members,
            ),
        )
        project = cast(tuple[Project, object], await projects.load(spec.key))[0]
        lead_ctx = await acting(spec.lead)
        ensure(lead_ctx, Action.PROJECT_MEMBER_MANAGE, project_target(project))
        for username, role in spec.members:
            await projects.add_member(
                lead_ctx,
                project,
                ProjectMemberAdd(role=role, user_id=users[username].id, **confirmed),
            )
        if spec.key == FORCED_CHANGE_PROJECT:
            for username in FORCED_CHANGE:
                await projects.create_member(
                    lead_ctx,
                    project,
                    ProjectMemberCreate(
                        email=email(username),
                        username=username,
                        name=PEOPLE[username],
                        password=DEMO_PASSWORD,
                        role=MEMBER,
                    ),
                )
        if spec.archived:
            # Org owners and admins archive a project, not its admins by role alone.
            ensure(owner_ctx, Action.PROJECT_ARCHIVE, project_target(project))
            await projects.archive(owner_ctx, project)

    summary = (
        f"Created the demo workspace {workspace.slug} with {len(PEOPLE)} users, each with the"
        f" password {DEMO_PASSWORD!r}; sign in as {email(SYSTEM_ADMIN)} (system admin) or any"
        " user in the developer guide's demo data table."
    )
    if not manual_pass:
        return summary
    await _requirements(session, acting)
    wendy_ctx = await acting(WORKSPACE_ADMIN)
    loaded = await UserService(session).load(users[DEACTIVATED].id)
    subject, target = cast(tuple[AccountSubject, Target], loaded)
    ensure(wendy_ctx, Action.USER_MANAGE, target)
    await auth.deactivate(wendy_ctx, subject)
    # Whoever runs the pass signs in as `admin` and sees this one beside their own.
    await auth.sign_in(email(SYSTEM_ADMIN), DEMO_PASSWORD, user_agent=SECOND_SESSION_AGENT)
    return f'{summary} With the manual pass\'s states (developer guide, "Demo data").'


async def _requirements(
    session: AsyncSession, acting: Callable[[str], Awaitable[AuthzContext]]
) -> None:
    """`PORTAL`'s requirements, each step by the person who would take it: `finn` (a member)
    reports them and revises `RQ-2` twice; `lena` (the lead; only project admins ask) asks `ella`
    (an admin) to approve three; `ella` approves two, and `finn` edits one of those after
    (Approved · modified); `finn` deletes one of his, and `lena` deletes another with its
    child."""
    service = RequirementService(session)
    finn, ella, lena = await acting("finn"), await acting("ella"), await acting("lena")
    project = cast(tuple[Project, object], await ProjectService(session).load(REQUIREMENTS_PROJECT))

    async def load(number: int) -> Requirement:
        return cast(tuple[Requirement, object], await service.load(REQUIREMENTS_PROJECT, number))[0]

    async def create(title: str, parent: int | None = None, description: str = "") -> int:
        parent_id = None if parent is None else (await load(parent)).id
        values = RequirementCreate(title=title, description_md=description, parent_id=parent_id)
        return (await service.create(finn, project[0], values)).number

    async def edit(number: int, note: str, description: str) -> None:
        requirement = await load(number)
        values = RequirementUpdate(
            version=requirement.version, change_note=note, description_md=description
        )
        await service.update(finn, requirement, values)

    accounts = await create("Customer accounts")
    sign_in = await create("Sign-in", accounts, SIGN_IN_DESCRIPTIONS[0])
    await create("Password reset", sign_in)
    await edit(sign_in, "Split into goal and rules.", SIGN_IN_DESCRIPTIONS[1])
    await edit(sign_in, "Added the session rule and a reference.", SIGN_IN_DESCRIPTIONS[2])

    pending = await create("Order history", description="Customers see their past orders.")
    approved = await create("Invoice download", description="Customers download a PDF invoice.")
    modified = await create("Saved addresses", description="Customers keep up to five addresses.")
    requests = {
        number: await service.request_approval(
            lena, await load(number), ApprovalRequestCreate(approver_ids=[ella.user_id])
        )
        for number in (pending, approved, modified)
    }
    for number in (approved, modified):
        loaded = await service.load_approval_request_to_decide(requests[number].id)
        request, target = cast(tuple[ApprovalRequest, Target], loaded)
        ensure(ella, Action.APPROVAL_DECIDE, target)
        await service.decide(
            ella, request, ApprovalDecisionCreate(decision=ApprovalDecision.APPROVED)
        )
    await edit(modified, "Raised the limit.", "Customers keep up to ten addresses.")

    await service.delete(finn, await load(await create("Gift cards")), DeletedChildren.PROMOTE)
    loyalty = await create("Loyalty points")
    await create("Points balance", loyalty)
    await service.delete(lena, await load(loyalty), DeletedChildren.DELETE)
