"""The demo dataset, `wl seed --demo` (build plan, S1-C13a; DL-83, DL-87 to DL-90): a fixed
workspace to look at in the browser, and the data the end-to-end tests run on. It is built
through the services, so every audit event is recorded, and each step acts as the person who
would take it for real, under the action its endpoint checks (`ensure`), so a step the app would
refuse fails here too: the system admin adds the workspace admin and creates the orgs, each org's
owner adds its members, creates its projects naming their leads, and archives `LEGACY`, and each
lead adds the project's members.
"""

from dataclasses import dataclass
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.actions import Action
from app.authz.authorize import ensure
from app.authz.context import AuthzContext
from app.authz.target import org_target, project_target, workspace_target
from app.core.settings import Settings
from app.enums import (
    OrgRole,
    ProjectRole,
    ProjectType,
    RestrictionCategory,
    RestrictionLevel,
    WorkspaceRole,
)
from app.models.org import Organization
from app.models.project import Project
from app.models.user import User
from app.schemas.org import OrgCreate
from app.schemas.project import ProjectCreate, ProjectMemberAdd, ProjectMemberCreate
from app.services.auth import AuthService
from app.services.org import OrgService
from app.services.project import ProjectService
from app.services.user import UserService
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
# projects, and `casey` is in both orgs, on a project in each (the org switcher).
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


def email(username: str) -> str:
    return f"{username}@{DOMAIN}"


async def build_demo(session: AsyncSession, settings: Settings) -> str:
    """Build the dataset in an empty database (`WorkspaceService.seed` refuses otherwise) and
    return the command's summary."""
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
        people = {p.lead for p in PROJECTS if p.org == slug} | {
            username for p in PROJECTS if p.org == slug for username, _ in p.members
        }
        for username in sorted(people):
            await orgs.add_member(owner_ctx, org, email(username), OrgRole.MEMBER)
        org_of[slug] = (org, owner_ctx)

    projects = ProjectService(session)
    for spec in PROJECTS:
        org, owner_ctx = org_of[spec.org]
        ensure(owner_ctx, Action.PROJECT_CREATE, org_target(org))
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
            ),
        )
        project = cast(tuple[Project, object], await projects.load(spec.key))[0]
        lead_ctx = await acting(spec.lead)
        ensure(lead_ctx, Action.PROJECT_MEMBER_MANAGE, project_target(project))
        for username, role in spec.members:
            await projects.add_member(
                lead_ctx, project, ProjectMemberAdd(role=role, user_id=users[username].id)
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

    return (
        f"Created the demo workspace {workspace.slug} with {len(PEOPLE)} users, each with the"
        f" password {DEMO_PASSWORD!r}; sign in as {email(SYSTEM_ADMIN)} (system admin) or any"
        " user in the developer guide's demo data table."
    )
