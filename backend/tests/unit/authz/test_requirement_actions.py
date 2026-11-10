"""S2-C3's `requirement.view` (S2-plan, "Actions per row": project viewers and up, inherited
admins; kind content; design-doc §5, "The choke point", "Role capabilities"; §4, "Visibility"):

- granted to the project's viewers, members, and admins, and to inherited admins (system
  admins, workspace owners/admins, owners/admins of the project's org), on the project and on a
  requirement inside it;
- denied to everyone else: an org member without a project role, an admin of another project,
  a workspace member not on the project, another org's or workspace's owner, nobody;
- a read, so an archived project still allows it (§5 step 1 denies mutations only; §9: an
  archived project is "still browsable");
- `ensure()`: 404 to who can't see the project (§5: "404, not 403"); nobody who sees the project
  is denied it.

Export control (S2-C4) is not covered here. Personas are those of tests/support/authz.py,
relative to workspace WS, org ORG, and project PROJ (in ORG).
"""

import pytest

from app.authz.authorize import authorize, ensure
from app.authz.target import Target
from app.core.errors import NotFoundError
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

VIEW = "requirement.view"

INHERITED_ADMINS = {"system_admin", "workspace_owner", "workspace_admin", "org_owner", "org_admin"}
SEES_THE_PROJECT = INHERITED_ADMINS | {"project_admin", "project_member", "project_viewer"}
UNSEEN = [
    "org_member",
    "other_project_admin",
    "workspace_member",
    "other_org_owner",
    "other_workspace_owner",
    "nobody",
]


class _Requirement:
    """A stand-in for a requirement inside PROJ (`project_target(project, requirement)`)."""


REQUIREMENT_TARGET = Target(
    workspace_id=WS, organization_id=ORG, project_id=PROJ, entity=_Requirement()
)
ARCHIVED_REQUIREMENT_TARGET = Target(
    workspace_id=WS, organization_id=ORG, project_id=PROJ, archived=True, entity=_Requirement()
)
LIVE = [PROJECT_TARGET, REQUIREMENT_TARGET]
ARCHIVED = [ARCHIVED_PROJECT_TARGET, ARCHIVED_REQUIREMENT_TARGET]
TARGET_IDS = ["project", "requirement"]


@pytest.mark.parametrize("target", LIVE, ids=TARGET_IDS)
@pytest.mark.parametrize(("persona", "allowed"), rows(SEES_THE_PROJECT))
def test_requirement_view_is_for_project_viewers_and_up_and_inherited_admins(
    persona: str, allowed: bool, target: Target
) -> None:
    """S2-plan, S2-C3 row; §5 "Role capabilities": a viewer views "the project and everything in
    it"; an org membership alone shows the org, not its projects (§4)."""
    assert authorize(PERSONAS[persona], VIEW, target) is allowed


@pytest.mark.parametrize("target", ARCHIVED, ids=TARGET_IDS)
@pytest.mark.parametrize(("persona", "allowed"), rows(SEES_THE_PROJECT))
def test_requirement_view_still_works_in_an_archived_project(
    persona: str, allowed: bool, target: Target
) -> None:
    """§5 step 1 denies mutations only; §9: an archived project is read-only, still browsable."""
    assert authorize(PERSONAS[persona], VIEW, target) is allowed


def test_a_project_role_grants_requirement_view_only_on_its_own_project() -> None:
    """The admin of PROJ2 (same org) views PROJ2's requirements, not PROJ's."""
    other = PERSONAS["other_project_admin"]

    assert authorize(other, VIEW, Target(WS, ORG, PROJ2)) is True
    assert authorize(other, VIEW, PROJECT_TARGET) is False


@pytest.mark.parametrize(
    "target", [*LIVE, *ARCHIVED], ids=[*TARGET_IDS, "archived", "archived-req"]
)
@pytest.mark.parametrize("persona", sorted(SEES_THE_PROJECT))
def test_ensure_lets_who_sees_the_project_view_its_requirements(
    persona: str, target: Target
) -> None:
    """Nobody who sees the project is denied the read, so there's no 403 case for it."""
    assert ensure(PERSONAS[persona], VIEW, target) is None


@pytest.mark.parametrize(
    "target", [*LIVE, *ARCHIVED], ids=[*TARGET_IDS, "archived", "archived-req"]
)
@pytest.mark.parametrize("persona", UNSEEN)
def test_requirement_view_is_404_to_who_cannot_see_the_project(
    persona: str, target: Target
) -> None:
    """§5: failures on entities the user can't see return 404, not 403."""
    with pytest.raises(NotFoundError):
        ensure(PERSONAS[persona], VIEW, target)
