"""S1-C11's six actions (DL-77; build plan, "Projects (§1.1, §3)", "The project actions"):

- org level: `project.create` (org members and up, workspace owners/admins, system admins; a
  project-only link to the org grants nothing) and `project.assign_first_admin` (org
  owners/admins, workspace owners/admins, system admins);
- project level: `project.view` (project viewers and up, and inherited admins; not a mutation,
  so still allowed on an archived project), `project.update` (project admins, inherited
  included), `project.archive` and `project.unarchive` (org owners/admins, workspace
  owners/admins, system admins; `project.unarchive` is archive-exempt). An archived project
  denies every other mutation (design-doc §5, step 1), archiving it again included.

Personas are those of tests/support/authz.py, relative to workspace WS, org ORG, and project
PROJ (in ORG).
"""

import uuid

import pytest

from app.authz.authorize import allowed_actions, authorize, ensure
from app.authz.context import AuthzContext, ProjectAccess
from app.authz.target import Target
from app.core.errors import ForbiddenError, NotFoundError
from app.enums import OrgRole, ProjectRole, WorkspaceRole
from tests.support.authz import (
    ARCHIVED_PROJECT_TARGET,
    ORG,
    ORG2,
    ORG_TARGET,
    PERSONAS,
    PROJ,
    PROJ2,
    PROJECT_TARGET,
    WS,
    rows,
)

pytestmark = pytest.mark.security

INHERITED_ADMINS = {"system_admin", "workspace_owner", "workspace_admin", "org_owner", "org_admin"}
ORG_MEMBERS_AND_UP = INHERITED_ADMINS | {"org_member"}
PROJECT_ADMINS = INHERITED_ADMINS | {"project_admin"}
SEES_THE_PROJECT = PROJECT_ADMINS | {"project_member", "project_viewer"}


# --- project.create (org level) -----------------------------------------------------------------


@pytest.mark.parametrize(("persona", "allowed"), rows(ORG_MEMBERS_AND_UP))
def test_project_create_is_for_org_members_and_the_admins_above(
    persona: str, allowed: bool
) -> None:
    """design-doc §5, "Org roles": an org member creates projects in the org; a project
    membership there, staff membership alone, and roles elsewhere don't."""
    assert authorize(PERSONAS[persona], "project.create", ORG_TARGET) is allowed


@pytest.mark.parametrize("role", list(ProjectRole))
def test_a_project_only_link_to_the_org_grants_no_project_create(role: ProjectRole) -> None:
    """Users whose only link to an org is a project membership can't create projects in it,
    even as that project's admin and as staff of its workspace."""
    linked = AuthzContext(
        user_id=uuid.uuid4(),
        workspace_roles={WS: WorkspaceRole.MEMBER},
        projects={PROJ: ProjectAccess(role, ORG, WS)},
    )

    assert authorize(linked, "project.create", ORG_TARGET) is False


def test_an_org_member_creates_projects_only_in_their_own_org() -> None:
    member_of_org2 = AuthzContext(
        user_id=uuid.uuid4(), org_roles={ORG2: OrgRole.MEMBER}, org_workspaces={ORG2: WS}
    )

    assert authorize(member_of_org2, "project.create", Target(WS, organization_id=ORG2)) is True
    assert authorize(member_of_org2, "project.create", ORG_TARGET) is False


# --- project.assign_first_admin (org level) -----------------------------------------------------


@pytest.mark.parametrize(("persona", "allowed"), rows(INHERITED_ADMINS))
def test_naming_another_first_admin_is_for_org_owners_admins_and_above(
    persona: str, allowed: bool
) -> None:
    """design-doc §5, "Org roles": an org admin may name someone else; a plain org member
    creates projects but may not."""
    assert authorize(PERSONAS[persona], "project.assign_first_admin", ORG_TARGET) is allowed


# --- ensure() on the org-level actions: 403 for who sees the org, 404 for who doesn't -----------


@pytest.mark.parametrize(
    ("persona", "action"),
    [
        ("org_member", "project.assign_first_admin"),
        ("project_admin", "project.create"),
        ("project_viewer", "project.create"),
        ("other_project_admin", "project.create"),
        ("project_admin", "project.assign_first_admin"),
    ],
)
def test_an_org_level_project_action_is_403_to_who_sees_the_org(persona: str, action: str) -> None:
    with pytest.raises(ForbiddenError):
        ensure(PERSONAS[persona], action, ORG_TARGET)


@pytest.mark.parametrize(
    "persona", ["workspace_member", "other_org_owner", "other_workspace_owner", "nobody"]
)
@pytest.mark.parametrize("action", ["project.create", "project.assign_first_admin"])
def test_an_org_level_project_action_is_404_to_who_cannot_see_the_org(
    persona: str, action: str
) -> None:
    with pytest.raises(NotFoundError):
        ensure(PERSONAS[persona], action, ORG_TARGET)


# --- The project-level actions on an unarchived project -----------------------------------------


@pytest.mark.parametrize(("persona", "allowed"), rows(SEES_THE_PROJECT))
def test_project_view_is_for_its_members_and_inherited_admins(persona: str, allowed: bool) -> None:
    """An org membership alone (role member) shows the org, not its projects (§4); nor does
    another project in the same org."""
    assert authorize(PERSONAS[persona], "project.view", PROJECT_TARGET) is allowed


@pytest.mark.parametrize(("persona", "allowed"), rows(PROJECT_ADMINS))
def test_project_update_is_for_project_admins_inherited_included(
    persona: str, allowed: bool
) -> None:
    assert authorize(PERSONAS[persona], "project.update", PROJECT_TARGET) is allowed


@pytest.mark.parametrize("action", ["project.archive", "project.unarchive"])
@pytest.mark.parametrize(("persona", "allowed"), rows(INHERITED_ADMINS))
def test_archive_and_unarchive_are_for_org_owners_admins_and_above(
    action: str, persona: str, allowed: bool
) -> None:
    """design-doc §5, "Org roles": archiving is an org admin's; an explicit project admin who
    holds no admin role above the project may not."""
    assert authorize(PERSONAS[persona], action, PROJECT_TARGET) is allowed


def test_an_org_admin_inherits_project_admin_only_in_their_own_org() -> None:
    admin_of_org2 = AuthzContext(
        user_id=uuid.uuid4(), org_roles={ORG2: OrgRole.ADMIN}, org_workspaces={ORG2: WS}
    )

    assert authorize(admin_of_org2, "project.archive", PROJECT_TARGET) is False
    assert authorize(admin_of_org2, "project.update", PROJECT_TARGET) is False


def test_a_project_role_counts_only_on_its_own_project() -> None:
    """An admin of PROJ2 (same org) is nobody on PROJ."""
    other = PERSONAS["other_project_admin"]
    assert authorize(other, "project.update", Target(WS, ORG, PROJ2)) is True
    assert authorize(other, "project.update", PROJECT_TARGET) is False


# --- An archived project (design-doc §5, step 1; §9: read-only, still browsable) ----------------


@pytest.mark.parametrize(("persona", "allowed"), rows(SEES_THE_PROJECT))
def test_an_archived_project_can_still_be_viewed(persona: str, allowed: bool) -> None:
    assert authorize(PERSONAS[persona], "project.view", ARCHIVED_PROJECT_TARGET) is allowed


@pytest.mark.parametrize("action", ["project.update", "project.archive"])
@pytest.mark.parametrize("persona", list(PERSONAS))
def test_an_archived_project_denies_update_and_archive_to_everyone(
    action: str, persona: str
) -> None:
    """System admins included; archiving an archived project is denied like any mutation."""
    assert authorize(PERSONAS[persona], action, ARCHIVED_PROJECT_TARGET) is False


@pytest.mark.parametrize(("persona", "allowed"), rows(INHERITED_ADMINS))
def test_an_archived_project_can_be_unarchived_by_who_may_archive(
    persona: str, allowed: bool
) -> None:
    """Unarchive is the archive-exempt mutation; still not a project admin's."""
    assert authorize(PERSONAS[persona], "project.unarchive", ARCHIVED_PROJECT_TARGET) is allowed


# --- ensure() on the project-level actions -------------------------------------------------------


@pytest.mark.parametrize(
    ("persona", "action", "target"),
    [
        ("project_member", "project.update", PROJECT_TARGET),
        ("project_viewer", "project.update", PROJECT_TARGET),
        ("project_admin", "project.archive", PROJECT_TARGET),
        ("project_viewer", "project.archive", PROJECT_TARGET),
        ("project_admin", "project.unarchive", ARCHIVED_PROJECT_TARGET),
        ("system_admin", "project.update", ARCHIVED_PROJECT_TARGET),
        ("org_admin", "project.archive", ARCHIVED_PROJECT_TARGET),
        ("project_admin", "project.update", ARCHIVED_PROJECT_TARGET),
    ],
)
def test_a_project_action_is_403_to_who_sees_the_project(
    persona: str, action: str, target: Target
) -> None:
    with pytest.raises(ForbiddenError):
        ensure(PERSONAS[persona], action, target)


@pytest.mark.parametrize(
    "persona",
    [
        "org_member",
        "other_project_admin",
        "workspace_member",
        "other_org_owner",
        "other_workspace_owner",
        "nobody",
    ],
)
@pytest.mark.parametrize(
    "action", ["project.view", "project.update", "project.archive", "project.unarchive"]
)
def test_a_project_action_is_404_to_who_cannot_see_the_project(persona: str, action: str) -> None:
    with pytest.raises(NotFoundError):
        ensure(PERSONAS[persona], action, PROJECT_TARGET)


# --- allowed_actions on a project (the project read, DL-76) -------------------------------------

INHERITED_ON_A_LIVE_PROJECT = [
    "project.archive",
    "project.lower_restriction",
    "project.raise_restriction",
    "project.unarchive",
    "project.update",
    "project.view",
    "project.view_access",
    "project_member.manage",
    "requirement.create",
    "requirement.view",
]


@pytest.mark.parametrize(
    ("persona", "expected"),
    [
        ("system_admin", INHERITED_ON_A_LIVE_PROJECT),
        ("workspace_owner", INHERITED_ON_A_LIVE_PROJECT),
        ("workspace_admin", INHERITED_ON_A_LIVE_PROJECT),
        ("org_owner", INHERITED_ON_A_LIVE_PROJECT),
        ("org_admin", INHERITED_ON_A_LIVE_PROJECT),
        (
            "project_admin",
            [
                "project.lower_restriction",
                "project.raise_restriction",
                "project.update",
                "project.view",
                "project.view_access",
                "project_member.manage",
                "requirement.create",
                "requirement.view",
            ],
        ),
        ("project_member", ["project.view", "requirement.create", "requirement.view"]),
        ("project_viewer", ["project.view", "requirement.view"]),
        ("org_member", []),
        ("other_project_admin", []),
        ("nobody", []),
    ],
)
def test_allowed_actions_on_a_project(persona: str, expected: list[str]) -> None:
    assert allowed_actions(PERSONAS[persona], PROJECT_TARGET) == expected


@pytest.mark.parametrize(
    ("persona", "expected"),
    [
        (
            "system_admin",
            ["project.unarchive", "project.view", "project.view_access", "requirement.view"],
        ),
        (
            "workspace_admin",
            ["project.unarchive", "project.view", "project.view_access", "requirement.view"],
        ),
        (
            "org_admin",
            ["project.unarchive", "project.view", "project.view_access", "requirement.view"],
        ),
        ("project_admin", ["project.view", "project.view_access", "requirement.view"]),
        ("project_viewer", ["project.view", "requirement.view"]),
        ("org_member", []),
    ],
)
def test_allowed_actions_on_an_archived_project(persona: str, expected: list[str]) -> None:
    assert allowed_actions(PERSONAS[persona], ARCHIVED_PROJECT_TARGET) == expected


# --- allowed_actions on an org (/me's org entries; the org read) --------------------------------

ALL_ORG_LEVEL = [
    "org.update",
    "org.view",
    "org_member.manage",
    "org_member.manage_admins",
    "project.assign_first_admin",
    "project.create",
]


@pytest.mark.parametrize(
    ("persona", "expected"),
    [
        ("system_admin", ALL_ORG_LEVEL),
        ("workspace_owner", ALL_ORG_LEVEL),
        ("workspace_admin", ALL_ORG_LEVEL),
        ("org_owner", ALL_ORG_LEVEL),
        (
            "org_admin",
            ["org.view", "org_member.manage", "project.assign_first_admin", "project.create"],
        ),
        ("org_member", ["org.view", "project.create"]),
        ("project_admin", ["org.view"]),
        ("project_viewer", ["org.view"]),
        ("other_project_admin", ["org.view"]),
        ("workspace_member", []),
        ("other_org_owner", []),
        ("nobody", []),
    ],
)
def test_allowed_actions_on_an_org_carry_the_project_actions(
    persona: str, expected: list[str]
) -> None:
    assert allowed_actions(PERSONAS[persona], ORG_TARGET) == expected
