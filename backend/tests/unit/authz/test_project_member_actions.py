"""S1-C12's two actions (DL-79; build plan, "Projects (§1.1, §3)", "The project member actions"):

- `project_member.manage`: project admins, inherited included (system admins, workspace
  owners/admins, owners/admins of the project's org; design-doc §5, "Role capabilities": "Project
  admin" always includes inherited); a mutation, so an archived project denies it to everyone
  (design-doc §5, step 1; §9);
- `project.view_access`: the same people (design-doc §5, "Access review": the per-project view
  for project admins, including inherited); not a mutation, so still allowed on an archived
  project.

Both are project level, so a project's `allowed_actions` carry them where `authorize()` allows
them. Personas are those of tests/support/authz.py, relative to workspace WS, org ORG, and
project PROJ (in ORG).
"""

import uuid

import pytest

from app.authz.authorize import allowed_actions, authorize, ensure
from app.authz.context import AuthzContext
from app.authz.target import Target
from app.core.errors import ForbiddenError, NotFoundError
from app.enums import OrgRole
from tests.support.authz import (
    ARCHIVED_PROJECT_TARGET,
    ORG,
    ORG2,
    PERSONAS,
    PROJ2,
    PROJ3,
    PROJECT_TARGET,
    WS,
    rows,
)

pytestmark = pytest.mark.security

MANAGE = "project_member.manage"
VIEW_ACCESS = "project.view_access"
PROJECT_ADMINS = {
    "system_admin",
    "workspace_owner",
    "workspace_admin",
    "org_owner",
    "org_admin",
    "project_admin",
}
# See the project (design-doc §4, "Visibility") without being one of its admins.
SEE_ONLY = ["project_member", "project_viewer"]
UNSEEN = [
    "org_member",
    "other_project_admin",
    "workspace_member",
    "other_org_owner",
    "other_workspace_owner",
    "nobody",
]


# --- A live project -----------------------------------------------------------------------------


@pytest.mark.parametrize(("persona", "allowed"), rows(PROJECT_ADMINS))
def test_managing_members_is_for_project_admins_inherited_included(
    persona: str, allowed: bool
) -> None:
    """design-doc §5, "Project roles": admin manages the project's members; member and viewer
    don't, nor does anyone without project admin (an org member, another project's admin)."""
    assert authorize(PERSONAS[persona], MANAGE, PROJECT_TARGET) is allowed


@pytest.mark.parametrize(("persona", "allowed"), rows(PROJECT_ADMINS))
def test_the_access_review_is_for_project_admins_inherited_included(
    persona: str, allowed: bool
) -> None:
    """design-doc §5, "Access review": the per-project view, project admins (including
    inherited)."""
    assert authorize(PERSONAS[persona], VIEW_ACCESS, PROJECT_TARGET) is allowed


@pytest.mark.parametrize("action", [MANAGE, VIEW_ACCESS])
def test_an_org_admin_inherits_them_only_in_their_own_org(action: str) -> None:
    admin_of_org2 = AuthzContext(
        user_id=uuid.uuid4(), org_roles={ORG2: OrgRole.ADMIN}, org_workspaces={ORG2: WS}
    )

    # Owner-approved change (S1-C12): allowed on a project of their own org, not on PROJ's.
    assert authorize(admin_of_org2, action, Target(WS, ORG2, PROJ3)) is True
    assert authorize(admin_of_org2, action, PROJECT_TARGET) is False


@pytest.mark.parametrize("action", [MANAGE, VIEW_ACCESS])
def test_a_project_admin_role_counts_only_on_its_own_project(action: str) -> None:
    """An admin of PROJ2 (same org) holds both there and neither on PROJ."""
    other = PERSONAS["other_project_admin"]

    assert authorize(other, action, Target(WS, ORG, PROJ2)) is True
    assert authorize(other, action, PROJECT_TARGET) is False


# --- An archived project (design-doc §5, step 1; §9: read-only) ---------------------------------


@pytest.mark.parametrize("persona", list(PERSONAS))
def test_an_archived_project_denies_managing_members_to_everyone(persona: str) -> None:
    """DL-79: a mutation, so an archived project denies it, system admins included. (Removal
    with their projects is the handler's path, not this action.)"""
    assert authorize(PERSONAS[persona], MANAGE, ARCHIVED_PROJECT_TARGET) is False


@pytest.mark.parametrize(("persona", "allowed"), rows(PROJECT_ADMINS))
def test_the_access_review_of_an_archived_project_is_still_open_to_its_admins(
    persona: str, allowed: bool
) -> None:
    """DL-79: not a mutation; an archived project is still browsable (§9)."""
    assert authorize(PERSONAS[persona], VIEW_ACCESS, ARCHIVED_PROJECT_TARGET) is allowed


# --- ensure(): 403 for who sees the project, 404 for who doesn't --------------------------------


@pytest.mark.parametrize(
    ("persona", "target"),
    [
        ("project_member", PROJECT_TARGET),
        ("project_viewer", PROJECT_TARGET),
        ("project_viewer", ARCHIVED_PROJECT_TARGET),
        ("project_admin", ARCHIVED_PROJECT_TARGET),
        ("org_admin", ARCHIVED_PROJECT_TARGET),
        ("workspace_owner", ARCHIVED_PROJECT_TARGET),
        ("system_admin", ARCHIVED_PROJECT_TARGET),
    ],
)
def test_managing_members_is_403_to_who_sees_the_project(persona: str, target: Target) -> None:
    with pytest.raises(ForbiddenError):
        ensure(PERSONAS[persona], MANAGE, target)


@pytest.mark.parametrize("target", [PROJECT_TARGET, ARCHIVED_PROJECT_TARGET])
@pytest.mark.parametrize("persona", UNSEEN)
@pytest.mark.parametrize("action", [MANAGE, VIEW_ACCESS])
def test_both_actions_are_404_to_who_cannot_see_the_project(
    action: str, persona: str, target: Target
) -> None:
    with pytest.raises(NotFoundError):
        ensure(PERSONAS[persona], action, target)


# --- allowed_actions on a project (the project read; the member list's rows) ----------------------


@pytest.mark.parametrize(("persona", "listed"), rows(PROJECT_ADMINS))
@pytest.mark.parametrize("action", [MANAGE, VIEW_ACCESS])
def test_a_projects_allowed_actions_carry_them_exactly_where_allowed(
    action: str, persona: str, listed: bool
) -> None:
    """Build plan, "The project members API": a member row carries `project_member.manage` when
    the caller holds it; `allowed_actions` are evaluated through `authorize()`."""
    assert (action in allowed_actions(PERSONAS[persona], PROJECT_TARGET)) is listed


@pytest.mark.parametrize("persona", list(PERSONAS))
def test_an_archived_projects_allowed_actions_never_carry_managing_members(persona: str) -> None:
    assert MANAGE not in allowed_actions(PERSONAS[persona], ARCHIVED_PROJECT_TARGET)


@pytest.mark.parametrize(("persona", "listed"), rows(PROJECT_ADMINS))
def test_an_archived_projects_allowed_actions_keep_the_access_review(
    persona: str, listed: bool
) -> None:
    assert (VIEW_ACCESS in allowed_actions(PERSONAS[persona], ARCHIVED_PROJECT_TARGET)) is listed
