"""A requirement's revisions (design-doc §6.1; DL-145; build plan, S2-C9 and "API conventions":
cursor feeds): the list newest first, one requirement's revisions only, paged by `?before=`,
with the author's name; one revision's snapshot by number; both under `requirement.view` (S2-plan,
"Actions per row": project viewers and up, inherited admins; content, so export control applies).
"""

from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import ProjectRole
from app.models.requirement import Requirement, RequirementRevision
from app.models.user import User
from tests.factories.project import ProjectMembershipFactory
from tests.factories.requirement import RequirementFactory, RequirementRevisionFactory
from tests.factories.user import UserFactory
from tests.support.authz import Tenancy, persona_user, sign_in_as, tenancy

pytestmark = [pytest.mark.anyio, pytest.mark.security, pytest.mark.usefixtures("session")]

REVISIONS = "/api/projects/PMT/requirements/7/revisions"
TITLE = "Refunds above the card limit"


@pytest.fixture
async def t() -> Tenancy:
    return await tenancy()


@pytest.fixture
async def requirement(t: Tenancy) -> Requirement:
    return await RequirementFactory.create_async(project=t.project, number=7, title=TITLE)


@pytest.fixture
async def viewer(client: AsyncClient, t: Tenancy) -> User:
    user = await UserFactory.create_async(name="Vera Viewer")
    await ProjectMembershipFactory.create_async(
        project=t.project, user=user, role=ProjectRole.VIEWER
    )
    await sign_in_as(client, user)
    return user


async def revision(requirement: Requirement, number: int, **values: object) -> RequirementRevision:
    return await RequirementRevisionFactory.create_async(
        requirement=requirement, revision_number=number, **values
    )


def numbers(response: Response) -> list[int]:
    return [item["revision_number"] for item in response.json()["items"]]


def items(response: Response) -> list[dict[str, Any]]:
    return response.json()["items"]


async def test_the_revisions_are_newest_first_and_page_by_cursor(
    client: AsyncClient, requirement: Requirement, viewer: User
) -> None:
    """Bug: oldest first, or a cursor that repeats or skips a revision."""
    for number in (1, 2, 3):
        await revision(requirement, number)

    first = await client.get(REVISIONS, params={"limit": 2})
    second = await client.get(REVISIONS, params={"limit": 2, "before": first.json()["next_cursor"]})

    assert numbers(first) == [3, 2]
    assert (numbers(second), second.json()["next_cursor"]) == ([1], None)


async def test_the_list_holds_only_this_requirements_revisions(
    client: AsyncClient, t: Tenancy, requirement: Requirement, viewer: User
) -> None:
    """Bug: the list isn't filtered by requirement."""
    other = await RequirementFactory.create_async(project=t.project, number=8)
    await revision(requirement, 1, title="Ours")
    await revision(other, 1, title="Theirs")

    response = await client.get(REVISIONS)

    assert [item["title"] for item in items(response)] == ["Ours"]


async def test_a_list_row_names_its_author_and_carries_its_note_but_no_description(
    client: AsyncClient, requirement: Requirement, viewer: User
) -> None:
    """Bug: the author unresolved or wrong, a deactivated author shown as active (no
    "Deactivated" badge, ui-design-guide), the note dropped, or every description sent."""
    author = await UserFactory.create_async(name="Ana Author", is_active=False)
    await revision(
        requirement,
        2,
        title="Refunds up to the limit",
        change_note="Cap at the limit",
        creator=author,
    )

    (row,) = items(await client.get(REVISIONS))

    assert {k: v for k, v in row.items() if k not in ("id", "created_at")} == {
        "revision_number": 2,
        "title": "Refunds up to the limit",
        "change_note": "Cap at the limit",
        "created_by_id": str(author.id),
        "created_by_name": "Ana Author",
        "created_by_is_active": False,
    }


async def test_one_revision_is_its_own_snapshot_not_the_current_content(
    client: AsyncClient, requirement: Requirement, viewer: User
) -> None:
    """Bug: the read returns the requirement's current title or description, or the wrong
    revision."""
    author = await UserFactory.create_async(name="Ana Author")
    await revision(requirement, 1, title="First title", description_md="First body", creator=author)
    await revision(requirement, 2, title="Second title", description_md="Second body")

    response = await client.get(f"{REVISIONS}/1")

    assert response.status_code == 200
    body = response.json()
    assert (body["revision_number"], body["title"], body["description_md"]) == (
        1,
        "First title",
        "First body",
    )
    assert (body["created_by_name"], body["change_note"]) == ("Ana Author", None)


async def test_a_revision_number_the_requirement_does_not_have_is_404(
    client: AsyncClient, t: Tenancy, requirement: Requirement, viewer: User
) -> None:
    """Bug: the read looks the number up across requirements (RQ-8 has a revision 2, RQ-7
    doesn't)."""
    await revision(requirement, 1)
    other = await RequirementFactory.create_async(project=t.project, number=8)
    await revision(other, 2, title="Not ours")

    found = await client.get(f"{REVISIONS}/1")
    missing = await client.get(f"{REVISIONS}/2")

    assert found.status_code == 200
    assert (missing.status_code, missing.json()["code"]) == (404, "not_found")
    assert "Not ours" not in missing.text


async def test_a_deleted_requirements_revisions_are_404(
    client: AsyncClient, session: AsyncSession, requirement: Requirement, viewer: User
) -> None:
    """Bug: the revisions load the requirement with the trash included."""
    await revision(requirement, 1)
    requirement.deleted_at = requirement.created_at
    await session.flush()

    for_list = await client.get(REVISIONS)
    for_one = await client.get(f"{REVISIONS}/1")

    assert [(r.status_code, r.json()["code"]) for r in (for_list, for_one)] == [
        (404, "not_found"),
        (404, "not_found"),
    ]


async def test_an_unknown_query_parameter_is_a_422(
    client: AsyncClient, requirement: Requirement, viewer: User
) -> None:
    response = await client.get(REVISIONS, params={"befor": "x"})

    assert (response.status_code, response.json()["code"]) == (422, "validation_error")


# --- Who may read (requirement.view) ------------------------------------------------------------


@pytest.mark.parametrize("who", ["project_viewer", "org_admin", "system_admin"])
@pytest.mark.parametrize("path", ["", "/1"])
async def test_viewers_and_inherited_admins_read_the_revisions(
    client: AsyncClient, t: Tenancy, requirement: Requirement, who: str, path: str
) -> None:
    await revision(requirement, 1, title="Snapshot")
    await sign_in_as(client, await persona_user(t, who))

    response = await client.get(REVISIONS + path)

    assert response.status_code == 200
    assert "Snapshot" in response.text


@pytest.mark.parametrize("who", ["org_member", "other_project_admin", "workspace_member", "nobody"])
@pytest.mark.parametrize("path", ["", "/1"])
async def test_the_revisions_are_404_to_who_cannot_see_the_project(
    client: AsyncClient, t: Tenancy, requirement: Requirement, who: str, path: str
) -> None:
    """Bug: the routes load the requirement without `requirement.view`."""
    await revision(requirement, 1, title="Snapshot")
    await sign_in_as(client, await persona_user(t, who))

    response = await client.get(REVISIONS + path)

    assert (response.status_code, response.json()["code"]) == (404, "not_found")
    for name in ("Payments", "PMT", TITLE, "Snapshot"):
        assert name not in response.text


@pytest.mark.parametrize(
    ("who", "status"), [("org_admin", 404), ("system_admin", 404), ("project_viewer", 200)]
)
@pytest.mark.parametrize("path", ["", "/1"])
async def test_on_an_export_controlled_project_only_explicit_members_read_the_revisions(
    client: AsyncClient,
    session: AsyncSession,
    t: Tenancy,
    requirement: Requirement,
    who: str,
    status: int,
    path: str,
) -> None:
    """Design-doc §3.1: content is for explicit members only; bug: the gate isn't reached."""
    await revision(requirement, 1, title="Snapshot")
    t.project.restriction_categories = ["export_controlled"]
    await session.flush()
    await sign_in_as(client, await persona_user(t, who))

    response = await client.get(REVISIONS + path)

    assert response.status_code == status
    assert ("Snapshot" in response.text) is (status == 200)
