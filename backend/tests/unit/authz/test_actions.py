"""The action registry (build plan, "Authorization (§5)"; DL-44, DL-45, DL-56, DL-68, DL-73).
No test-only action is registered in this module."""

import pytest

from app.authz.actions import REGISTRY
from tests.support.authz import EXPECTED, Expected

pytestmark = pytest.mark.security


def test_the_registry_holds_exactly_the_expected_actions() -> None:
    """DL-44: each checkpoint registers its own area's actions; the expected registry lists every
    one (tests/support/authz.py, TD-78), so an action registered without a row fails here."""
    assert sorted(REGISTRY) == sorted(EXPECTED)


@pytest.mark.parametrize(("action", "expected"), sorted(EXPECTED.items()))
def test_each_real_action_is_registered_as_expected(action: str, expected: Expected) -> None:
    """Its level (DL-45, DL-56, DL-73, DL-77, DL-79), content or management (DL-82; §3.1), the
    lowest project role granting it, whether it changes anything, whether an archived project
    still allows it, whether only an explicit role grants it behind the gate (DL-82), and whether
    it's personal: a relationship grants it, no role (§5, "Personal actions")."""
    spec = REGISTRY[action]
    assert (
        spec.level,
        spec.access,
        spec.project_role,
        spec.mutation,
        spec.archive_exempt,
        spec.explicit_when_export_controlled,
        spec.relationship is not None,
    ) == (
        expected.level,
        expected.access,
        expected.project_role,
        expected.mutation,
        expected.archive_exempt,
        expected.explicit_when_export_controlled,
        expected.personal,
    )
