"""Creating, reading, and updating orgs, beyond who may call each endpoint (the authz spec tests
cover that): the first owner, the audit events, and the errors (build plan, "The workspace and
org API", DL-55; design-doc §4, §10.1)."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import AuditAction, AuditEntityType, OrgRole, WorkspaceRole
from app.models.audit_event import AuditEvent
from app.models.org import Membership, Organization
from app.models.user import User
from app.models.workspace import Workspace
from tests.factories.org import OrganizationFactory
from tests.factories.user import UserFactory
from tests.factories.workspace import WorkspaceFactory, WorkspaceMembershipFactory
from tests.support.authz import sign_in_as

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("session")]


@pytest.fixture
async def workspace() -> Workspace:
    return await WorkspaceFactory.create_async()


async def admin_of(client: AsyncClient, workspace: Workspace) -> User:
    user = await UserFactory.create_async()
    await WorkspaceMembershipFactory.create_async(
        workspace=workspace, user=user, role=WorkspaceRole.ADMIN
    )
    await sign_in_as(client, user)
    return user


async def events(session: AsyncSession) -> list[tuple[object, ...]]:
    rows = await session.execute(
        select(
            AuditEvent.action,
            AuditEvent.actor_id,
            AuditEvent.workspace_id,
            AuditEvent.organization_id,
            AuditEvent.target_user_id,
            AuditEvent.entity_type,
            AuditEvent.details,
        ).order_by(AuditEvent.id)
    )
    return [tuple(row) for row in rows]


def fields(body: dict[str, object]) -> list[tuple[list[object], str]]:
    details = body["details"]
    assert isinstance(details, dict)
    return [(f["loc"], f["type"]) for f in details["fields"]]  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]


async def count(session: AsyncSession, model: type[object]) -> int:
    return (await session.execute(select(func.count()).select_from(model))).scalar_one()


async def owners(session: AsyncSession, org_id: uuid.UUID) -> list[uuid.UUID]:
    return list(
        await session.scalars(
            select(Membership.user_id).where(
                Membership.organization_id == org_id, Membership.role == OrgRole.OWNER
            )
        )
    )


# --- Create ---------------------------------------------------------------------------------


async def test_creating_an_org_with_an_existing_owner(
    client: AsyncClient, session: AsyncSession, workspace: Workspace
) -> None:
    admin = await admin_of(client, workspace)
    cleo = await UserFactory.create_async()

    response = await client.post(
        f"/api/workspaces/{workspace.id}/orgs",
        json={"name": "Bolt Foods", "slug": "bolt", "owner_id": str(cleo.id)},
    )

    assert response.status_code == 201
    org_id = uuid.UUID(response.json()["id"])
    assert (response.json()["name"], response.json()["slug"]) == ("Bolt Foods", "bolt")
    assert await owners(session, org_id) == [cleo.id]
    assert await events(session) == [
        (
            AuditAction.ORG_CREATED,
            admin.id,
            workspace.id,
            org_id,
            None,
            AuditEntityType.ORGANIZATION,
            {"name": "Bolt Foods", "slug": "bolt"},
        ),
        (
            AuditAction.ORG_MEMBER_ADDED,
            admin.id,
            workspace.id,
            org_id,
            cleo.id,
            AuditEntityType.ORGANIZATION,
            {"role": "owner"},
        ),
    ]


async def test_creating_an_org_with_a_new_owner_creates_the_account(
    client: AsyncClient, session: AsyncSession, workspace: Workspace
) -> None:
    admin = await admin_of(client, workspace)

    response = await client.post(
        f"/api/workspaces/{workspace.id}/orgs",
        json={
            "name": "Bolt Foods",
            "slug": "bolt",
            "new_owner": {
                "email": "Cleo@Bolt.example",
                "username": "cleo",
                "name": "Cleo Park",
                "password": "a temporary passphrase",
            },
        },
    )

    assert response.status_code == 201
    cleo = (await session.execute(select(User).where(User.username == "cleo"))).scalar_one()
    assert (cleo.email, cleo.must_change_password) == ("cleo@bolt.example", True)
    assert await owners(session, uuid.UUID(response.json()["id"])) == [cleo.id]
    assert [
        (action, actor, target) for action, actor, _, _, target, *_ in await events(session)
    ] == [
        (AuditAction.USER_CREATED, admin.id, cleo.id),
        (AuditAction.ORG_CREATED, admin.id, None),
        (AuditAction.ORG_MEMBER_ADDED, admin.id, cleo.id),
    ]


@pytest.mark.parametrize(
    "owner",
    [
        {},
        {
            "owner_id": "00000000-0000-0000-0000-000000000001",
            "new_owner": {
                "email": "a@b.example",
                "username": "ab",
                "name": "A",
                "password": "x" * 9,
            },
        },
    ],
    ids=["neither", "both"],
)
async def test_an_org_needs_exactly_one_owner(
    client: AsyncClient, session: AsyncSession, workspace: Workspace, owner: dict[str, object]
) -> None:
    await admin_of(client, workspace)

    response = await client.post(
        f"/api/workspaces/{workspace.id}/orgs", json={"name": "Bolt", "slug": "bolt", **owner}
    )

    assert (response.status_code, fields(response.json())) == (
        422,
        [(["body", "owner_id"], "one_owner")],
    )
    assert await count(session, Organization) == 0


async def test_an_unknown_owner_is_a_404(
    client: AsyncClient, session: AsyncSession, workspace: Workspace
) -> None:
    await admin_of(client, workspace)

    response = await client.post(
        f"/api/workspaces/{workspace.id}/orgs",
        json={"name": "Bolt", "slug": "bolt", "owner_id": str(uuid.uuid4())},
    )

    assert (response.status_code, response.json()["code"]) == (404, "not_found")
    assert await count(session, Organization) == 0


async def test_a_deactivated_owner_is_a_422(
    client: AsyncClient, session: AsyncSession, workspace: Workspace
) -> None:
    await admin_of(client, workspace)
    gone = await UserFactory.create_async(is_active=False)

    response = await client.post(
        f"/api/workspaces/{workspace.id}/orgs",
        json={"name": "Bolt", "slug": "bolt", "owner_id": str(gone.id)},
    )

    assert (response.status_code, fields(response.json())) == (
        422,
        [(["body", "owner_id"], "account_inactive")],
    )
    assert await count(session, Organization) == 0


async def test_a_new_owners_problems_are_reported_inside_new_owner(
    client: AsyncClient, session: AsyncSession, workspace: Workspace
) -> None:
    await admin_of(client, workspace)
    users_before = await count(session, User)

    response = await client.post(
        f"/api/workspaces/{workspace.id}/orgs",
        json={
            "name": "Bolt",
            "slug": "bolt",
            "new_owner": {"email": "nope", "username": "cleo", "name": "Cleo", "password": "short"},
        },
    )

    assert (response.status_code, fields(response.json())) == (
        422,
        [
            (["body", "new_owner", "email"], "invalid_email"),
            (["body", "new_owner", "password"], "too_short"),
        ],
    )
    assert (await count(session, User), await count(session, Organization)) == (users_before, 0)


@pytest.mark.parametrize(
    ("body", "field", "type_"),
    [
        ({"name": "Bolt", "slug": "status"}, "slug", "reserved"),
        ({"name": "", "slug": "bolt"}, "name", "missing"),
    ],
)
async def test_an_invalid_org_name_or_slug_is_a_422(
    client: AsyncClient,
    workspace: Workspace,
    body: dict[str, str],
    field: str,
    type_: str,
) -> None:
    await admin_of(client, workspace)
    cleo = await UserFactory.create_async()

    response = await client.post(
        f"/api/workspaces/{workspace.id}/orgs", json={**body, "owner_id": str(cleo.id)}
    )

    assert (response.status_code, fields(response.json())) == (422, [(["body", field], type_)])


async def test_an_org_slug_taken_in_the_workspace_is_a_422(
    client: AsyncClient, workspace: Workspace
) -> None:
    await admin_of(client, workspace)
    await OrganizationFactory.create_async(workspace=workspace, slug="bolt")
    cleo = await UserFactory.create_async()

    response = await client.post(
        f"/api/workspaces/{workspace.id}/orgs",
        json={"name": "Bolt", "slug": "bolt", "owner_id": str(cleo.id)},
    )

    assert (response.status_code, fields(response.json())) == (422, [(["body", "slug"], "taken")])


@pytest.mark.parametrize(
    ("slug", "expected"),
    [
        ("fresh", {"available": True, "problem": None}),
        ("bolt", {"available": False, "problem": "taken"}),
        ("elsewhere", {"available": True, "problem": None}),
        ("api", {"available": False, "problem": "reserved"}),
    ],
    ids=["free", "taken-here", "taken-in-another-workspace", "reserved"],
)
async def test_new_org_slug_availability(
    client: AsyncClient, workspace: Workspace, slug: str, expected: dict[str, object]
) -> None:
    await admin_of(client, workspace)
    await OrganizationFactory.create_async(workspace=workspace, slug="bolt")
    await OrganizationFactory.create_async(slug="elsewhere")

    response = await client.get(
        f"/api/workspaces/{workspace.id}/org-slug-availability", params={"slug": slug}
    )

    assert response.json() == expected


# --- Read and update ----------------------------------------------------------------------------


async def test_renaming_an_org_records_old_and_new_values(
    client: AsyncClient, session: AsyncSession, workspace: Workspace
) -> None:
    admin = await admin_of(client, workspace)
    org = await OrganizationFactory.create_async(workspace=workspace, name="Bolt", slug="bolt")

    response = await client.patch(f"/api/orgs/{org.id}", json={"name": "Bolt Foods"})

    assert (response.status_code, response.json()["name"]) == (200, "Bolt Foods")
    assert await session.scalar(select(Organization.name)) == "Bolt Foods"
    assert await events(session) == [
        (
            AuditAction.ORG_UPDATED,
            admin.id,
            workspace.id,
            org.id,
            None,
            AuditEntityType.ORGANIZATION,
            {"old": {"name": "Bolt"}, "new": {"name": "Bolt Foods"}},
        )
    ]


async def test_an_org_slug_another_org_in_the_workspace_has_is_a_422(
    client: AsyncClient, workspace: Workspace
) -> None:
    await admin_of(client, workspace)
    org = await OrganizationFactory.create_async(workspace=workspace, slug="bolt")
    await OrganizationFactory.create_async(workspace=workspace, slug="cove")

    response = await client.patch(f"/api/orgs/{org.id}", json={"slug": "cove"})

    assert (response.status_code, fields(response.json())) == (422, [(["body", "slug"], "taken")])


@pytest.mark.parametrize(
    ("slug", "expected"),
    [
        ("bolt", {"available": True, "problem": None}),
        ("cove", {"available": False, "problem": "taken"}),
    ],
    ids=["own", "another-orgs"],
)
async def test_an_orgs_own_slug_counts_as_available(
    client: AsyncClient, workspace: Workspace, slug: str, expected: dict[str, object]
) -> None:
    await admin_of(client, workspace)
    org = await OrganizationFactory.create_async(workspace=workspace, slug="bolt")
    await OrganizationFactory.create_async(workspace=workspace, slug="cove")

    response = await client.get(f"/api/orgs/{org.id}/slug-availability", params={"slug": slug})

    assert response.json() == expected


@pytest.mark.parametrize(
    ("taken", "field"),
    [({"email": "cleo@bolt.example"}, "email"), ({"username": "cleo"}, "username")],
)
async def test_a_new_owners_taken_email_or_username_is_reported_inside_new_owner(
    client: AsyncClient,
    session: AsyncSession,
    workspace: Workspace,
    taken: dict[str, str],
    field: str,
) -> None:
    """Where the org form shows it: next to the new owner's field, not the org's."""
    await admin_of(client, workspace)
    await UserFactory.create_async(email="cleo@bolt.example", username="cleo")
    new_owner = {
        "email": "other@bolt.example",
        "username": "other",
        "name": "Cleo Park",
        "password": "a temporary passphrase",
        **taken,
    }

    response = await client.post(
        f"/api/workspaces/{workspace.id}/orgs",
        json={"name": "Bolt", "slug": "bolt", "new_owner": new_owner},
    )

    assert (response.status_code, fields(response.json())) == (
        422,
        [(["body", "new_owner", field], "taken")],
    )
    assert await count(session, Organization) == 0
