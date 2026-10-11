"""The action registry (build plan, "Authorization (§5)"; DL-44, DL-45, DL-56). No test-only
action is registered in this module."""

import pytest

from app.authz.actions import REGISTRY, Level

pytestmark = pytest.mark.security


def test_the_registry_holds_exactly_the_s1_c7_to_s1_c9_actions() -> None:
    """DL-44: each checkpoint registers its own area's actions; S1-C7 the four workspace-level
    ones (DL-45), S1-C8 three more (DL-56), S1-C9 three more (DL-68)."""
    assert sorted(REGISTRY) == [
        "org.create",
        "org.update",
        "org.view",
        "org_member.manage",
        "org_member.manage_admins",
        "user.check",
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
    ],
)
def test_each_real_action_is_registered_at_its_level(action: str, level: Level) -> None:
    """DL-45 and DL-56: `workspace_staff.manage_admins` is workspace-level (`/me` carries it);
    `org.view` and `org.update` are at org level."""
    assert REGISTRY[action].level is level
