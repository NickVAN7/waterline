"""Authorization wiring of S2-C8's endpoints (build plan, Slice 2 row 8; design-doc §5 "Other
targeted rules" → Deletion; §3.1 export-controlled projects; §9 "Deleting a requirement",
"Permissions in the delete dialog", "Restore", "Trash", "Restoring a tree", "A link to a deleted
item", "A deleted requirement's history"; DL-146, DL-200, DL-206):

- `DELETE /api/projects/{key}/requirements/{number}?children=promote|delete`
  (`requirement.delete`): 204 to the reporter of a never-approved requirement and to project
  admins (inherited included); 403 to who sees the project but may not; 404, naming nothing, to
  who can't see it, and to an inherited admin on an export-controlled project. `children=delete`
  is 403, with nothing deleted, when a descendant isn't the caller's to delete ("never ... delete
  indirectly what they couldn't delete directly"), while `promote` (the default) is allowed;
- `POST .../requirements/{number}/restore` (`requirement.restore`, "whoever may delete an item
  may also restore it"): the same people; 403, nothing restored, when a descendant restored with
  it (the same `deleted_at`) isn't the caller's to restore; a child deleted separately doesn't
  count; 404 for a requirement not in the trash;
- `GET /api/projects/{key}/trash`: "each user what they can restore; project admins see
  everything in the project": a member only their own never-approved items, a viewer nothing,
  404 to who can't see the project and behind the export-control gate;
- a requirement deleted through the endpoint is a 404 on its read and its history (DL-200,
  DL-206), and on a second delete;
- a requirement read's `allowed_actions` carry `requirement.delete` exactly when it's allowed,
  and its `can_delete_children` is whether the whole subtree may go (DL-222);
- the reporter acts as a project member: a reporter who is now a viewer gets 403, and sees
  nothing in the trash (DL-219); `children=delete` takes grandchildren too, and a delete or
  restore reaching one the caller couldn't act on directly is a 403 (DL-221);
- a trash row is listed by its own rule, carrying Restore only when the whole restore would
  pass; an archived project's trash lists the same rows, with no Restore (DL-220, DL-222).

Persisted state is asserted only as far as authorization needs (in or out of the tree, or
`deleted_at` re-read); ranks, promote placement, restriction lifts, and approval cancelling are
the main session's. Personas are relative to workspace "Acme Consulting", org "Bolt Foods"
(bolt-foods), and project "Payments" (PMT) (tests/support/authz.py, `persona_user`).
"""

from datetime import UTC, datetime
from typing import Any, cast

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import ProjectRole, RequirementStatus
from app.models.requirement import Requirement
from app.models.user import User
from tests.factories import BaseFactory
from tests.factories.org import OrganizationFactory
from tests.factories.project import ProjectFactory, ProjectMembershipFactory
from tests.factories.requirement import RequirementFactory, RequirementRevisionFactory
from tests.factories.user import UserFactory
from tests.factories.workspace import WorkspaceFactory
from tests.support.authz import Tenancy, persona_user, sign_in_as

pytestmark = [pytest.mark.anyio, pytest.mark.security, pytest.mark.usefixtures("session")]

INHERITED_ADMINS = ["system_admin", "workspace_owner", "workspace_admin", "org_owner", "org_admin"]
PROJECT_ADMINS = [*INHERITED_ADMINS, "project_admin"]
PROJECT_UNSEEN = [
    "org_member",
    "other_project_admin",
    "workspace_member",
    "other_org_owner",
    "other_workspace_owner",
    "nobody",
]

DELETED_AT = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
EARLIER = datetime(2026, 9, 1, 9, 0, tzinfo=UTC)
ARCHIVED_AT = datetime(2026, 10, 2, 9, 0, tzinfo=UTC)
TITLE = "Refunds above the card limit"
CHILD_TITLE = "Partial refunds"
GRANDCHILD_TITLE = "Refund reason codes"

TREE = "/api/projects/PMT/requirements"
URL = "/api/projects/PMT/requirements/7"
MISSING_URL = "/api/projects/NOPE/requirements/7"
RESTORE = "/api/projects/PMT/requirements/7/restore"
MISSING_RESTORE = "/api/projects/NOPE/requirements/7/restore"
TRASH = "/api/projects/PMT/trash"
MISSING_TRASH = "/api/projects/NOPE/trash"


async def signed_in(
    client: AsyncClient, who: str, *, export_controlled: bool = False
) -> tuple[Tenancy, User]:
    """`who` signed in, relative to "Payments" (PMT)."""
    workspace = await WorkspaceFactory.create_async(name="Acme Consulting", slug="acme")
    org = await OrganizationFactory.create_async(
        workspace=workspace, name="Bolt Foods", slug="bolt-foods"
    )
    project = await ProjectFactory.create_async(
        organization=org,
        key="PMT",
        name="Payments",
        restriction_level=None,
        restriction_categories=["export_controlled"] if export_controlled else [],
    )
    t = Tenancy(workspace, org, project)
    user = await persona_user(t, who)
    await sign_in_as(client, user)
    return t, user


async def someone_else(t: Tenancy) -> User:
    """Ivy Moss, another explicit member (role member) of PMT."""
    ivy = await UserFactory.create_async(
        email="ivy@bolt.example", name="Ivy Moss", is_system_admin=False
    )
    await ProjectMembershipFactory.create_async(
        project=t.project, user=ivy, role=ProjectRole.MEMBER
    )
    return ivy


async def requirement(
    t: Tenancy,
    number: int,
    *,
    reporter: User,
    approved: bool = False,
    parent: Requirement | None = None,
    deleted_at: datetime | None = None,
    title: str = TITLE,
) -> Requirement:
    """RQ-`number` in PMT at revision 1, reported by `reporter`; once approved, its
    `approved_revision_id` is revision 1."""
    item = await RequirementFactory.create_async(
        project=t.project,
        number=number,
        title=title,
        reporter=reporter,
        parent_requirement_id=None if parent is None else parent.id,
        rank=f"a{number}",
        status=RequirementStatus.APPROVED if approved else RequirementStatus.DRAFT,
        deleted_at=deleted_at,
    )
    revision = await RequirementRevisionFactory.create_async(
        requirement=item, revision_number=1, title=title
    )
    item.current_revision_id = revision.id
    if approved:
        item.approved_revision_id = revision.id
        item.approved_at = DELETED_AT
    # The app reads through its own session: flush what was set after the factory's flush.
    await cast(AsyncSession, BaseFactory.__async_session__).flush()
    return item


async def archive(session: AsyncSession, t: Tenancy) -> None:
    t.project.archived_at = ARCHIVED_AT
    await session.flush()


async def is_deleted(session: AsyncSession, item: Requirement) -> bool:
    """Whether the requirement is in the trash, re-read from the database."""
    statement = (
        select(Requirement.deleted_at)
        .where(Requirement.id == item.id)
        .execution_options(include_deleted=True)
    )
    return (await session.execute(statement)).scalar_one() is not None


async def tree_numbers(client: AsyncClient) -> set[int]:
    """The numbers in the project's tree, as the signed-in user reads it."""
    response = await client.get(TREE)
    assert response.status_code == 200
    return {item["number"] for item in response.json()["items"]}


def trash_numbers(body: dict[str, Any]) -> set[int]:
    return {item["number"] for item in body["items"]}


def assert_hidden(response: Response, missing: Response, *titles: str) -> None:
    """404 `not_found`, the same body as for a project that doesn't exist, naming nothing."""
    assert (response.status_code, response.json()["code"]) == (404, "not_found")
    assert response.json() == missing.json()
    for name in ("Bolt Foods", "bolt-foods", "Payments", "PMT", *titles):
        assert name not in response.text


def assert_forbidden(response: Response) -> None:
    assert (response.status_code, response.json()["code"]) == (403, "forbidden")


# --- DELETE …/requirements/{number}: who may -----------------------------------------------------


@pytest.mark.parametrize("who", PROJECT_UNSEEN)
async def test_deleting_is_404_to_who_cannot_see_the_project_even_as_its_reporter(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    """§5: failures on entities the user can't see return 404, not 403."""
    t, user = await signed_in(client, who)
    item = await requirement(t, 7, reporter=user)

    response = await client.delete(URL)

    assert_hidden(response, await client.delete(MISSING_URL), TITLE)
    assert await is_deleted(session, item) is False


@pytest.mark.parametrize("approved", [False, True], ids=["never-approved", "approved"])
async def test_a_project_viewer_may_not_delete_a_requirement(
    client: AsyncClient, session: AsyncSession, approved: bool
) -> None:
    """§5 "Role capabilities": a viewer views; they see the project, so a 403."""
    t, _ = await signed_in(client, "project_viewer")
    item = await requirement(t, 7, reporter=await someone_else(t), approved=approved)

    assert_forbidden(await client.delete(URL))
    assert await is_deleted(session, item) is False


async def test_a_reporter_who_is_now_a_viewer_may_not_delete_it(
    client: AsyncClient, session: AsyncSession
) -> None:
    """DL-219: the reporter deletes as a project member (member role or above)."""
    t, user = await signed_in(client, "project_viewer")
    item = await requirement(t, 7, reporter=user)

    assert_forbidden(await client.delete(URL))
    assert await is_deleted(session, item) is False


async def test_a_member_may_not_delete_someone_elses_requirement(
    client: AsyncClient, session: AsyncSession
) -> None:
    """§5 Deletion: the reporter, or a project admin."""
    t, _ = await signed_in(client, "project_member")
    item = await requirement(t, 7, reporter=await someone_else(t))

    assert_forbidden(await client.delete(URL))
    assert await is_deleted(session, item) is False


async def test_the_reporter_deletes_their_never_approved_requirement(
    client: AsyncClient, session: AsyncSession
) -> None:
    """§5 Deletion: "reporter while it has never been approved"."""
    t, user = await signed_in(client, "project_member")
    item = await requirement(t, 7, reporter=user)

    response = await client.delete(URL)

    assert response.status_code == 204
    assert await is_deleted(session, item) is True
    assert 7 not in await tree_numbers(client)


async def test_the_reporter_may_not_delete_their_approved_requirement(
    client: AsyncClient, session: AsyncSession
) -> None:
    """§5 Deletion: "once approved, project admin only"."""
    t, user = await signed_in(client, "project_member")
    item = await requirement(t, 7, reporter=user, approved=True)

    assert_forbidden(await client.delete(URL))
    assert await is_deleted(session, item) is False


@pytest.mark.parametrize("who", PROJECT_ADMINS)
async def test_a_project_admin_deletes_someone_elses_approved_requirement(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    """§5 Deletion: once approved, project admin ("Project admin" includes inherited)."""
    t, _ = await signed_in(client, who)
    item = await requirement(t, 7, reporter=await someone_else(t), approved=True)

    response = await client.delete(URL)

    assert response.status_code == 204
    assert await is_deleted(session, item) is True
    assert 7 not in await tree_numbers(client)


@pytest.mark.parametrize("who", ["project_admin", "project_member"])
async def test_deleting_in_an_archived_project_is_403(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    """§5 step 1: every mutation inside an archived project is denied; §9: archived is
    read-only. The member is the reporter of a never-approved requirement."""
    t, user = await signed_in(client, who)
    item = await requirement(t, 7, reporter=user)
    await archive(session, t)

    assert_forbidden(await client.delete(URL))
    assert await is_deleted(session, item) is False


@pytest.mark.parametrize("who", INHERITED_ADMINS)
async def test_deleting_on_an_ec_project_is_404_to_an_inherited_admin_even_as_reporter(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    """§3.1: "Every content action denied to them, read or mutation, is a 404"."""
    t, user = await signed_in(client, who, export_controlled=True)
    item = await requirement(t, 7, reporter=user)

    response = await client.delete(URL)

    assert_hidden(response, await client.delete(MISSING_URL), TITLE)
    assert await is_deleted(session, item) is False


@pytest.mark.parametrize(("who", "approved"), [("project_member", False), ("project_admin", True)])
async def test_an_explicit_member_deletes_on_an_ec_project(
    client: AsyncClient, session: AsyncSession, who: str, approved: bool
) -> None:
    """§3.1: content needs an explicit membership, which they hold."""
    t, user = await signed_in(client, who, export_controlled=True)
    item = await requirement(t, 7, reporter=user, approved=approved)

    assert (await client.delete(URL)).status_code == 204
    assert await is_deleted(session, item) is True


# --- DELETE: children deleted with it, or promoted ------------------------------------------------


@pytest.mark.parametrize("approved_child", [False, True], ids=["others-child", "own-approved"])
async def test_deleting_children_the_member_may_not_delete_is_403_and_deletes_nothing(
    client: AsyncClient, session: AsyncSession, approved_child: bool
) -> None:
    """§9 "Permissions in the delete dialog": "soft-delete them too" applies only to items the
    user could delete directly; never delete indirectly what they couldn't delete directly. The
    child is Ivy's, or the member's own but approved."""
    t, user = await signed_in(client, "project_member")
    parent = await requirement(t, 7, reporter=user)
    child_reporter = user if approved_child else await someone_else(t)
    child = await requirement(
        t, 8, reporter=child_reporter, approved=approved_child, parent=parent, title=CHILD_TITLE
    )

    assert_forbidden(await client.delete(URL, params={"children": "delete"}))
    assert (await is_deleted(session, parent), await is_deleted(session, child)) == (False, False)


async def test_deleting_a_grandchild_the_member_may_not_delete_is_403_and_deletes_nothing(
    client: AsyncClient, session: AsyncSession
) -> None:
    """§9: a delete's descendants go with it ("restores the descendants deleted in the same
    action"), so each must be the caller's to delete; here the grandchild is Ivy's."""
    t, user = await signed_in(client, "project_member")
    parent = await requirement(t, 7, reporter=user)
    child = await requirement(t, 8, reporter=user, parent=parent, title=CHILD_TITLE)
    grandchild = await requirement(
        t, 9, reporter=await someone_else(t), parent=child, title=GRANDCHILD_TITLE
    )

    assert_forbidden(await client.delete(URL, params={"children": "delete"}))
    assert [await is_deleted(session, r) for r in (parent, child, grandchild)] == [
        False,
        False,
        False,
    ]


@pytest.mark.parametrize("params", [{"children": "promote"}, {}], ids=["promote", "default"])
async def test_promoting_children_the_member_may_not_delete_is_allowed(
    client: AsyncClient, session: AsyncSession, params: dict[str, str]
) -> None:
    """§9: for children they can't delete, *promote* is offered; it's the default."""
    t, user = await signed_in(client, "project_member")
    parent = await requirement(t, 7, reporter=user)
    child = await requirement(t, 8, reporter=await someone_else(t), parent=parent)

    response = await client.delete(URL, params=params)

    assert response.status_code == 204
    assert (await is_deleted(session, parent), await is_deleted(session, child)) == (True, False)
    assert await tree_numbers(client) == {8}


async def test_the_member_deletes_their_own_never_approved_subtree_with_it(
    client: AsyncClient, session: AsyncSession
) -> None:
    """DL-221: deleting with its children deletes the whole subtree, grandchildren included."""
    t, user = await signed_in(client, "project_member")
    parent = await requirement(t, 7, reporter=user)
    child = await requirement(t, 8, reporter=user, parent=parent, title=CHILD_TITLE)
    grandchild = await requirement(t, 9, reporter=user, parent=child, title=GRANDCHILD_TITLE)

    response = await client.delete(URL, params={"children": "delete"})

    assert response.status_code == 204
    assert [await is_deleted(session, r) for r in (parent, child, grandchild)] == [
        True,
        True,
        True,
    ]
    assert await tree_numbers(client) == set()


@pytest.mark.parametrize("who", ["project_admin", "org_admin"])
async def test_a_project_admin_deletes_others_approved_children_with_it(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t, _ = await signed_in(client, who)
    ivy = await someone_else(t)
    parent = await requirement(t, 7, reporter=ivy, approved=True)
    child = await requirement(t, 8, reporter=ivy, approved=True, parent=parent, title=CHILD_TITLE)

    response = await client.delete(URL, params={"children": "delete"})

    assert response.status_code == 204
    assert (await is_deleted(session, parent), await is_deleted(session, child)) == (True, True)
    assert await tree_numbers(client) == set()


# --- A deleted requirement is a 404 (DL-200, DL-206) -------------------------------------------


async def test_a_deleted_requirements_read_and_history_are_404(client: AsyncClient) -> None:
    """DL-200: a link to a deleted item is the standard 404 for everyone; DL-206: so is its
    history. The same body as a number that doesn't exist."""
    t, _ = await signed_in(client, "project_admin")
    await requirement(t, 7, reporter=await someone_else(t))
    assert (await client.get(URL)).status_code == 200

    assert (await client.delete(URL)).status_code == 204

    missing = "/api/projects/PMT/requirements/99"
    assert_hidden(await client.get(URL), await client.get(missing), TITLE)
    assert_hidden(
        await client.get(f"{URL}/activity"), await client.get(f"{missing}/activity"), TITLE
    )


async def test_deleting_a_deleted_requirement_again_is_404(client: AsyncClient) -> None:
    """DL-200: a deleted item is a 404; restore, not delete, is the way back."""
    t, _ = await signed_in(client, "project_admin")
    await requirement(t, 7, reporter=await someone_else(t))
    assert (await client.delete(URL)).status_code == 204

    response = await client.delete(URL)

    assert (response.status_code, response.json()["code"]) == (404, "not_found")


# --- allowed_actions on the read ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("who", "own", "approved", "offered"),
    [
        ("project_member", True, False, True),
        ("project_member", False, False, False),
        ("project_member", True, True, False),
        ("project_viewer", False, False, False),
        ("project_admin", False, True, True),
        ("org_admin", False, True, True),
    ],
)
async def test_allowed_actions_offer_delete_exactly_when_it_is_allowed(
    client: AsyncClient, who: str, own: bool, approved: bool, offered: bool
) -> None:
    """Build plan, "API conventions": `allowed_actions` evaluated through `authorize()`, so the
    UI hides what the user can't do (§5)."""
    t, user = await signed_in(client, who)
    await requirement(t, 7, reporter=user if own else await someone_else(t), approved=approved)

    response = await client.get(URL)

    assert response.status_code == 200
    assert ("requirement.delete" in response.json()["allowed_actions"]) is offered


async def subtree(
    t: Tenancy, user: User, child: str, grandchild: str, *, child_approved: bool = False
) -> None:
    """RQ-7, never approved, reported by `user`, its child RQ-8, and RQ-8's child RQ-9; each
    descendant reported by `user` ("own") or by Ivy ("ivy")."""
    ivy = await someone_else(t)
    reporters = {"own": user, "ivy": ivy}
    parent = await requirement(t, 7, reporter=user)
    middle = await requirement(
        t, 8, reporter=reporters[child], approved=child_approved, parent=parent, title=CHILD_TITLE
    )
    await requirement(t, 9, reporter=reporters[grandchild], parent=middle, title=GRANDCHILD_TITLE)


@pytest.mark.parametrize(
    ("who", "child", "grandchild", "child_approved", "expected"),
    [
        ("project_member", "own", "own", False, True),
        ("project_member", "own", "ivy", False, False),
        ("project_member", "ivy", "own", False, False),
        ("project_member", "own", "own", True, False),
        ("project_admin", "ivy", "ivy", True, True),
        ("org_admin", "ivy", "ivy", True, True),
    ],
    ids=[
        "member-own-subtree",
        "member-ivys-grandchild",
        "member-ivys-child",
        "member-own-approved-child",
        "project-admin",
        "org-admin",
    ],
)
async def test_can_delete_children_says_whether_the_whole_subtree_may_go(
    client: AsyncClient,
    who: str,
    child: str,
    grandchild: str,
    child_approved: bool,
    expected: bool,
) -> None:
    """DL-222: the read's `can_delete_children` is whether the caller may delete the
    requirement's whole subtree (DL-221), so the dialog offers "delete them too" only then."""
    t, user = await signed_in(client, who)
    await subtree(t, user, child, grandchild, child_approved=child_approved)

    response = await client.get(URL)

    assert response.status_code == 200
    assert response.json()["can_delete_children"] is expected


@pytest.mark.parametrize(
    ("who", "own", "expected"),
    [
        ("project_member", True, True),
        ("project_member", False, False),
        ("project_viewer", True, False),
        ("project_viewer", False, False),
    ],
)
async def test_can_delete_children_without_children_is_whether_it_may_be_deleted(
    client: AsyncClient, who: str, own: bool, expected: bool
) -> None:
    """DL-222: true exactly when the caller may delete the requirement and every descendant
    (none here); a reporter who is now a viewer may not (DL-219)."""
    t, user = await signed_in(client, who)
    await requirement(t, 7, reporter=user if own else await someone_else(t))

    response = await client.get(URL)

    assert response.status_code == 200
    assert response.json()["can_delete_children"] is expected


# --- POST …/restore: who may ---------------------------------------------------------------------


@pytest.mark.parametrize("who", PROJECT_UNSEEN)
async def test_restoring_is_404_to_who_cannot_see_the_project_even_as_its_reporter(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t, user = await signed_in(client, who)
    item = await requirement(t, 7, reporter=user, deleted_at=DELETED_AT)

    response = await client.post(RESTORE)

    assert_hidden(response, await client.post(MISSING_RESTORE), TITLE)
    assert await is_deleted(session, item) is True


async def test_a_project_viewer_may_not_restore(client: AsyncClient, session: AsyncSession) -> None:
    t, _ = await signed_in(client, "project_viewer")
    item = await requirement(t, 7, reporter=await someone_else(t), deleted_at=DELETED_AT)

    assert_forbidden(await client.post(RESTORE))
    assert await is_deleted(session, item) is True


@pytest.mark.parametrize(("own", "approved"), [(False, False), (True, True)])
async def test_a_member_may_not_restore_what_they_may_not_delete(
    client: AsyncClient, session: AsyncSession, own: bool, approved: bool
) -> None:
    """§5 Deletion: "whoever may delete an item may also restore it": not someone else's, and
    not an approved one."""
    t, user = await signed_in(client, "project_member")
    reporter = user if own else await someone_else(t)
    item = await requirement(t, 7, reporter=reporter, approved=approved, deleted_at=DELETED_AT)

    assert_forbidden(await client.post(RESTORE))
    assert await is_deleted(session, item) is True


async def test_a_reporter_who_is_now_a_viewer_may_not_restore_it(
    client: AsyncClient, session: AsyncSession
) -> None:
    """DL-219: the reporter restores as a project member (member role or above)."""
    t, user = await signed_in(client, "project_viewer")
    item = await requirement(t, 7, reporter=user, deleted_at=DELETED_AT)

    assert_forbidden(await client.post(RESTORE))
    assert await is_deleted(session, item) is True


async def test_the_reporter_restores_their_never_approved_requirement(
    client: AsyncClient, session: AsyncSession
) -> None:
    t, user = await signed_in(client, "project_member")
    item = await requirement(t, 7, reporter=user, deleted_at=DELETED_AT)

    response = await client.post(RESTORE)

    assert (response.status_code, response.json()["number"]) == (200, 7)
    assert await is_deleted(session, item) is False
    assert await tree_numbers(client) == {7}


@pytest.mark.parametrize("who", PROJECT_ADMINS)
async def test_a_project_admin_restores_someone_elses_approved_requirement(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t, _ = await signed_in(client, who)
    item = await requirement(
        t, 7, reporter=await someone_else(t), approved=True, deleted_at=DELETED_AT
    )

    response = await client.post(RESTORE)

    assert (response.status_code, response.json()["number"]) == (200, 7)
    assert await is_deleted(session, item) is False
    assert await tree_numbers(client) == {7}


async def test_restoring_in_an_archived_project_is_403(
    client: AsyncClient, session: AsyncSession
) -> None:
    t, _ = await signed_in(client, "project_admin")
    item = await requirement(t, 7, reporter=await someone_else(t), deleted_at=DELETED_AT)
    await archive(session, t)

    assert_forbidden(await client.post(RESTORE))
    assert await is_deleted(session, item) is True


@pytest.mark.parametrize("who", INHERITED_ADMINS)
async def test_restoring_on_an_ec_project_is_404_to_an_inherited_admin(
    client: AsyncClient, session: AsyncSession, who: str
) -> None:
    t, user = await signed_in(client, who, export_controlled=True)
    item = await requirement(t, 7, reporter=user, deleted_at=DELETED_AT)

    response = await client.post(RESTORE)

    assert_hidden(response, await client.post(MISSING_RESTORE), TITLE)
    assert await is_deleted(session, item) is True


async def test_an_explicit_member_restores_on_an_ec_project(
    client: AsyncClient, session: AsyncSession
) -> None:
    t, user = await signed_in(client, "project_member", export_controlled=True)
    item = await requirement(t, 7, reporter=user, deleted_at=DELETED_AT)

    assert (await client.post(RESTORE)).status_code == 200
    assert await is_deleted(session, item) is False


async def test_restoring_a_requirement_not_in_the_trash_is_404(
    client: AsyncClient, session: AsyncSession
) -> None:
    """The restore endpoint's contract: 404 for one not in the trash."""
    t, _ = await signed_in(client, "project_admin")
    item = await requirement(t, 7, reporter=await someone_else(t))

    response = await client.post(RESTORE)

    assert (response.status_code, response.json()["code"]) == (404, "not_found")
    assert await is_deleted(session, item) is False


# --- Restore: the descendants deleted with it ----------------------------------------------------


@pytest.mark.parametrize("approved_child", [False, True], ids=["others-child", "own-approved"])
async def test_restoring_with_a_descendant_the_member_may_not_restore_is_403(
    client: AsyncClient, session: AsyncSession, approved_child: bool
) -> None:
    """§9 "Restoring a tree": restoring also restores the descendants deleted in the same action
    (the same `deleted_at`); restore follows delete, so each must be the caller's to restore."""
    t, user = await signed_in(client, "project_member")
    parent = await requirement(t, 7, reporter=user, deleted_at=DELETED_AT)
    child_reporter = user if approved_child else await someone_else(t)
    child = await requirement(
        t,
        8,
        reporter=child_reporter,
        approved=approved_child,
        parent=parent,
        deleted_at=DELETED_AT,
        title=CHILD_TITLE,
    )

    assert_forbidden(await client.post(RESTORE))
    assert (await is_deleted(session, parent), await is_deleted(session, child)) == (True, True)


async def test_restoring_with_a_grandchild_the_member_may_not_restore_is_403(
    client: AsyncClient, session: AsyncSession
) -> None:
    """DL-221: a restore that would reach a descendant the user couldn't restore directly is a
    403, and nothing changes; here the grandchild deleted with it is Ivy's."""
    t, user = await signed_in(client, "project_member")
    parent = await requirement(t, 7, reporter=user, deleted_at=DELETED_AT)
    child = await requirement(
        t, 8, reporter=user, parent=parent, deleted_at=DELETED_AT, title=CHILD_TITLE
    )
    grandchild = await requirement(
        t,
        9,
        reporter=await someone_else(t),
        parent=child,
        deleted_at=DELETED_AT,
        title=GRANDCHILD_TITLE,
    )

    assert_forbidden(await client.post(RESTORE))
    assert [await is_deleted(session, r) for r in (parent, child, grandchild)] == [
        True,
        True,
        True,
    ]


async def test_the_member_restores_their_own_descendants_with_it(
    client: AsyncClient, session: AsyncSession
) -> None:
    t, user = await signed_in(client, "project_member")
    parent = await requirement(t, 7, reporter=user, deleted_at=DELETED_AT)
    child = await requirement(
        t, 8, reporter=user, parent=parent, deleted_at=DELETED_AT, title=CHILD_TITLE
    )

    assert (await client.post(RESTORE)).status_code == 200
    assert (await is_deleted(session, parent), await is_deleted(session, child)) == (False, False)
    assert await tree_numbers(client) == {7, 8}


async def test_a_child_deleted_separately_does_not_stop_the_restore(
    client: AsyncClient, session: AsyncSession
) -> None:
    """§9: "children deleted separately stay in the trash", so they aren't restored with it, and
    their reporter doesn't matter."""
    t, user = await signed_in(client, "project_member")
    parent = await requirement(t, 7, reporter=user, deleted_at=DELETED_AT)
    child = await requirement(
        t, 8, reporter=await someone_else(t), parent=parent, deleted_at=EARLIER, title=CHILD_TITLE
    )

    assert (await client.post(RESTORE)).status_code == 200
    assert (await is_deleted(session, parent), await is_deleted(session, child)) == (False, True)
    assert await tree_numbers(client) == {7}


# --- GET …/trash ---------------------------------------------------------------------------------


async def trash_of(t: Tenancy, user: User) -> None:
    """In PMT's trash: RQ-1, never approved, and RQ-2, approved, both reported by `user`; RQ-3,
    never approved, reported by Ivy. RQ-4 (the user's) is live."""
    ivy = await someone_else(t)
    await requirement(t, 1, reporter=user, deleted_at=DELETED_AT, title="Card refunds")
    await requirement(
        t, 2, reporter=user, approved=True, deleted_at=DELETED_AT, title="Bank refunds"
    )
    await requirement(t, 3, reporter=ivy, deleted_at=DELETED_AT, title="Voucher refunds")
    await requirement(t, 4, reporter=user, title="Refund reports")


async def test_the_trash_shows_a_member_only_what_they_may_restore(client: AsyncClient) -> None:
    """§9: "The trash view shows each user what they can restore": the member's own
    never-approved item, with Restore in its `allowed_actions`."""
    t, user = await signed_in(client, "project_member")
    await trash_of(t, user)

    response = await client.get(TRASH)

    assert response.status_code == 200
    body = response.json()
    assert (trash_numbers(body), body["total"]) == ({1}, 1)
    assert "requirement.restore" in body["items"][0]["allowed_actions"]


@pytest.mark.parametrize("who", PROJECT_ADMINS)
async def test_the_trash_shows_a_project_admin_everything_in_the_project(
    client: AsyncClient, who: str
) -> None:
    """§9: "project admins see everything in the project"."""
    t, user = await signed_in(client, who)
    await trash_of(t, user)

    response = await client.get(TRASH)

    assert response.status_code == 200
    body = response.json()
    assert (trash_numbers(body), body["total"]) == ({1, 2, 3}, 3)
    assert [("requirement.restore" in item["allowed_actions"]) for item in body["items"]] == [
        True,
        True,
        True,
    ]


async def test_the_trash_shows_a_viewer_nothing(client: AsyncClient) -> None:
    """A viewer may delete nothing (§5), so may restore nothing."""
    t, _ = await signed_in(client, "project_viewer")
    await trash_of(t, await UserFactory.create_async())

    response = await client.get(TRASH)

    assert response.status_code == 200
    assert (response.json()["items"], response.json()["total"]) == ([], 0)


@pytest.mark.parametrize("who", PROJECT_UNSEEN)
async def test_the_trash_is_404_to_who_cannot_see_the_project(
    client: AsyncClient, who: str
) -> None:
    t, user = await signed_in(client, who)
    await trash_of(t, user)

    response = await client.get(TRASH)

    assert_hidden(response, await client.get(MISSING_TRASH), "Card refunds", "Voucher refunds")


@pytest.mark.parametrize("who", INHERITED_ADMINS)
async def test_the_trash_on_an_ec_project_is_404_to_an_inherited_admin(
    client: AsyncClient, who: str
) -> None:
    """Build plan, Slice 2 "Done when": an inherited admin without an explicit membership gets a
    404 for ... the trash."""
    t, user = await signed_in(client, who, export_controlled=True)
    await trash_of(t, user)

    response = await client.get(TRASH)

    assert_hidden(response, await client.get(MISSING_TRASH), "Card refunds", "Voucher refunds")


async def test_the_trash_on_an_ec_project_shows_an_explicit_admin_everything(
    client: AsyncClient,
) -> None:
    t, user = await signed_in(client, "project_admin", export_controlled=True)
    await trash_of(t, user)

    response = await client.get(TRASH)

    assert response.status_code == 200
    assert trash_numbers(response.json()) == {1, 2, 3}


def restorable(body: dict[str, Any]) -> dict[int, bool]:
    """Each listed number, and whether its `allowed_actions` carry `requirement.restore`."""
    return {
        item["number"]: "requirement.restore" in item["allowed_actions"] for item in body["items"]
    }


async def test_the_trash_shows_a_reporter_who_is_now_a_viewer_nothing(client: AsyncClient) -> None:
    """DL-219: the reporter restores as a project member, so a viewer's own item isn't theirs to
    restore."""
    t, user = await signed_in(client, "project_viewer")
    await requirement(t, 7, reporter=user, deleted_at=DELETED_AT)

    response = await client.get(TRASH)

    assert response.status_code == 200
    assert (response.json()["items"], response.json()["total"]) == ([], 0)


@pytest.mark.parametrize(
    ("child", "expected"),
    [("ivy", {7: False}), ("own", {7: True, 8: True})],
    ids=["ivys-child", "own-child"],
)
async def test_a_trash_row_carries_restore_only_when_the_whole_restore_would_pass(
    client: AsyncClient, child: str, expected: dict[int, bool]
) -> None:
    """DL-220: a row is listed when the user could restore that item alone, even if a
    descendant deleted with it would refuse the restore; DL-222: Restore is in its
    `allowed_actions` only when the whole restore would pass. Ivy's child isn't listed."""
    t, user = await signed_in(client, "project_member")
    parent = await requirement(t, 7, reporter=user, deleted_at=DELETED_AT)
    await requirement(
        t,
        8,
        reporter=user if child == "own" else await someone_else(t),
        parent=parent,
        deleted_at=DELETED_AT,
        title=CHILD_TITLE,
    )

    response = await client.get(TRASH)

    assert response.status_code == 200
    assert restorable(response.json()) == expected


@pytest.mark.parametrize(
    ("who", "expected"),
    [
        ("project_member", {1: False}),
        ("project_admin", {1: False, 2: False, 3: False}),
        ("org_admin", {1: False, 2: False, 3: False}),
    ],
)
async def test_an_archived_projects_trash_lists_the_same_rows_with_no_restore(
    client: AsyncClient, session: AsyncSession, who: str, expected: dict[int, bool]
) -> None:
    """DL-220: an archived project's trash lists the same items as a live one, with no Restore
    in `allowed_actions` (§5 step 1: no mutation in an archived project)."""
    t, user = await signed_in(client, who)
    await trash_of(t, user)
    await archive(session, t)

    response = await client.get(TRASH)

    assert response.status_code == 200
    assert restorable(response.json()) == expected
