"""The action registry (build plan, "Authorization (§5)"; DL-44, DL-45). No test-only action is
registered in this module."""

import pytest

from app.authz.actions import REGISTRY, Action, Level

pytestmark = pytest.mark.security


def test_the_registry_holds_exactly_the_four_workspace_level_actions() -> None:
    """DL-44: S1-C7 registers only the workspace-level actions; each later checkpoint adds its
    own area's."""
    assert sorted(REGISTRY) == [
        "org.create",
        "workspace.update",
        "workspace.view",
        "workspace_staff.manage",
    ]


@pytest.mark.parametrize("action", list(Action))
def test_each_real_action_is_registered_at_workspace_level(action: Action) -> None:
    assert REGISTRY[action].level is Level.WORKSPACE
