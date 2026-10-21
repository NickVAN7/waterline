"""Every real action's registration keeps design-doc §5's inheritance rules, so a later area
can't hand an action to every org member or staff member by a wrong role in its `ActionSpec`
(S1-C7 security review). Not a spec test: it checks registrations, not `authorize()`."""

import pytest

from app.authz.actions import REGISTRY, Action, ActionSpec
from app.enums import OrgRole, WorkspaceRole

pytestmark = pytest.mark.security

REAL = [pytest.param(action, REGISTRY[action], id=action.value) for action in Action]


@pytest.mark.parametrize(("action", "spec"), REAL)
def test_an_org_member_role_grants_only_project_creation(action: Action, spec: ActionSpec) -> None:
    """§5, "Org roles": an org member gets no other action through the org role."""
    assert spec.org_role is not OrgRole.MEMBER or action == "project.create"


@pytest.mark.parametrize(("action", "spec"), REAL)
def test_staff_membership_alone_grants_no_action(action: Action, spec: ActionSpec) -> None:
    """§5, "Workspace roles": a workspace member sees only what they're assigned to, with no
    inherited access and no workspace pages."""
    assert spec.workspace_role is not WorkspaceRole.MEMBER
