"""S3-C12's action `project.view_activity`, the project activity feed (S3-plan, "Actions per
row", S3-C12, and Q10; design-doc §5, "The project activity feed is content"; §3.1,
"Export-controlled projects (who sees content)"):

- a project-level content action, for project viewers and up and inherited admins (system,
  workspace, and org owners/admins);
- not a mutation: an archived project still allows it (§5 step 1; §9, still browsable);
- content: on an export-controlled project an inherited admin without an explicit membership is
  denied it (a 404 from `ensure()`), project entries included; explicit members keep it.

Personas are those of tests/support/authz.py, relative to workspace WS, org ORG, and project
PROJ (in ORG).
"""

from dataclasses import replace

import pytest

from app.authz.actions import REGISTRY, Level
from app.authz.authorize import authorize, ensure
from app.authz.context import ProjectAccess
from app.authz.target import Target
from app.core.errors import NotFoundError
from app.enums import AccessKind, ProjectRole
from tests.support.authz import (
    ARCHIVED_PROJECT_TARGET,
    ORG,
    PERSONAS,
    PROJ,
    PROJ2,
    PROJECT_TARGET,
    WS,
    rows,
)

pytestmark = pytest.mark.security

VIEW_ACTIVITY = "project.view_activity"

INHERITED_ADMINS = {"system_admin", "workspace_owner", "workspace_admin", "org_owner", "org_admin"}
EXPLICIT = {"project_admin", "project_member", "project_viewer"}
SEES_THE_PROJECT = INHERITED_ADMINS | EXPLICIT
UNSEEN = [
    "org_member",
    "other_project_admin",
    "workspace_member",
    "other_org_owner",
    "other_workspace_owner",
    "nobody",
]

EC = Target(workspace_id=WS, organization_id=ORG, project_id=PROJ, export_controlled=True)
ARCHIVED_EC = Target(
    workspace_id=WS, organization_id=ORG, project_id=PROJ, archived=True, export_controlled=True
)


# --- The registry entry --------------------------------------------------------------------------


def test_it_is_a_project_level_content_read_from_the_viewer_role() -> None:
    """Q10: one content action; viewers and up; a read, so not a mutation and not archive-exempt
    (nothing to exempt); no explicit-only rule beyond the gate; not personal."""
    spec = REGISTRY[VIEW_ACTIVITY]

    assert (
        spec.level,
        spec.access,
        spec.project_role,
        spec.mutation,
        spec.archive_exempt,
        spec.explicit_when_export_controlled,
        spec.relationship is None,
    ) == (Level.PROJECT, AccessKind.CONTENT, ProjectRole.VIEWER, False, False, False, True)


# --- Who may, on a live project ------------------------------------------------------------------


@pytest.mark.parametrize(("persona", "allowed"), rows(SEES_THE_PROJECT))
def test_the_feed_is_for_viewers_and_up_and_inherited_admins(persona: str, allowed: bool) -> None:
    assert authorize(PERSONAS[persona], VIEW_ACTIVITY, PROJECT_TARGET) is allowed


def test_a_project_role_grants_it_only_on_its_own_project() -> None:
    """The admin of PROJ2 (same org) reads PROJ2's feed, not PROJ's."""
    other = PERSONAS["other_project_admin"]

    assert authorize(other, VIEW_ACTIVITY, Target(WS, ORG, PROJ2)) is True
    assert authorize(other, VIEW_ACTIVITY, PROJECT_TARGET) is False


@pytest.mark.parametrize("persona", UNSEEN)
def test_the_feed_is_404_to_who_cannot_see_the_project(persona: str) -> None:
    with pytest.raises(NotFoundError):
        ensure(PERSONAS[persona], VIEW_ACTIVITY, PROJECT_TARGET)


@pytest.mark.parametrize("persona", sorted(SEES_THE_PROJECT))
def test_ensure_lets_who_sees_the_project_read_the_feed(persona: str) -> None:
    assert ensure(PERSONAS[persona], VIEW_ACTIVITY, PROJECT_TARGET) is None


# --- An archived project: still readable (§5 step 1, §9) ----------------------------------------


@pytest.mark.parametrize(("persona", "allowed"), rows(SEES_THE_PROJECT))
def test_the_feed_stays_readable_in_an_archived_project(persona: str, allowed: bool) -> None:
    assert authorize(PERSONAS[persona], VIEW_ACTIVITY, ARCHIVED_PROJECT_TARGET) is allowed


# --- Export control (§3.1; §5 "The project activity feed is content"; Q10) ----------------------


@pytest.mark.parametrize(("persona", "allowed"), rows(EXPLICIT))
def test_on_an_ec_project_the_feed_is_for_explicit_members_only(
    persona: str, allowed: bool
) -> None:
    assert authorize(PERSONAS[persona], VIEW_ACTIVITY, EC) is allowed


@pytest.mark.parametrize(("persona", "allowed"), rows(EXPLICIT))
def test_on_an_archived_ec_project_the_feed_is_for_explicit_members_only(
    persona: str, allowed: bool
) -> None:
    assert authorize(PERSONAS[persona], VIEW_ACTIVITY, ARCHIVED_EC) is allowed


@pytest.mark.parametrize("persona", sorted(INHERITED_ADMINS))
def test_that_denial_to_an_inherited_admin_is_a_404(persona: str) -> None:
    with pytest.raises(NotFoundError):
        ensure(PERSONAS[persona], VIEW_ACTIVITY, EC)


@pytest.mark.parametrize("persona", sorted(INHERITED_ADMINS))
def test_an_inherited_admin_with_a_viewer_membership_reads_an_ec_projects_feed(
    persona: str,
) -> None:
    ctx = replace(PERSONAS[persona], projects={PROJ: ProjectAccess(ProjectRole.VIEWER, ORG, WS)})

    assert authorize(ctx, VIEW_ACTIVITY, EC) is True
