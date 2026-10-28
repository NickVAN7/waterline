"""The action registry (build plan, "Authorization (§5)"; DL-44, DL-45, DL-56, DL-68, DL-73).
No test-only action is registered in this module."""

import pytest

from app.authz.actions import REGISTRY, Level

pytestmark = pytest.mark.security


def test_the_registry_holds_exactly_the_s1_c7_to_s1_c13_actions() -> None:
    """DL-44: each checkpoint registers its own area's actions; S1-C7 the four workspace-level
    ones (DL-45), S1-C8 three more (DL-56), S1-C9 three more (DL-68), S1-C10 two (DL-73; no
    separate `user.reset_password`), S1-C11 six (DL-77), S1-C12 two (DL-79), S1-C13 two (DL-82)."""
    assert sorted(REGISTRY) == [
        "org.create",
        "org.update",
        "org.view",
        "org_member.manage",
        "org_member.manage_admins",
        "project.archive",
        "project.assign_first_admin",
        "project.create",
        "project.lower_restriction",
        "project.raise_restriction",
        "project.unarchive",
        "project.update",
        "project.view",
        "project.view_access",
        "project_member.manage",
        "requirement.approve_manually",
        "requirement.create",
        "requirement.lower_restriction",
        "requirement.raise_restriction",
        "requirement.reassign_reporter",
        "requirement.update",
        "requirement.view",
        "user.check",
        "user.manage",
        "user.view_access",
        "workspace.update",
        "workspace.view",
        "workspace_staff.manage",
        "workspace_staff.manage_admins",
    ]


@pytest.mark.parametrize(
    ("action", "level"),
    [
        ("workspace.view", Level.WORKSPACE),
        ("workspace.update", Level.WORKSPACE),
        ("workspace_staff.manage", Level.WORKSPACE),
        ("workspace_staff.manage_admins", Level.WORKSPACE),
        ("org.create", Level.WORKSPACE),
        ("org.view", Level.ORGANIZATION),
        ("org.update", Level.ORGANIZATION),
        ("org_member.manage", Level.ORGANIZATION),
        ("org_member.manage_admins", Level.ORGANIZATION),
        ("user.check", Level.WORKSPACE),
        ("user.manage", Level.USER),
        ("user.view_access", Level.USER),
        ("project.create", Level.ORGANIZATION),
        ("project.assign_first_admin", Level.ORGANIZATION),
        ("project.view", Level.PROJECT),
        ("project.update", Level.PROJECT),
        ("project.archive", Level.PROJECT),
        ("project.unarchive", Level.PROJECT),
        ("project_member.manage", Level.PROJECT),
        ("project.view_access", Level.PROJECT),
        ("requirement.view", Level.PROJECT),
        ("requirement.create", Level.PROJECT),
        ("requirement.update", Level.PROJECT),
        ("requirement.reassign_reporter", Level.PROJECT),
        ("requirement.raise_restriction", Level.PROJECT),
        ("requirement.lower_restriction", Level.PROJECT),
        ("requirement.approve_manually", Level.PROJECT),
    ],
)
def test_each_real_action_is_registered_at_its_level(action: str, level: Level) -> None:
    """DL-45 and DL-56: `workspace_staff.manage_admins` is workspace-level (`/me` carries it);
    `org.view` and `org.update` are at org level; DL-73: the account actions are on a user
    target, at its own level; DL-77: the two creation actions at org level (so `/me`'s org
    entries carry them), the other four on the project; DL-79: both member actions on the
    project."""
    assert REGISTRY[action].level is level
