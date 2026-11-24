"""S3-C2's actions for phases, workstreams, tasks, and subtasks (S3-plan, "Actions per row";
design-doc §5, "The choke point", "Role capabilities", "Other targeted rules" → Deletion; §3.1;
DL-82, DL-211, DL-219, DL-223):

- reads (`phase.view`, `workstream.view`, `task.view`): viewers and up, inherited admins;
- `phase.manage`, `workstream.manage`, `task.create`, `task.update`, `task.raise_restriction`,
  `subtask.manage`: members and up ("project admin" always includes inherited admin);
- `task.reassign_reporter`, `task.lower_restriction`: project admins (as the requirement's);
- `task.delete`, `task.restore`: project admins, and the task's reporter as a project member
  (member role or above); whoever may delete may restore;
- all content: on an export-controlled project an inherited admin without an explicit
  membership is denied every one (a 404 from `ensure()`); lowering there needs an explicit
  project admin (DL-82);
- every one but the reads is a mutation: an archived project denies it to everyone (§5 step 1).

Personas are those of tests/support/authz.py, relative to workspace WS, org ORG, and project
PROJ (in ORG).
"""

import uuid
from dataclasses import replace

import pytest

from app.authz.authorize import authorize, ensure
from app.authz.context import AuthzContext, ProjectAccess
from app.authz.target import Target
from app.core.errors import ForbiddenError, NotFoundError
from app.enums import ProjectRole
from app.models.task import Task
from tests.support.authz import ORG, PERSONAS, PROJ, PROJ2, WS, rows

pytestmark = pytest.mark.security

READS = ["phase.view", "workstream.view", "task.view"]
MEMBER_ACTIONS = [
    "phase.manage",
    "workstream.manage",
    "task.create",
    "task.update",
    "task.raise_restriction",
    "subtask.manage",
]
ADMIN_ACTIONS = ["task.reassign_reporter", "task.lower_restriction", "task.delete", "task.restore"]
MUTATIONS = MEMBER_ACTIONS + ADMIN_ACTIONS
ALL = READS + MUTATIONS
DELETE_AND_RESTORE = ["task.delete", "task.restore"]

INHERITED_ADMINS = {"system_admin", "workspace_owner", "workspace_admin", "org_owner", "org_admin"}
PROJECT_ADMINS = INHERITED_ADMINS | {"project_admin"}
MEMBERS_AND_UP = PROJECT_ADMINS | {"project_member"}
SEES_THE_PROJECT = MEMBERS_AND_UP | {"project_viewer"}
EXPLICIT = {"project_admin", "project_member", "project_viewer"}
UNSEEN = [
    "org_member",
    "other_project_admin",
    "workspace_member",
    "other_org_owner",
    "other_workspace_owner",
    "nobody",
]

SOMEONE_ELSE = uuid.UUID(int=5000)


def task_target(
    reporter: uuid.UUID = SOMEONE_ELSE,
    *,
    project: uuid.UUID = PROJ,
    archived: bool = False,
    export_controlled: bool = False,
) -> Target:
    """A task reported by `reporter` inside `project` (in ORG), as `project_target(project,
    task)` builds it."""
    return Target(
        workspace_id=WS,
        organization_id=ORG,
        project_id=project,
        archived=archived,
        export_controlled=export_controlled,
        entity=Task(reporter_id=reporter),
    )


def own(persona: str, *, archived: bool = False, export_controlled: bool = False) -> Target:
    """A task in PROJ reported by `persona` themself."""
    return task_target(
        PERSONAS[persona].user_id, archived=archived, export_controlled=export_controlled
    )


def _with_membership(persona: str, role: ProjectRole) -> AuthzContext:
    """The persona, plus an explicit `role` membership on PROJ."""
    return replace(PERSONAS[persona], projects={PROJ: ProjectAccess(role, ORG, WS)})


LIVE = task_target()
ARCHIVED = task_target(archived=True)
EC = task_target(export_controlled=True)


# --- Who may, on a live project -----------------------------------------------------------------


@pytest.mark.parametrize("action", READS)
@pytest.mark.parametrize(("persona", "allowed"), rows(SEES_THE_PROJECT))
def test_the_reads_are_for_viewers_and_up_and_inherited_admins(
    persona: str, allowed: bool, action: str
) -> None:
    assert authorize(PERSONAS[persona], action, LIVE) is allowed


@pytest.mark.parametrize("action", MEMBER_ACTIONS)
@pytest.mark.parametrize(("persona", "allowed"), rows(MEMBERS_AND_UP))
def test_the_member_actions_are_for_members_and_up(
    persona: str, allowed: bool, action: str
) -> None:
    """§5 member: create and edit tasks, subtasks; manage phases, workstreams; §3.1: members
    raise an item's restriction."""
    assert authorize(PERSONAS[persona], action, LIVE) is allowed


@pytest.mark.parametrize("action", ADMIN_ACTIONS)
@pytest.mark.parametrize(("persona", "allowed"), rows(PROJECT_ADMINS))
def test_the_admin_actions_are_for_project_admins(persona: str, allowed: bool, action: str) -> None:
    """DL-211 (reassigning the reporter), §3.1 (lowering), §5 Deletion (someone else's task)."""
    assert authorize(PERSONAS[persona], action, LIVE) is allowed


@pytest.mark.parametrize("action", ALL)
def test_a_project_role_grants_them_only_on_its_own_project(action: str) -> None:
    """The admin of PROJ2 (same org) may on PROJ2, not on PROJ."""
    other = PERSONAS["other_project_admin"]

    assert authorize(other, action, task_target(project=PROJ2)) is True
    assert authorize(other, action, LIVE) is False


# --- The reporter's delete and restore (DL-219, DL-223) -----------------------------------------


@pytest.mark.parametrize("action", DELETE_AND_RESTORE)
@pytest.mark.parametrize(("persona", "allowed"), rows(MEMBERS_AND_UP))
def test_the_reporter_may_delete_and_restore_as_a_project_member(
    persona: str, allowed: bool, action: str
) -> None:
    """A member reporter may; a viewer reporter may not (DL-219); admins may anyway."""
    assert authorize(PERSONAS[persona], action, own(persona)) is allowed


@pytest.mark.parametrize("action", DELETE_AND_RESTORE)
def test_a_member_may_not_delete_or_restore_someone_elses_task(action: str) -> None:
    assert authorize(PERSONAS["project_member"], action, task_target(SOMEONE_ELSE)) is False


@pytest.mark.parametrize("action", DELETE_AND_RESTORE)
def test_the_reporter_without_access_to_the_project_may_not(action: str) -> None:
    """The reporter now only on PROJ2 can't see PROJ: denied, a 404 (DL-219)."""
    reporter = PERSONAS["other_project_admin"]
    target = task_target(reporter.user_id)

    assert authorize(reporter, action, target) is False
    with pytest.raises(NotFoundError):
        ensure(reporter, action, target)


@pytest.mark.parametrize("action", DELETE_AND_RESTORE)
def test_a_viewer_reporter_gets_403(action: str) -> None:
    with pytest.raises(ForbiddenError):
        ensure(PERSONAS["project_viewer"], action, own("project_viewer"))


@pytest.mark.parametrize("action", DELETE_AND_RESTORE)
def test_the_reporter_may_on_an_export_controlled_project_as_an_explicit_member(
    action: str,
) -> None:
    assert (
        authorize(PERSONAS["project_member"], action, own("project_member", export_controlled=True))
        is True
    )


@pytest.mark.parametrize("action", DELETE_AND_RESTORE)
def test_the_reporter_may_not_in_an_archived_project(action: str) -> None:
    assert (
        authorize(PERSONAS["project_member"], action, own("project_member", archived=True)) is False
    )


# --- An archived project: reads stay, mutations denied (§5 step 1) ------------------------------


@pytest.mark.parametrize("action", READS)
@pytest.mark.parametrize(("persona", "allowed"), rows(SEES_THE_PROJECT))
def test_the_reads_still_work_in_an_archived_project(
    persona: str, allowed: bool, action: str
) -> None:
    assert authorize(PERSONAS[persona], action, ARCHIVED) is allowed


@pytest.mark.parametrize("action", MUTATIONS)
@pytest.mark.parametrize(("persona", "allowed"), rows(set()))
def test_an_archived_project_denies_every_mutation_to_everyone(
    persona: str, allowed: bool, action: str
) -> None:
    assert authorize(PERSONAS[persona], action, ARCHIVED) is allowed


# --- Export control (§3.1; §5 step 2; DL-82) ----------------------------------------------------


@pytest.mark.parametrize("action", ALL)
@pytest.mark.parametrize("persona", sorted(INHERITED_ADMINS))
def test_an_inherited_admin_without_a_membership_is_denied_every_one_on_an_ec_project(
    persona: str, action: str
) -> None:
    assert authorize(PERSONAS[persona], action, EC) is False


@pytest.mark.parametrize("action", ALL)
@pytest.mark.parametrize("persona", sorted(INHERITED_ADMINS))
def test_that_denial_is_a_404(persona: str, action: str) -> None:
    with pytest.raises(NotFoundError):
        ensure(PERSONAS[persona], action, EC)


@pytest.mark.parametrize("action", READS)
@pytest.mark.parametrize(("persona", "allowed"), rows(EXPLICIT))
def test_on_an_ec_project_the_reads_are_for_explicit_members(
    persona: str, allowed: bool, action: str
) -> None:
    assert authorize(PERSONAS[persona], action, EC) is allowed


@pytest.mark.parametrize("action", MEMBER_ACTIONS)
@pytest.mark.parametrize(("persona", "allowed"), rows({"project_admin", "project_member"}))
def test_on_an_ec_project_the_member_actions_are_for_explicit_members_and_up(
    persona: str, allowed: bool, action: str
) -> None:
    assert authorize(PERSONAS[persona], action, EC) is allowed


@pytest.mark.parametrize("action", ADMIN_ACTIONS)
@pytest.mark.parametrize(("persona", "allowed"), rows({"project_admin"}))
def test_on_an_ec_project_the_admin_actions_are_for_explicit_admins(
    persona: str, allowed: bool, action: str
) -> None:
    assert authorize(PERSONAS[persona], action, EC) is allowed


@pytest.mark.parametrize("persona", sorted(INHERITED_ADMINS))
def test_an_inherited_admin_with_a_membership_raises_but_may_not_lower_on_an_ec_project(
    persona: str,
) -> None:
    """§3.1: lowering on an export-controlled project needs an explicit project admin (DL-82)."""
    ctx = _with_membership(persona, ProjectRole.MEMBER)

    assert authorize(ctx, "task.raise_restriction", EC) is True
    assert authorize(ctx, "task.lower_restriction", EC) is False


@pytest.mark.parametrize("persona", sorted(INHERITED_ADMINS))
def test_an_inherited_admin_with_a_membership_lowers_on_a_project_not_ec(persona: str) -> None:
    ctx = _with_membership(persona, ProjectRole.MEMBER)

    assert authorize(ctx, "task.lower_restriction", LIVE) is True


# --- ensure(): 403 to who sees the project, 404 to who can't -------------------------------------


@pytest.mark.parametrize("action", ALL)
@pytest.mark.parametrize("persona", UNSEEN)
def test_every_one_is_404_to_who_cannot_see_the_project(persona: str, action: str) -> None:
    with pytest.raises(NotFoundError):
        ensure(PERSONAS[persona], action, LIVE)


@pytest.mark.parametrize("action", MUTATIONS)
def test_a_viewer_gets_403_for_the_mutations(action: str) -> None:
    with pytest.raises(ForbiddenError):
        ensure(PERSONAS["project_viewer"], action, LIVE)


@pytest.mark.parametrize("action", ADMIN_ACTIONS)
def test_a_member_gets_403_for_the_admin_actions(action: str) -> None:
    with pytest.raises(ForbiddenError):
        ensure(PERSONAS["project_member"], action, LIVE)


@pytest.mark.parametrize("action", READS)
@pytest.mark.parametrize("persona", sorted(SEES_THE_PROJECT))
def test_ensure_lets_who_sees_the_project_read(persona: str, action: str) -> None:
    assert ensure(PERSONAS[persona], action, LIVE) is None
