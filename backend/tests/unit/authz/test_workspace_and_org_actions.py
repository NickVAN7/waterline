"""S1-C8's three actions (DL-56; build plan, "Authorization (§5)"): `workspace_staff.manage_admins`
(workspace owners, system admins), `org.view` (anyone who sees the org, design-doc §4
"Visibility"), and `org.update` (org owners, workspace owners/admins, system admins). Personas
are those of tests/support/authz.py, relative to workspace WS and org ORG."""

import pytest

from app.authz.authorize import allowed_actions, authorize, ensure
from app.authz.target import Target
from app.core.errors import ForbiddenError, NotFoundError
from tests.support.authz import ORG_TARGET, PERSONAS, WORKSPACE_TARGET, rows

pytestmark = pytest.mark.security

# Who sees ORG (design-doc §4, "Visibility"): the admins who inherit it, an org membership, or a
# project membership on one of its projects (PROJ or PROJ2).
SEES_THE_ORG = {
    "system_admin", "workspace_owner", "workspace_admin", "org_owner", "org_admin", "org_member",
    "project_admin", "project_member", "project_viewer", "other_project_admin",
}  # fmt: skip


@pytest.mark.parametrize(("persona", "allowed"), rows({"system_admin", "workspace_owner"}))
def test_managing_admin_roles_is_for_workspace_owners_and_system_admins(
    persona: str, allowed: bool
) -> None:
    """DL-56: a workspace admin manages staff but can't grant, change, or remove an owner or
    admin role."""
    assert (
        authorize(PERSONAS[persona], "workspace_staff.manage_admins", WORKSPACE_TARGET) is allowed
    )


@pytest.mark.parametrize(("persona", "allowed"), rows(SEES_THE_ORG))
def test_org_view_is_for_anyone_who_sees_the_org(persona: str, allowed: bool) -> None:
    """Denied to a workspace member with no assignment there, another org's owner, another
    workspace's owner, and a user with no memberships."""
    assert authorize(PERSONAS[persona], "org.view", ORG_TARGET) is allowed


@pytest.mark.parametrize(
    ("persona", "allowed"),
    rows({"system_admin", "workspace_owner", "workspace_admin", "org_owner"}),
)
def test_org_update_is_for_org_owners_and_the_admins_above(persona: str, allowed: bool) -> None:
    """design-doc §5: managing the org itself is an org owner's; an org admin is denied."""
    assert authorize(PERSONAS[persona], "org.update", ORG_TARGET) is allowed


# --- ensure(): 403 for what the user sees, 404 for what they don't -----------------------------


@pytest.mark.parametrize(
    ("persona", "action", "target"),
    [
        ("workspace_admin", "workspace_staff.manage_admins", WORKSPACE_TARGET),
        ("org_admin", "org.update", ORG_TARGET),
        ("org_member", "org.update", ORG_TARGET),
        ("project_viewer", "org.update", ORG_TARGET),
    ],
)
def test_ensure_is_403_for_a_new_action_on_what_the_user_sees(
    persona: str, action: str, target: Target
) -> None:
    with pytest.raises(ForbiddenError):
        ensure(PERSONAS[persona], action, target)


@pytest.mark.parametrize(
    ("persona", "action", "target"),
    [
        ("workspace_member", "workspace_staff.manage_admins", WORKSPACE_TARGET),
        ("org_owner", "workspace_staff.manage_admins", WORKSPACE_TARGET),
        ("workspace_member", "org.view", ORG_TARGET),
        ("other_org_owner", "org.view", ORG_TARGET),
        ("nobody", "org.view", ORG_TARGET),
        ("other_workspace_owner", "org.update", ORG_TARGET),
    ],
)
def test_ensure_is_404_for_a_new_action_on_what_the_user_cannot_see(
    persona: str, action: str, target: Target
) -> None:
    with pytest.raises(NotFoundError):
        ensure(PERSONAS[persona], action, target)


@pytest.mark.parametrize(
    "persona", ["org_member", "project_viewer", "other_project_admin", "workspace_owner"]
)
def test_ensure_lets_anyone_who_sees_the_org_view_it(persona: str) -> None:
    assert ensure(PERSONAS[persona], "org.view", ORG_TARGET) is None


# --- allowed_actions on an org (build plan, "API conventions"; DL-56) ---------------------------


@pytest.mark.parametrize(
    ("persona", "expected"),
    [
        ("system_admin", ["org.update", "org.view"]),
        ("workspace_owner", ["org.update", "org.view"]),
        ("workspace_admin", ["org.update", "org.view"]),
        ("org_owner", ["org.update", "org.view"]),
        ("org_admin", ["org.view"]),
        ("org_member", ["org.view"]),
        ("project_viewer", ["org.view"]),
        ("other_project_admin", ["org.view"]),
        ("workspace_member", []),
        ("other_org_owner", []),
        ("other_workspace_owner", []),
        ("nobody", []),
    ],
)
def test_allowed_actions_on_an_org(persona: str, expected: list[str]) -> None:
    assert allowed_actions(PERSONAS[persona], ORG_TARGET) == expected
