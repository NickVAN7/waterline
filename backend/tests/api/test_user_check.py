"""The user check (build plan, "The user check"; DL-66): what each form answers, and the 422 for
none or several. Who may call it is in tests/api/authz/test_user_check.py (spec tests)."""

import pytest
from httpx import AsyncClient

from app.enums import WorkspaceRole
from app.models.workspace import Workspace
from tests.factories.user import UserFactory
from tests.factories.workspace import WorkspaceFactory, WorkspaceMembershipFactory
from tests.support.authz import sign_in_as

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("session")]


@pytest.fixture
async def workspace(client: AsyncClient) -> Workspace:
    """A workspace, with `client` signed in as its admin."""
    workspace = await WorkspaceFactory.create_async()
    admin = await UserFactory.create_async()
    await WorkspaceMembershipFactory.create_async(
        workspace=workspace, user=admin, role=WorkspaceRole.ADMIN
    )
    await sign_in_as(client, admin)
    return workspace


async def check(client: AsyncClient, workspace: Workspace, **params: str) -> tuple[int, object]:
    response = await client.get(f"/api/workspaces/{workspace.id}/user-check", params=params)
    return response.status_code, response.json()


@pytest.mark.parametrize(
    "params",
    [{}, {"email": "a@b.example", "name": "Jane Doe"}, {"username": "jane", "name": "Jane"}],
)
async def test_none_or_several_parameters_is_a_422(
    client: AsyncClient, workspace: Workspace, params: dict[str, str]
) -> None:
    status, body = await check(client, workspace, **params)

    assert status == 422
    assert isinstance(body, dict)
    assert [(f["loc"], f["type"]) for f in body["details"]["fields"]] == [  # pyright: ignore[reportUnknownVariableType]
        (["query"], "one_parameter")
    ]


@pytest.mark.security
async def test_someone_outside_the_audience_gets_a_404_before_the_parameters_are_checked(
    client: AsyncClient, workspace: Workspace
) -> None:
    """The check's existence isn't revealed to anyone outside its audience, even by a 422
    (DL-68)."""
    await sign_in_as(client, await UserFactory.create_async())

    status, body = await check(client, workspace)

    assert (status, body) == (
        404,
        {"code": "not_found", "message": "Not found.", "details": {}},
    )


async def test_the_email_form_says_whether_an_account_has_it_and_nothing_else(
    client: AsyncClient, workspace: Workspace
) -> None:
    """Never whose it is (DL-66): the answer is the same shape either way, with no name or
    username."""
    await UserFactory.create_async(email="ann@acme.example", name="Ann Lee", username="ann-lee")

    assert await check(client, workspace, email=" Ann@Acme.example ") == (
        200,
        {"email": "ann@acme.example", "exists": True},
    )
    assert await check(client, workspace, email="nobody@acme.example") == (
        200,
        {"email": "nobody@acme.example", "exists": False},
    )


@pytest.mark.parametrize(
    ("username", "expected"),
    [
        ("free-name", {"available": True, "problem": None}),
        ("ann-lee", {"available": False, "problem": "taken"}),
        ("9ann", {"available": False, "problem": "must_start_with_letter"}),
        # The format first: a taken value that's also invalid reads as the format's problem.
        ("Ann-Lee", {"available": False, "problem": "invalid_characters"}),
    ],
)
async def test_the_username_form_reports_the_rule_then_taken(
    client: AsyncClient, workspace: Workspace, username: str, expected: dict[str, object]
) -> None:
    await UserFactory.create_async(username="ann-lee")

    assert await check(client, workspace, username=username) == (200, expected)


@pytest.mark.parametrize(
    ("taken", "expected"),
    [
        ([], "jane-doe"),
        (["jane-doe"], "jane-doe-2"),
        # The service keeps counting while each candidate is taken.
        (["jane-doe", "jane-doe-2", "jane-doe-3"], "jane-doe-4"),
        # A gap is used: only the base is taken.
        (["jane-doe", "jane-doe-3"], "jane-doe-2"),
    ],
)
async def test_the_name_form_suggests_the_first_free_username(
    client: AsyncClient, workspace: Workspace, taken: list[str], expected: str
) -> None:
    for username in taken:
        await UserFactory.create_async(username=username)

    assert await check(client, workspace, name="Jane Doe") == (200, {"suggestion": expected})


async def test_a_name_with_no_valid_username_suggests_nothing(
    client: AsyncClient, workspace: Workspace
) -> None:
    assert await check(client, workspace, name="李 王") == (200, {"suggestion": None})
