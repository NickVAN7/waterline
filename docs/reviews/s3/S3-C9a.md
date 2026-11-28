# Review record: S3-C9a — A requirement's linked tasks on its delete

- **Base commit:** `f00e358` (S3-C9)
- **Reviewers:** `checkpoint-reviewer`, `security-reviewer` (the build plan: every row from S3-C1
  to S3-C15), `ui-reviewer` (the diff touches `frontend/src/`: the generated client and the
  requirement fixture), on one snapshot (DL-105).

## Decisions during the checkpoint

- **The owner's three answers** (Nov 25, 2026, before building; DL-413, design-doc §9): the
  unlink logged on both sides; `can_delete_tasks` over the whole subtree's linked tasks; a task in
  the trash keeps its link, and a restored one keeps it (S3-C9's open question).
- **No spec tests:** the row adds no action and changes nothing in `app/rules/` or `app/authz/`
  (the build plan's `spec-test-writer` list doesn't name it); the tasks' delete is `task.delete`,
  checked on each task. The indirect-delete threat's tests are the main session's, marked
  `security`.
- **The task area owns the write:** `TaskService.leave_requirements()` locks the live tasks
  linked to the requirements being deleted (ID order), checks `task.delete` on each before any
  change (403), then deletes them at the requirement's `deleted_at` or detaches them, logging
  the task's side; it returns the detached pairs, and the requirement service logs its side. It
  runs before the promotion and the `deleted_at` writes.
- **Lock order, requirement before task:** the delete holds the requirements (already locked by
  the tree's delete), then their tasks. A task edit used to lock its row before holding the
  requirement it links to, which could deadlock with a delete of that requirement; it now holds
  the requirement first (`TaskService.update`; S3-C6's code, in this row's scope as the delete's
  lock order needs it). The race test reproduces the deadlock with the old order.
- **The wiring test's handler order:** the requirement service now imports the task service, so
  `_lift_tasks` registers before `_lift_requirements`; each lifts its own table, so the order is
  incidental and the test's expected list was updated.
- **A shallow S3-C9 test fixed:** `TaskFactory` ignores `reporter_id=` (it sets `reporter`), so
  S3-C9's `test_a_reporters_delete_waiting_on_a_reporter_change_is_refused` never made Ann the
  reporter and passed without the race; it now passes `reporter=ann` (sabotage: the service's
  recheck removed, it fails).

## Tests

| # | Behavior | Source | Test |
|---|---|---|---|
| 1 | Detach is the default; each unlink logged on the task and the requirement | §9, DL-413 | `test_detach_is_the_default_and_logs_each_unlink_on_both_sides` |
| 2 | The children's tasks detached only when the children are deleted | DL-224 | `test_the_childrens_tasks_are_detached_only_when_the_children_are_deleted` |
| 3 | A task in the trash keeps its link | DL-413 | `test_a_task_in_the_trash_keeps_its_link` |
| 4 | Restoring the requirement re-links nothing | §9 | `test_restoring_the_requirement_re_links_nothing` |
| 5 | `tasks=delete` deletes them at the requirement's moment, logged, in the trash | §9 | `test_deleting_the_tasks_too_deletes_them_at_the_requirements_moment` |
| 6 | Restoring the requirement leaves its deleted tasks in the trash | §9 | `test_restoring_the_requirement_leaves_its_deleted_tasks_in_the_trash` |
| 7 | Deleting a task you couldn't delete directly: 403, nothing changed (security) | §9, threat model | `test_deleting_a_task_you_couldnt_delete_directly_is_403_and_nothing_changes` |
| 8 | Detaching a task you couldn't delete is allowed (security) | §9 | `test_detaching_a_task_you_couldnt_delete_is_allowed` |
| 9 | An unknown `tasks` choice is a 422 | contract | `test_an_unknown_tasks_choice_is_a_422` |
| 10 | `can_delete_tasks` over the requirement's and a descendant's tasks (security) | §9, DL-413 | `test_the_read_says_whether_the_linked_tasks_can_be_deleted_with_it` |
| 11 | No `can_delete_tasks` for who may not delete the requirement | §9 | `test_who_may_not_delete_the_requirement_may_not_delete_its_tasks` |
| 12 | A delete waiting on a link detaches the newly linked task | §9 | `test_a_requirement_deleted_while_a_task_links_to_it_detaches_the_task` |
| 13 | A link queued behind a requirement delete doesn't deadlock with it | backend/CLAUDE.md, locks | `test_a_link_queued_behind_a_requirement_delete_does_not_deadlock_with_it` |

Files: `backend/tests/api/test_requirement_linked_tasks.py` (1–11),
`backend/tests/integration/services/test_task_concurrency.py` (12–13).

Main-session sabotage, each restored after: the task-delete check in `leave_requirements` off
(7 fails); the requirement-side unlink log removed (1 fails); `can_delete_tasks` over the
requirement alone (10's descendant case fails); the update's requirement hold back after the
task's lock (13 fails: a deadlock, `OperationalError`). Removing the update's hold altogether
doesn't fail 12: the link's foreign-key check also makes the delete wait, so 12 checks the
outcome, and 13 the lock order.

## Pass 1 (snapshot `reviewed-1`)

Totals: 7 findings (checkpoint 7, security 0, UI 0) plus one UI note: 5 fixed, 2 logged (TD-134,
and the note as TD-135), 0 rejected. No re-review: the major findings' fixes are tests only
(DL-105).

### checkpoint-reviewer: ready after fixes

| # | Severity | Area | Finding | Resolution |
|---|---|---|---|---|
| 1 | major | tests | `leave_requirements`' check over the subtree's tasks had no test: limited to the root's tasks, 3,455 tests passed, so a member could delete a colleague's task linked to their requirement's child (§9's indirect delete) | **Fixed:** test 7 parametrized over Bob's task on RQ-1 or its child (`children=delete&tasks=delete`); the reviewer's sabotage rerun in the main session: the child case fails |
| 2 | major | tests | No test that each requirement-side unlink lands on the requirement the task was linked to: logged on the root, the suite stayed green | **Fixed:** `test_each_unlink_is_logged_on_the_requirement_the_task_was_linked_to`; the reviewer's sabotage rerun: it fails |
| 3 | major | tests | `test_the_read_says_whether_the_linked_tasks_can_be_deleted_with_it` held an `if` | **Fixed:** the no-task case is its own test (`test_a_requirement_with_no_tasks_may_be_deleted_with_them`); the rest parametrized by the requirement's number. The race test's setup loop stays (orchestration only) |
| 4 | minor | docs | History shows an `unlinked` entry as "made a change", naming no task, and no TD says so | **Logged:** TD-134, Fix by S3-C12 (with TD-132) |
| 5 | minor | docs | The behavior reference's Delete… paragraph doesn't say linked tasks are unlinked | **Fixed:** one sentence, pointing to TD-135 |
| 6 | minor | docs | The build plan's cross-area write example names the task service's per-task delete | **Fixed:** names `leave_requirements`, which checks each task's own delete |
| 7 | minor | docs | The root `CLAUDE.md` Status not updated | **Fixed:** S3-C9a done; next S3-C10 |

Sabotage checks:

| Behavior | Source | Change made (in the copy) | Tests run | Caught by |
|---|---|---|---|---|
| Each requirement-side unlink on the requirement the task was linked to | DL-413, §9 | `by_id[requirement_id]` → the root | full backend suite | **none** → finding 2 |
| `tasks=delete` checks `task.delete` on each task | §9, threat model | `TASK_DELETE` → `TASK_UPDATE` | the linked-tasks and task concurrency files | `test_deleting_a_task_you_couldnt_delete_directly_is_403_and_nothing_changes` |
| `tasks=delete` checks the subtree's tasks | §9, DL-221 | the check limited to the root's tasks | `tests/api`, `tests/integration` | **none** → finding 1 |

### security-reviewer: ready

No findings.

### ui-reviewer: pass

| # | Severity | Rule | Finding | Resolution |
|---|---|---|---|---|
| N1 | note | — | No row builds the delete dialog's linked-tasks choice; the dialog sends no `tasks` and doesn't mention tasks; the read has no `has_tasks` | **Logged:** TD-135, Fix by S3-C25 (Requirement ↔ tasks) |

## Open for the owner

None.

## Owner decisions during the checkpoint

- DL-413 (Nov 25, 2026, before building): the three answers above.
