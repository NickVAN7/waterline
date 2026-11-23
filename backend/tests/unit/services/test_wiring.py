"""Importing `app.services.wiring`, or any entry point (the worker, the CLI, the app), alone
registers every cross-area handler (the handoff's Package 4 item 2), whatever else a process
imports. Run in a fresh interpreter: this test session has imported every service already."""

import json
import subprocess
import sys

import pytest

from tests.conftest import BACKEND

# Prints each registry's handlers by name, after importing only the module named first.
SCRIPT = """
import importlib, json, sys
importlib.import_module(sys.argv[1])
from app.services import approval, project, roster, user
print(json.dumps({
    "email_changed": [h.__name__ for h in user._ON_EMAIL_CHANGED],
    "member_removed": [h.__name__ for h in roster._ON_MEMBER_REMOVED],
    "restriction_changed": [h.__name__ for h in project._ON_RESTRICTION_CHANGED],
    "approved": {str(k): h.__name__ for k, h in approval._ON_APPROVED.items()},
    "rejected": {str(k): h.__name__ for k, h in approval._ON_REJECTED.items()},
}))
"""


# The worker is the one that needs it: its own imports reach only some areas (S3-C0s review).
@pytest.mark.parametrize(
    "module", ["app.services.wiring", "app.jobs.worker", "app.cli", "app.main"]
)
def test_importing_it_alone_fills_every_handler_registry(module: str) -> None:
    """Bug: a registry filled only when some other import happens to load the area that
    registers into it, so a process that never imports it skips the handler silently."""
    result = subprocess.run(  # noqa: S603 -- fixed arguments: this interpreter running SCRIPT
        [sys.executable, "-c", SCRIPT, module],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )

    assert json.loads(result.stdout) == {
        "email_changed": ["_end_sessions"],
        "member_removed": ["_remove_with_projects"],
        "restriction_changed": ["_lift_requirements"],
        "approved": {"requirement": "_approved"},
        "rejected": {"requirement": "_rejected"},
    }
