"""The projects API's behavior beyond who may call it (build plan, "The projects API", DL-76):
seeding, the first admin and lead, key rules, updates and their events, archiving, the org's list,
module guidance, and My work. Who gets 2xx/403/404 is in tests/api/authz/test_projects.py (spec
tests)."""

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import Select, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.scoping import Scope
from app.enums import AuditAction, OrgRole, ProjectRole, WorkspaceRole
from app.models.audit_event import AuditEvent
from app.models.project import Project, ProjectMembership
from app.models.user import User
from app.repositories.project import ProjectRepository
from tests.factories.org import MembershipFactory, OrganizationFactory
from tests.factories.project import ProjectFactory, ProjectMembershipFactory
from tests.factories.user import UserFactory
from tests.factories.workspace import WorkspaceMembershipFactory
from tests.support.authz import Tenancy, sign_in_as, tenancy

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("session")]


@pytest.fixture
async def t() -> Tenancy:
    return await tenancy()


async def org_member(t: Tenancy, role: OrgRole = OrgRole.MEMBER, **user: object) -> User:
    person = await UserFactory.create_async(**user)
    await MembershipFactory.create_async(organization=t.org, user=person, role=role)
    return person


async def signed_in(client: AsyncClient, user: User) -> User:
    await sign_in_as(client, user)
    return user


async def stored(session: AsyncSession, key: str) -> Project:
    statement = select(Project).where(Project.key == key).execution_options(populate_existing=True)
    return (await session.execute(statement)).scalar_one()


async def members(session: AsyncSession, project: Project) -> dict[object, ProjectRole]:
    rows = await session.execute(
        select(ProjectMembership.user_id, ProjectMembership.role).where(
            ProjectMembership.project_id == project.id
        )
    )
    return dict(rows.all())


async def events(session: AsyncSession) -> list[tuple[object, ...]]:
    rows = await session.execute(
        select(
            AuditEvent.action,
            AuditEvent.actor_id,
            AuditEvent.organization_id,
            AuditEvent.target_user_id,
            AuditEvent.details,
        ).order_by(AuditEvent.id)
    )
    return [tuple(row) for row in rows]


def fields(body: dict[str, object]) -> list[tuple[list[object], str]]:
    return [(e["loc"], e["type"]) for e in body["details"]["fields"]]  # pyright: ignore[reportIndexIssue, reportUnknownVariableType, reportArgumentType]


async def projects_of(user: User, t: Tenancy, count: int) -> None:
    """`count` projects P00, P01, … in the tenancy's org, each with `user` as a member."""
    for n in range(count):
        project = await ProjectFactory.create_async(
            organization=t.org, key=f"P{n:02d}", name=f"Project {n:02d}"
        )
        await ProjectMembershipFactory.create_async(project=project, user=user)


def new(**values: object) -> dict[str, object]:
    return {"name": "Invoicing", "key": "INV", "type": "software", **values}


# --- Create ---------------------------------------------------------------------------------------


async def test_a_new_project_makes_its_creator_first_admin_and_lead_and_records_both(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    olga = await signed_in(client, await org_member(t, name="Olga Owens"))

    response = await client.post(
        f"/api/orgs/{t.org.id}/projects", json=new(key=" inv ", name=" Invoicing ")
    )

    body = response.json()
    assert response.status_code == 201
    assert (body["key"], body["name"], body["status"], body["lead_id"], body["lead_name"]) == (
        "INV",
        "Invoicing",
        "planning",
        str(olga.id),
        "Olga Owens",  # the lead's name in the response, from the new lead (DL-111)
    )
    # The creator's new membership counts in the response's actions.
    assert "project.update" in body["allowed_actions"]
    project = await stored(session, "INV")
    assert await members(session, project) == {olga.id: ProjectRole.ADMIN}
    assert await events(session) == [
        (
            AuditAction.PROJECT_CREATED,
            olga.id,
            t.org.id,
            None,
            {"restriction_level": None, "restriction_categories": []},
        ),
        (AuditAction.PROJECT_MEMBER_ADDED, olga.id, t.org.id, olga.id, {"role": "admin"}),
    ]


@pytest.mark.parametrize("project_type", ["software", "erp", "general"])
async def test_a_new_project_is_seeded_with_no_unshipped_module(
    client: AsyncClient, session: AsyncSession, t: Tenancy, project_type: str
) -> None:
    """Seeding skips a module that hasn't shipped, `sprints` and `github` included (DL-136)."""
    await signed_in(client, await org_member(t))

    response = await client.post(f"/api/orgs/{t.org.id}/projects", json=new(type=project_type))

    assert response.json()["enabled_modules"] == []
    assert (await stored(session, "INV")).enabled_modules == []


@pytest.mark.parametrize("modules", [["sprints"], ["github", "github"]])
async def test_an_unshipped_module_chosen_at_creation_is_refused(
    client: AsyncClient, session: AsyncSession, t: Tenancy, modules: list[str]
) -> None:
    await signed_in(client, await org_member(t))

    response = await client.post(
        f"/api/orgs/{t.org.id}/projects", json=new(enabled_modules=modules)
    )

    assert (response.status_code, fields(response.json())) == (
        422,
        [(["body", "enabled_modules"], "module_unavailable")],
    )
    assert await session.scalar(select(Project.id).where(Project.key == "INV")) is None


async def test_a_module_that_isnt_allowed_yet_is_refused(client: AsyncClient, t: Tenancy) -> None:
    await signed_in(client, await org_member(t))

    response = await client.post(
        f"/api/orgs/{t.org.id}/projects", json=new(type="erp", enabled_modules=["raid"])
    )

    assert (response.status_code, fields(response.json())) == (
        422,
        [(["body", "enabled_modules", 0], "enum")],
    )


async def test_a_named_first_admin_gets_the_membership_and_the_lead(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    await signed_in(client, await org_member(t, OrgRole.ADMIN))
    pia = await org_member(t)

    response = await client.post(
        f"/api/orgs/{t.org.id}/projects", json=new(first_admin_id=str(pia.id))
    )

    assert response.json()["lead_id"] == str(pia.id)
    assert await members(session, await stored(session, "INV")) == {pia.id: ProjectRole.ADMIN}


async def test_a_deactivated_first_admin_is_refused(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    await signed_in(client, await org_member(t, OrgRole.ADMIN))
    gone = await org_member(t, is_active=False)

    response = await client.post(
        f"/api/orgs/{t.org.id}/projects", json=new(first_admin_id=str(gone.id))
    )

    assert (response.status_code, fields(response.json())) == (
        422,
        [(["body", "first_admin_id"], "account_inactive")],
    )
    assert await events(session) == []


@pytest.mark.parametrize(
    ("key", "problem"),
    [
        ("IN", "too_short"),
        ("INVOICE", "too_long"),
        ("1NV", "must_start_with_letter"),
        ("PMT", "taken"),
    ],
)
async def test_a_bad_or_taken_key_is_refused(
    client: AsyncClient, session: AsyncSession, t: Tenancy, key: str, problem: str
) -> None:
    """PMT is taken by the tenancy's project; keys are unique in the workspace."""
    await signed_in(client, await org_member(t))

    response = await client.post(f"/api/orgs/{t.org.id}/projects", json=new(key=key))

    assert (response.status_code, fields(response.json())) == (422, [(["body", "key"], problem)])
    assert await events(session) == []


async def test_a_key_is_taken_across_the_workspaces_orgs(client: AsyncClient, t: Tenancy) -> None:
    other = await OrganizationFactory.create_async(workspace=t.workspace)
    await ProjectFactory.create_async(organization=other, key="LDG")
    await signed_in(client, await org_member(t))

    response = await client.post(f"/api/orgs/{t.org.id}/projects", json=new(key="ldg"))

    assert fields(response.json()) == [(["body", "key"], "taken")]


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        ("inv", {"available": True, "problem": None}),
        ("pmt", {"available": False, "problem": "taken"}),
        ("in", {"available": False, "problem": "too_short"}),
    ],
)
async def test_key_availability_uppercases_the_key_as_create_does(
    client: AsyncClient, t: Tenancy, key: str, expected: dict[str, object]
) -> None:
    await signed_in(client, await org_member(t))

    response = await client.get(
        f"/api/orgs/{t.org.id}/project-key-availability", params={"key": key}
    )

    assert response.json() == expected


# --- Update ---------------------------------------------------------------------------------------


async def admin_of_pmt(client: AsyncClient, t: Tenancy) -> User:
    return await signed_in(client, await org_member(t, OrgRole.ADMIN))


async def test_an_update_changes_and_records_the_fields_sent(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    admin = await admin_of_pmt(client, t)

    response = await client.patch(
        "/api/projects/pmt",
        json={"name": "Payments 2", "status": "active", "type": "erp"},
    )

    assert response.status_code == 200
    project = await stored(session, "PMT")
    assert (project.name, project.status, project.type) == ("Payments 2", "active", "erp")
    [(action, actor, org_id, _, details)] = await events(session)
    assert (action, actor, org_id) == (AuditAction.PROJECT_UPDATED, admin.id, t.org.id)
    assert details == {
        "old": {
            "name": "Payments",
            "status": "planning",
            "type": "software",
        },
        "new": {"name": "Payments 2", "status": "active", "type": "erp"},
    }


async def test_an_update_enabling_an_unshipped_module_is_refused(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    await admin_of_pmt(client, t)

    response = await client.patch(
        "/api/projects/pmt", json={"name": "Payments 2", "enabled_modules": ["sprints"]}
    )

    assert (response.status_code, fields(response.json())) == (
        422,
        [(["body", "enabled_modules"], "module_unavailable")],
    )
    project = await stored(session, "PMT")
    assert (project.name, project.enabled_modules) == ("Payments", [])
    assert await events(session) == []


async def test_an_update_that_changes_nothing_records_nothing(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    await admin_of_pmt(client, t)

    response = await client.patch("/api/projects/PMT", json={"name": "Payments", "key": "NEW"})

    assert (response.status_code, response.json()["key"]) == (200, "PMT")
    assert await events(session) == []


async def test_the_project_read_names_its_lead_and_none_without_one(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    await admin_of_pmt(client, t)
    lena = await UserFactory.create_async(name="Lena Lead")
    led = await ProjectFactory.create_async(organization=t.org, key="LED", lead=lena)
    await ProjectMembershipFactory.create_async(project=led, user=lena)

    with_lead = await client.get("/api/projects/LED")
    without = await client.get("/api/projects/PMT")

    assert (
        with_lead.json()["lead_id"],
        with_lead.json()["lead_name"],
        with_lead.json()["lead_is_active"],
    ) == (str(lena.id), "Lena Lead", True)
    assert (
        without.json()["lead_id"],
        without.json()["lead_name"],
        without.json()["lead_is_active"],
    ) == (None, None, None)


async def test_a_deactivated_lead_stays_the_lead_marked_inactive(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    """Design-doc §1.1: a deactivated lead stays the lead, shown as deactivated (DL-113)."""
    await admin_of_pmt(client, t)
    gail = await UserFactory.create_async(name="Gail Gone", is_active=False)
    led = await ProjectFactory.create_async(organization=t.org, key="LED", lead=gail)
    await ProjectMembershipFactory.create_async(project=led, user=gail)

    body = (await client.get("/api/projects/LED")).json()

    assert (body["lead_id"], body["lead_name"], body["lead_is_active"]) == (
        str(gail.id),
        "Gail Gone",
        False,
    )


async def test_the_lead_must_be_a_project_member(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    await admin_of_pmt(client, t)
    outsider = await org_member(t)

    response = await client.patch("/api/projects/PMT", json={"lead_id": str(outsider.id)})

    assert (response.status_code, fields(response.json())) == (
        422,
        [(["body", "lead_id"], "not_member")],
    )


async def test_a_member_becomes_lead_and_null_clears_the_lead(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    await admin_of_pmt(client, t)
    pia = await UserFactory.create_async(name="Pia Park")
    await ProjectMembershipFactory.create_async(project=t.project, user=pia)

    named = await client.patch("/api/projects/PMT", json={"lead_id": str(pia.id)})
    cleared = await client.patch("/api/projects/PMT", json={"lead_id": None})

    assert (named.json()["lead_id"], cleared.json()["lead_id"]) == (str(pia.id), None)
    # The new lead's name, not the one before the change (DL-111).
    assert (named.json()["lead_name"], cleared.json()["lead_name"]) == ("Pia Park", None)
    assert (await stored(session, "PMT")).lead_id is None
    assert [details for *_, details in await events(session)] == [
        {"old": {"lead_id": None}, "new": {"lead_id": str(pia.id)}},
        {"old": {"lead_id": str(pia.id)}, "new": {"lead_id": None}},
    ]


async def test_a_deactivated_member_cant_be_named_lead_but_an_existing_one_stays(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    await admin_of_pmt(client, t)
    gone = await UserFactory.create_async(is_active=False)
    await ProjectMembershipFactory.create_async(project=t.project, user=gone)
    stays = await UserFactory.create_async(is_active=False)
    await ProjectMembershipFactory.create_async(project=t.project, user=stays)
    project = await stored(session, "PMT")
    project.lead_id = stays.id
    await session.flush()

    naming = await client.patch("/api/projects/PMT", json={"lead_id": str(gone.id)})
    resaving = await client.patch(
        "/api/projects/PMT", json={"lead_id": str(stays.id), "name": "Payments 2"}
    )

    assert fields(naming.json()) == [(["body", "lead_id"], "account_inactive")]
    assert (resaving.status_code, resaving.json()["lead_id"]) == (200, str(stays.id))


async def test_a_blank_name_is_refused(client: AsyncClient, t: Tenancy) -> None:
    await admin_of_pmt(client, t)

    response = await client.patch("/api/projects/PMT", json={"name": " "})

    assert fields(response.json()) == [(["body", "name"], "missing")]


# --- Archive --------------------------------------------------------------------------------------


async def test_archiving_and_unarchiving_record_each_and_a_second_unarchive_nothing(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    admin = await admin_of_pmt(client, t)

    archived = await client.post("/api/projects/PMT/archive")
    after_archive = (await stored(session, "PMT")).archived_at
    unarchived = await client.post("/api/projects/PMT/unarchive")
    again = await client.post("/api/projects/PMT/unarchive")

    assert (archived.status_code, unarchived.status_code, again.status_code) == (204, 204, 204)
    assert after_archive is not None
    assert (await stored(session, "PMT")).archived_at is None
    assert [(a, actor) for a, actor, *_ in await events(session)] == [
        (AuditAction.PROJECT_ARCHIVED, admin.id),
        (AuditAction.PROJECT_UNARCHIVED, admin.id),
    ]


# --- The org's list -------------------------------------------------------------------------------


async def test_the_org_list_hides_archived_projects_unless_asked(
    client: AsyncClient, t: Tenancy
) -> None:
    await admin_of_pmt(client, t)
    await ProjectFactory.create_async(
        organization=t.org, key="ARC", name="Archive", archived_at=datetime.now(UTC)
    )

    live = await client.get(f"/api/orgs/{t.org.id}/projects")
    every = await client.get(
        f"/api/orgs/{t.org.id}/projects", params={"include_archived": "true", "sort": "key"}
    )

    assert [p["key"] for p in live.json()["items"]] == ["PMT"]
    assert [p["key"] for p in every.json()["items"]] == ["ARC", "PMT"]
    assert every.json()["items"][1]["organization_slug"] == "bolt-foods"


async def test_archived_only_lists_the_orgs_archived_projects_alone(
    client: AsyncClient, t: Tenancy
) -> None:
    """DL-181: the org overview's "Archived" section."""
    await admin_of_pmt(client, t)
    await ProjectFactory.create_async(
        organization=t.org, key="ARC", name="Archive", archived_at=datetime.now(UTC)
    )

    response = await client.get(f"/api/orgs/{t.org.id}/projects", params={"archived_only": "true"})

    assert [p["key"] for p in response.json()["items"]] == ["ARC"]


async def test_the_org_list_refuses_archived_only_with_include_archived(
    client: AsyncClient, t: Tenancy
) -> None:
    """DL-182, through the real endpoint."""
    await admin_of_pmt(client, t)

    response = await client.get(
        f"/api/orgs/{t.org.id}/projects",
        params={"archived_only": "true", "include_archived": "true"},
    )

    assert response.status_code == 422
    (field,) = response.json()["details"]["fields"]
    assert (field["loc"], field["type"]) == (["query", "archived_only"], "conflict")


async def test_each_listed_project_names_its_org_and_the_users_access(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    """DL-153: the explicit role where the user has one, else `inherited_admin`, on the org's
    list and My work's (one item model)."""
    admin = await admin_of_pmt(client, t)
    viewed = await ProjectFactory.create_async(organization=t.org, key="VWR", name="Viewed")
    await ProjectMembershipFactory.create_async(project=viewed, user=admin, role=ProjectRole.VIEWER)
    await session.flush()

    org_list = await client.get(f"/api/orgs/{t.org.id}/projects", params={"sort": "key"})
    my_work = await client.get("/api/me/work/projects", params={"sort": "key"})

    expected = [("PMT", "Bolt Foods", "inherited_admin"), ("VWR", "Bolt Foods", "viewer")]
    fields = ("key", "organization_name", "my_access")
    assert [tuple(p[f] for f in fields) for p in org_list.json()["items"]] == expected
    assert [tuple(p[f] for f in fields) for p in my_work.json()["items"]] == expected


async def test_each_listed_project_names_its_lead_or_none(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    """DL-153: the org's list, and My work's (one item model), carry the lead's name."""
    admin = await admin_of_pmt(client, t)
    lena = await UserFactory.create_async(name="Lena Lead")
    await ProjectMembershipFactory.create_async(project=t.project, user=lena)
    t.project.lead_id = lena.id
    unled = await ProjectFactory.create_async(organization=t.org, key="NOL", name="No lead")
    await ProjectMembershipFactory.create_async(project=unled, user=admin, role=ProjectRole.ADMIN)
    await session.flush()

    org_list = await client.get(f"/api/orgs/{t.org.id}/projects", params={"sort": "key"})
    my_work = await client.get("/api/me/work/projects", params={"sort": "key"})

    expected = [("NOL", None), ("PMT", "Lena Lead")]
    assert [(p["key"], p["lead_name"]) for p in org_list.json()["items"]] == expected
    assert [(p["key"], p["lead_name"]) for p in my_work.json()["items"]] == expected


async def test_the_org_list_holds_only_that_orgs_projects(client: AsyncClient, t: Tenancy) -> None:
    """A workspace admin sees every org's projects, but each org's list only its own."""
    admin = await UserFactory.create_async()
    await WorkspaceMembershipFactory.create_async(
        workspace=t.workspace, user=admin, role=WorkspaceRole.ADMIN
    )
    await signed_in(client, admin)
    other = await OrganizationFactory.create_async(workspace=t.workspace)
    await ProjectFactory.create_async(organization=other, key="LDG")

    response = await client.get(f"/api/orgs/{t.org.id}/projects")

    assert [p["key"] for p in response.json()["items"]] == ["PMT"]


async def test_the_org_list_filters_by_status(client: AsyncClient, t: Tenancy) -> None:
    await admin_of_pmt(client, t)
    await ProjectFactory.create_async(organization=t.org, key="ACT", status="active")

    response = await client.get(f"/api/orgs/{t.org.id}/projects", params={"status": "active"})

    assert [p["key"] for p in response.json()["items"]] == ["ACT"]


@pytest.mark.security
async def test_the_org_list_is_a_404_for_an_org_the_user_cant_see(
    client: AsyncClient, t: Tenancy
) -> None:
    await signed_in(client, await UserFactory.create_async())

    response = await client.get(f"/api/orgs/{t.org.id}/projects")

    assert (response.status_code, response.json()["code"]) == (404, "not_found")
    assert "Payments" not in response.text


# --- Module guidance ------------------------------------------------------------------------------


async def test_module_guidance_lists_every_module_and_each_types_recommendations(
    client: AsyncClient, t: Tenancy
) -> None:
    await signed_in(client, await org_member(t))

    body = (await client.get("/api/module-guidance")).json()

    assert [(m["module"], m["available"], bool(m["note"])) for m in body["modules"]] == [
        (m, False, True)
        for m in [
            "sprints",
            "github",
            "raid",
            "status_reports",
            "budget",
            "data_migration",
            "cutover",
        ]
    ]
    assert {r["type"]: r["recommended"] for r in body["types"]} == {
        "software": ["sprints", "github"],
        "erp": ["raid", "status_reports", "budget", "data_migration", "cutover"],
        "general": [],
    }


@pytest.mark.security
@pytest.mark.parametrize("path", ["/api/module-guidance", "/api/me/work", "/api/me/work/projects"])
async def test_signed_in_endpoints_need_a_session(client: AsyncClient, path: str) -> None:
    response = await client.get(path)

    assert (response.status_code, response.json()["code"]) == (401, "not_authenticated")


# --- My work --------------------------------------------------------------------------------------


async def test_my_work_shows_the_first_ten_projects_and_the_total(
    client: AsyncClient, t: Tenancy
) -> None:
    pia = await signed_in(client, await UserFactory.create_async())
    await projects_of(pia, t, 11)
    archived = await ProjectFactory.create_async(
        organization=t.org, key="ARC", archived_at=datetime.now(UTC)
    )
    await ProjectMembershipFactory.create_async(project=archived, user=pia)

    response = await client.get("/api/me/work")

    projects = response.json()["sections"]["projects"]
    assert (projects["available"], projects["total"]) == (True, 11)
    assert [p["key"] for p in projects["items"]] == [f"P{n:02d}" for n in range(10)]
    assert projects["items"][0]["organization_slug"] == "bolt-foods"


async def test_my_projects_page_through_the_rest(client: AsyncClient, t: Tenancy) -> None:
    pia = await signed_in(client, await UserFactory.create_async())
    await projects_of(pia, t, 3)

    response = await client.get("/api/me/work/projects", params={"limit": 2, "offset": 2})

    assert ([p["key"] for p in response.json()["items"]], response.json()["total"]) == (["P02"], 3)


async def test_a_section_whose_query_fails_is_unavailable(
    client: AsyncClient, t: Tenancy, monkeypatch: pytest.MonkeyPatch
) -> None:
    await signed_in(client, await UserFactory.create_async())

    real = ProjectRepository.visible

    def failing(self: ProjectRepository, scope: Scope, **options: bool) -> Select[Project]:
        # A query Postgres rejects (no such column), so the savepoint really rolls back.
        return real(self, scope, **options).where(text("no_such_column = 1"))

    monkeypatch.setattr(ProjectRepository, "visible", failing)

    response = await client.get("/api/me/work")

    assert (response.status_code, response.json()) == (
        200,
        {"sections": {"projects": {"available": False, "items": [], "total": 0}}},
    )


# --- The first-admin picker (DL-152) -------------------------------------------------------------


async def test_first_admin_candidates_are_the_orgs_active_members_and_the_staff(
    client: AsyncClient, t: Tenancy
) -> None:
    await signed_in(client, await org_member(t, OrgRole.ADMIN, name="Ada Admin"))
    await org_member(t, name="Bob Baker")
    await org_member(t, name="Eve Gone", is_active=False)
    dan = await UserFactory.create_async(name="Dan Diaz")
    await WorkspaceMembershipFactory.create_async(
        workspace=t.workspace, user=dan, role=WorkspaceRole.MEMBER
    )
    elsewhere = await OrganizationFactory.create_async(workspace=t.workspace)
    olly = await UserFactory.create_async(name="Olly Other")
    await MembershipFactory.create_async(organization=elsewhere, user=olly, role=OrgRole.MEMBER)

    response = await client.get(f"/api/orgs/{t.org.id}/first-admin-candidates")

    assert response.status_code == 200
    assert [c["name"] for c in response.json()["items"]] == ["Ada Admin", "Bob Baker", "Dan Diaz"]
    assert response.json()["total"] == 3


async def test_first_admin_candidates_search_names(client: AsyncClient, t: Tenancy) -> None:
    await signed_in(client, await org_member(t, OrgRole.ADMIN, name="Ada Admin"))
    await org_member(t, name="Bob Baker")

    response = await client.get(f"/api/orgs/{t.org.id}/first-admin-candidates?q=bob")

    assert [c["name"] for c in response.json()["items"]] == ["Bob Baker"]


@pytest.mark.security
async def test_an_org_member_cant_list_first_admin_candidates(
    client: AsyncClient, t: Tenancy
) -> None:
    """Naming a first admin is for org owners and admins (DL-77): a member sees the org, so 403."""
    await signed_in(client, await org_member(t, OrgRole.MEMBER))

    response = await client.get(f"/api/orgs/{t.org.id}/first-admin-candidates")

    assert (response.status_code, response.json()["code"]) == (403, "forbidden")


@pytest.mark.security
async def test_first_admin_candidates_are_404_outside_the_org(
    client: AsyncClient, t: Tenancy
) -> None:
    elsewhere = await OrganizationFactory.create_async(workspace=t.workspace)
    outsider = await UserFactory.create_async()
    await MembershipFactory.create_async(organization=elsewhere, user=outsider, role=OrgRole.ADMIN)
    await signed_in(client, outsider)

    response = await client.get(f"/api/orgs/{t.org.id}/first-admin-candidates")

    assert (response.status_code, response.json()["code"]) == (404, "not_found")
    assert "Bolt Foods" not in response.text
