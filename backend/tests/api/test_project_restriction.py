"""Restriction and export control beyond who may call it (design-doc §3.1; build plan, "The
restriction API"; DL-81): the confirmations on create, on a restriction change, and on every
member add; their 422s; what each records; and `access` in both access reviews. Who gets
2xx/403/404 is in tests/api/authz/test_restriction.py (spec tests)."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import AuditAction, OrgRole, ProjectRole, RestrictionLevel, WorkspaceRole
from app.models.audit_event import AuditEvent
from app.models.project import Project, ProjectMembership
from app.models.user import User
from tests.factories.org import MembershipFactory
from tests.factories.project import ProjectFactory, ProjectMembershipFactory
from tests.factories.user import UserFactory
from tests.factories.workspace import WorkspaceMembershipFactory
from tests.support.authz import Tenancy, sign_in_as, tenancy

pytestmark = [pytest.mark.anyio, pytest.mark.security, pytest.mark.usefixtures("session")]

RESTRICTION = "/api/projects/PMT/restriction"
MEMBERS = "/api/projects/PMT/members"
EC = "export_controlled"
OLGA = uuid.UUID("01900000-0000-7000-8000-00000000000a")
OTTO = uuid.UUID("01900000-0000-7000-8000-00000000000b")
VIV = uuid.UUID("01900000-0000-7000-8000-00000000000c")
ADA = uuid.UUID("01900000-0000-7000-8000-00000000000d")


@pytest.fixture
async def t() -> Tenancy:
    return await tenancy()


@pytest.fixture
async def admin(client: AsyncClient, t: Tenancy) -> User:
    """PMT's explicit admin, signed in."""
    user = await UserFactory.create_async(id=ADA, name="Ada Admin")
    await ProjectMembershipFactory.create_async(
        project=t.project, user=user, role=ProjectRole.ADMIN
    )
    await sign_in_as(client, user)
    return user


async def export_controlled(session: AsyncSession, t: Tenancy) -> None:
    t.project.restriction_categories = [EC]
    await session.flush()


async def org_member(t: Tenancy, **user: object) -> User:
    person = await UserFactory.create_async(**user)
    await MembershipFactory.create_async(organization=t.org, user=person, role=OrgRole.MEMBER)
    return person


async def stored(session: AsyncSession, key: str = "PMT") -> tuple[object, list[str]]:
    statement = (
        select(Project.restriction_level, Project.restriction_categories)
        .where(Project.key == key)
        .execution_options(populate_existing=True)
    )
    return tuple((await session.execute(statement)).one())  # pyright: ignore[reportReturnType]


async def project_member_ids(session: AsyncSession, t: Tenancy) -> set[object]:
    rows = await session.scalars(
        select(ProjectMembership.user_id).where(ProjectMembership.project_id == t.project.id)
    )
    return set(rows)


async def events(session: AsyncSession) -> list[tuple[object, ...]]:
    rows = await session.execute(
        select(AuditEvent.action, AuditEvent.target_user_id, AuditEvent.details).order_by(
            AuditEvent.id
        )
    )
    return [tuple(row) for row in rows]


def fields(body: dict[str, object]) -> list[tuple[list[object], str]]:
    return [(e["loc"], e["type"]) for e in body["details"]["fields"]]  # pyright: ignore[reportIndexIssue, reportUnknownVariableType, reportArgumentType]


# --- Create (DL-81) -------------------------------------------------------------------------------


def new(**values: object) -> dict[str, object]:
    return {"name": "Invoicing", "key": "INV", "type": "software", **values}


async def test_a_project_created_with_a_restriction_stores_and_records_its_restriction(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    olga = await org_member(t)
    await sign_in_as(client, olga)

    response = await client.post(
        f"/api/orgs/{t.org.id}/projects",
        json=new(restriction_level="confidential", restriction_categories=["pii", "financial"]),
    )

    assert response.status_code == 201
    body = response.json()
    assert (body["restriction_level"], body["restriction_categories"]) == (
        "confidential",
        ["financial", "pii"],
    )
    assert await stored(session, "INV") == (RestrictionLevel.CONFIDENTIAL, ["financial", "pii"])
    assert await events(session) == [
        (
            AuditAction.PROJECT_CREATED,
            None,
            {
                "restriction_level": "confidential",
                "restriction_categories": ["financial", "pii"],
            },
        ),
        (AuditAction.PROJECT_MEMBER_ADDED, olga.id, {"role": "admin"}),
    ]


async def test_a_project_created_export_controlled_records_the_first_admins_confirmation(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    olga = await org_member(t)
    await sign_in_as(client, olga)

    response = await client.post(
        f"/api/orgs/{t.org.id}/projects",
        json=new(
            restriction_categories=[EC],
            export_control_confirmed=True,
            confirmed_member_ids=[str(olga.id)],
        ),
    )

    assert response.status_code == 201
    assert await stored(session, "INV") == (None, [EC])
    assert await events(session) == [
        (
            AuditAction.PROJECT_CREATED,
            None,
            {
                "restriction_level": None,
                "restriction_categories": [EC],
                "export_control_confirmed": True,
                "confirmed_member_ids": [str(olga.id)],
            },
        ),
        (
            AuditAction.PROJECT_MEMBER_ADDED,
            olga.id,
            {"role": "admin", "export_control_confirmed": True},
        ),
    ]


async def test_confirming_the_creator_instead_of_the_named_first_admin_is_refused(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    """Named by an org admin, the first admin (not the creator) is the only explicit member."""
    olga = await UserFactory.create_async(id=OLGA)
    await MembershipFactory.create_async(organization=t.org, user=olga, role=OrgRole.ADMIN)
    await org_member(t, id=OTTO)
    await sign_in_as(client, olga)

    response = await client.post(
        f"/api/orgs/{t.org.id}/projects",
        json=new(
            first_admin_id=str(OTTO),
            restriction_categories=[EC],
            export_control_confirmed=True,
            confirmed_member_ids=[str(OLGA)],
        ),
    )

    assert (response.status_code, fields(response.json())) == (
        422,
        [(["body", "confirmed_member_ids"], "members_changed")],
    )
    assert await session.scalar(select(Project.id).where(Project.key == "INV")) is None


async def test_the_named_first_admins_confirmation_is_recorded(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    olga = await UserFactory.create_async(id=OLGA)
    await MembershipFactory.create_async(organization=t.org, user=olga, role=OrgRole.ADMIN)
    await org_member(t, id=OTTO)
    await sign_in_as(client, olga)

    response = await client.post(
        f"/api/orgs/{t.org.id}/projects",
        json=new(
            first_admin_id=str(OTTO),
            restriction_categories=[EC],
            export_control_confirmed=True,
            confirmed_member_ids=[str(OTTO)],
        ),
    )

    assert response.status_code == 201
    assert [e[2] for e in await events(session) if e[0] is AuditAction.PROJECT_CREATED] == [
        {
            "restriction_level": None,
            "restriction_categories": [EC],
            "export_control_confirmed": True,
            "confirmed_member_ids": [str(OTTO)],
        }
    ]


@pytest.mark.parametrize(
    ("confirmation", "expected"),
    [
        (
            {},
            [
                (["body", "export_control_confirmed"], "confirmation_required"),
                (["body", "confirmed_member_ids"], "confirmation_required"),
            ],
        ),
        (
            {"export_control_confirmed": False, "confirmed_member_ids": [str(OLGA)]},
            [(["body", "export_control_confirmed"], "confirmation_required")],
        ),
        (
            {"export_control_confirmed": True},
            [(["body", "confirmed_member_ids"], "confirmation_required")],
        ),
        (
            {"export_control_confirmed": True, "confirmed_member_ids": [str(OTTO)]},
            [(["body", "confirmed_member_ids"], "members_changed")],
        ),
        (
            {"export_control_confirmed": True, "confirmed_member_ids": [str(OLGA), str(OTTO)]},
            [(["body", "confirmed_member_ids"], "members_changed")],
        ),
    ],
)
async def test_creating_a_project_export_controlled_needs_the_confirmation(
    client: AsyncClient,
    session: AsyncSession,
    t: Tenancy,
    confirmation: dict[str, object],
    expected: list[tuple[list[str], str]],
) -> None:
    await sign_in_as(client, await org_member(t, id=OLGA))
    await org_member(t, id=OTTO)

    response = await client.post(
        f"/api/orgs/{t.org.id}/projects", json=new(restriction_categories=[EC], **confirmation)
    )

    assert (response.status_code, fields(response.json())) == (422, expected)
    assert await session.scalar(select(Project.id).where(Project.key == "INV")) is None
    assert await events(session) == []


@pytest.mark.parametrize(
    ("confirmation", "expected"),
    [
        (
            {"export_control_confirmed": True},
            [(["body", "export_control_confirmed"], "confirmation_not_needed")],
        ),
        (
            {"export_control_confirmed": False, "confirmed_member_ids": []},
            [
                (["body", "export_control_confirmed"], "confirmation_not_needed"),
                (["body", "confirmed_member_ids"], "confirmation_not_needed"),
            ],
        ),
    ],
)
async def test_a_confirmation_on_a_project_created_without_export_control_is_refused(
    client: AsyncClient,
    session: AsyncSession,
    t: Tenancy,
    confirmation: dict[str, object],
    expected: list[tuple[list[str], str]],
) -> None:
    await sign_in_as(client, await org_member(t))

    response = await client.post(
        f"/api/orgs/{t.org.id}/projects",
        json=new(restriction_categories=["pii"], **confirmation),
    )

    assert (response.status_code, fields(response.json())) == (422, expected)
    assert await session.scalar(select(Project.id).where(Project.key == "INV")) is None


# --- PUT /restriction (DL-81) ------------------------------------------------------------------


async def test_a_restriction_change_stores_and_records_old_and_new(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    t.project.restriction_level = RestrictionLevel.INTERNAL
    t.project.restriction_categories = ["financial"]
    await session.flush()

    response = await client.put(
        RESTRICTION, json={"level": "confidential", "categories": ["pii", "pii"]}
    )

    assert response.status_code == 200
    assert (
        response.json()["restriction_level"],
        response.json()["restriction_categories"],
    ) == (
        "confidential",
        ["pii"],
    )
    assert await stored(session) == (RestrictionLevel.CONFIDENTIAL, ["pii"])
    assert await events(session) == [
        (
            AuditAction.PROJECT_RESTRICTION_CHANGED,
            None,
            {
                "old": {
                    "restriction_level": "internal",
                    "restriction_categories": ["financial"],
                },
                "new": {"restriction_level": "confidential", "restriction_categories": ["pii"]},
            },
        )
    ]


async def test_the_removed_restricted_level_is_refused(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    """DL-134 removed Restricted: an enum still holding it would store it."""
    response = await client.put(RESTRICTION, json={"level": "restricted", "categories": []})

    assert (response.status_code, fields(response.json())) == (422, [(["body", "level"], "enum")])
    assert await stored(session) == (None, [])
    assert await events(session) == []


async def test_the_restriction_already_held_records_nothing(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    t.project.restriction_level = RestrictionLevel.CONFIDENTIAL
    t.project.restriction_categories = ["pii", "financial"]
    await session.flush()

    response = await client.put(
        RESTRICTION, json={"level": "confidential", "categories": ["financial", "pii"]}
    )

    assert response.status_code == 200
    assert await events(session) == []


async def test_marking_a_project_export_controlled_records_the_confirmed_members(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User
) -> None:
    viv = await UserFactory.create_async()
    await ProjectMembershipFactory.create_async(
        project=t.project, user=viv, role=ProjectRole.VIEWER
    )

    response = await client.put(
        RESTRICTION,
        json={
            "level": None,
            "categories": [EC],
            "export_control_confirmed": True,
            "confirmed_member_ids": [str(viv.id), str(admin.id)],
        },
    )

    assert response.status_code == 200
    assert await stored(session) == (None, [EC])
    assert await events(session) == [
        (
            AuditAction.PROJECT_RESTRICTION_CHANGED,
            None,
            {
                "old": {"restriction_level": None, "restriction_categories": []},
                "new": {"restriction_level": None, "restriction_categories": [EC]},
                "export_control_confirmed": True,
                "confirmed_member_ids": sorted([str(viv.id), str(admin.id)]),
            },
        )
    ]


@pytest.mark.parametrize(
    ("confirmation", "expected"),
    [
        (
            {},
            [
                (["body", "export_control_confirmed"], "confirmation_required"),
                (["body", "confirmed_member_ids"], "confirmation_required"),
            ],
        ),
        (
            {"export_control_confirmed": True, "confirmed_member_ids": [str(ADA)]},
            [(["body", "confirmed_member_ids"], "members_changed")],
        ),
        (
            {
                "export_control_confirmed": True,
                "confirmed_member_ids": [str(ADA), str(VIV), str(OTTO)],
            },
            [(["body", "confirmed_member_ids"], "members_changed")],
        ),
    ],
)
async def test_marking_a_project_export_controlled_needs_its_current_members_confirmed(
    client: AsyncClient,
    session: AsyncSession,
    t: Tenancy,
    admin: User,
    confirmation: dict[str, object],
    expected: list[tuple[list[str], str]],
) -> None:
    viv = await UserFactory.create_async(id=VIV)
    await ProjectMembershipFactory.create_async(
        project=t.project, user=viv, role=ProjectRole.VIEWER
    )
    await UserFactory.create_async(id=OTTO)  # not on the project

    response = await client.put(
        RESTRICTION, json={"level": None, "categories": [EC], **confirmation}
    )

    assert (response.status_code, fields(response.json())) == (422, expected)
    assert await stored(session) == (None, [])
    assert await events(session) == []


@pytest.mark.parametrize("already", [False, True])
async def test_a_confirmation_where_no_export_control_is_added_is_refused(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User, already: bool
) -> None:
    """Without `export_controlled`, or keeping it (not adding it)."""
    categories = [EC] if already else []
    t.project.restriction_categories = categories
    await session.flush()

    response = await client.put(
        RESTRICTION,
        json={
            "level": "confidential",
            "categories": categories,
            "export_control_confirmed": True,
            "confirmed_member_ids": [str(admin.id)],
        },
    )

    assert (response.status_code, fields(response.json())) == (
        422,
        [
            (["body", "export_control_confirmed"], "confirmation_not_needed"),
            (["body", "confirmed_member_ids"], "confirmation_not_needed"),
        ],
    )
    assert await stored(session) == (None, categories)


# --- Member adds on an export-controlled project (DL-81) ------------------------------------------


@pytest.mark.parametrize("path", ["user_id", "email", "new"])
async def test_every_member_add_to_an_export_controlled_project_needs_the_confirmation(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User, path: str
) -> None:
    await export_controlled(session, t)
    bob = await org_member(t, email="bob@bolt.example")
    url, body = _add(path, bob)

    response = await client.post(url, json=body)

    assert (response.status_code, fields(response.json())) == (
        422,
        [(["body", "export_control_confirmed"], "confirmation_required")],
    )
    assert await project_member_ids(session, t) == {admin.id}
    assert await events(session) == []


@pytest.mark.parametrize("path", ["user_id", "email", "new"])
async def test_a_confirmed_member_add_records_the_confirmation(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User, path: str
) -> None:
    await export_controlled(session, t)
    bob = await org_member(t, email="bob@bolt.example")
    url, body = _add(path, bob)

    response = await client.post(url, json={**body, "export_control_confirmed": True})

    assert response.status_code == 201
    added = [e for e in await events(session) if e[0] is AuditAction.PROJECT_MEMBER_ADDED]
    assert [e[2] for e in added] == [{"role": "viewer", "export_control_confirmed": True}]
    assert len(await project_member_ids(session, t)) == 2


@pytest.mark.parametrize("path", ["user_id", "email", "new"])
async def test_a_confirmation_on_a_member_add_without_export_control_is_refused(
    client: AsyncClient, session: AsyncSession, t: Tenancy, admin: User, path: str
) -> None:
    bob = await org_member(t, email="bob@bolt.example")
    url, body = _add(path, bob)

    response = await client.post(url, json={**body, "export_control_confirmed": True})

    assert (response.status_code, fields(response.json())) == (
        422,
        [(["body", "export_control_confirmed"], "confirmation_not_needed")],
    )
    assert await project_member_ids(session, t) == {admin.id}


def _add(path: str, bob: User) -> tuple[str, dict[str, object]]:
    """A viewer add by `path`: the picker (`user_id`), email first, or a new account."""
    match path:
        case "user_id":
            return MEMBERS, {"user_id": str(bob.id), "role": "viewer"}
        case "email":
            return MEMBERS, {"email": bob.email, "role": "viewer"}
        case _:
            return f"{MEMBERS}/new", {
                "email": "nina@bolt.example",
                "username": "nina-new",
                "name": "Nina New",
                "password": "temporary-pass-1",
                "role": "viewer",
            }


# --- Access reviews (DL-81) -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("categories", "expected"),
    [
        (
            [EC],
            [
                ("Ada Admin", "content"),
                ("Olga Orgadmin", "management"),
                ("Vera Viewer", "content"),
                ("Wendy Owner", "management"),
            ],
        ),
        (
            ["pii"],
            [
                ("Ada Admin", "content"),
                ("Olga Orgadmin", "content"),
                ("Vera Viewer", "content"),
                ("Wendy Owner", "content"),
            ],
        ),
    ],
)
async def test_the_project_review_shows_inherited_admins_as_management_on_export_control(
    client: AsyncClient,
    session: AsyncSession,
    t: Tenancy,
    admin: User,
    categories: list[str],
    expected: list[tuple[str, str]],
) -> None:
    t.project.restriction_categories = categories
    await session.flush()
    olga = await UserFactory.create_async(name="Olga Orgadmin")
    await MembershipFactory.create_async(organization=t.org, user=olga, role=OrgRole.ADMIN)
    vera = await UserFactory.create_async(name="Vera Viewer")
    await MembershipFactory.create_async(organization=t.org, user=vera, role=OrgRole.ADMIN)
    await ProjectMembershipFactory.create_async(
        project=t.project, user=vera, role=ProjectRole.VIEWER
    )
    wendy = await UserFactory.create_async(name="Wendy Owner")
    await WorkspaceMembershipFactory.create_async(
        workspace=t.workspace, user=wendy, role=WorkspaceRole.OWNER
    )

    response = await client.get("/api/projects/PMT/access")

    assert response.status_code == 200
    assert [(p["user"]["name"], p["access"]) for p in response.json()["people"]] == expected


async def test_the_person_review_shows_management_on_export_controlled_projects_without_a_role(
    client: AsyncClient, session: AsyncSession, t: Tenancy
) -> None:
    await export_controlled(session, t)
    await ProjectFactory.create_async(organization=t.org, key="LDG", name="Ledger")
    secret = await ProjectFactory.create_async(
        organization=t.org, key="SEC", name="Secret", restriction_categories=[EC]
    )
    olga = await UserFactory.create_async(name="Olga Orgadmin")
    await MembershipFactory.create_async(organization=t.org, user=olga, role=OrgRole.ADMIN)
    await ProjectMembershipFactory.create_async(project=secret, user=olga, role=ProjectRole.VIEWER)
    await sign_in_as(client, olga)

    response = await client.get(f"/api/users/{olga.id}/access")

    assert response.status_code == 200
    assert [
        (p["key"], p["export_controlled"], p["access"]) for p in response.json()["projects"]
    ] == [
        ("LDG", False, "content"),
        ("PMT", True, "management"),
        ("SEC", True, "content"),
    ]
