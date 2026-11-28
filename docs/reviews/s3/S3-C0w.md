# Review record: S3-C0w — The two large services split

- **Checkpoint:** Slice 3, Checkpoint 0w (group `s3-polish`; the handoff's Package 5 item 4, its
  service splits only, DL-406)
- **Base commit:** `6214350` (S3-C0v's checkpoint, the last commit before this one; DL-17)
- **Reviewers:** `checkpoint-reviewer` and `security-reviewer` (the build plan names S3-C0w), in
  parallel on one snapshot (DL-105, DL-392). No `ui-reviewer`: no frontend change. No re-review:
  the major finding's fix is a test, the others comments and docs (the `checkpoint` skill, step 5).
- **Totals:** checkpoint-reviewer ready after fixes, 1 major and 2 minor, all fixed;
  security-reviewer ready, no findings, 3 notes passed to the general review, fixed with finding 2.
- **Gates at close:** `wl check` green, mutation testing included; CI's `wl check --full` on the
  pushed commit.

---

## Before the reviewers

- **The split:** each new module is a subclass of the service it came from, so the moved methods
  are unchanged and keep the parent's locks and logging: `ProjectMemberService`
  (`services/project_members.py`: the members list, the pickers, adds and the org add's projects
  step, role changes, removals, the member-removed handler; `project.py` 960 lines to 605) and
  `RequirementApprovalService` (`services/requirement_approvals.py`: request, decide, approve by
  hand, cancel, read, the approved and rejected handlers; `requirement.py` 1,148 to 850). Their
  layers: `project_members` beside `task`, `requirement_approvals` above `requirement`; both in
  `wiring.py`.
- **Renamed to import:** `_confirmation` and `_CONFIRMED`, shared by the members code and
  `set_restriction`, are `export_control_confirmation` and `EXPORT_CONTROL_CONFIRMED` (strict
  pyright refuses a private name across modules).
- **Drift fix (DL-362):** the row moved S3-C0v's person check into `requirement_approvals.py`;
  `RequirementService.update`'s reporter check uses it, and the base class can't import from its
  subclass under the layers, so it stays in `requirement.py`. The row now says so.
- **Callers:** the routers, `deps.py`, `demo.py`, and six concurrency test files call the new
  classes; the tests changed in their imports and the class they build only. 7,600 backend tests
  pass.

## checkpoint-reviewer, pass 1

**Verdict:** ready after fixes. The move compared line by line, whitespace ignored: only the
docstrings, imports, class lines, the two renames, the handlers building the subclass, and line
wrapping differ.

| # | Severity | Finding | Resolution |
|---|---|---|---|
| 1 | major · tests | No test checks that an org add with projects refuses a project archived while it waited (S3-C0m's code): with the re-check under the lock in `_lock_projects_for_org_add` removed, all 2,783 API and integration tests passed; the single-project add has its race test, the org add none. | **Fixed:** `test_an_org_add_with_projects_waiting_on_an_archive_adds_nothing` (`test_restriction_concurrency.py`): the archive first, the org add second, a 403, no project member, no org membership. The session's sabotage (the re-check removed) fails it. Siblings: the single-project add's archive race (`test_a_member_add_waiting_on_an_archive_is_denied`) exists; no other add path locks projects. |
| 2 | minor · lean | Comments left in the wrong place by the move: `project_members.py`'s "The entity a project endpoint loads…" over an unrelated import; `requirement.py`'s "A requirement's approval requests…" over `_categories`; `requirement.py`'s empty "Approval requests" section header; `project.py`'s "Members" header over `access_review` alone. | **Fixed:** the first and third deleted; the second moved above `APPROVAL_REQUESTS` in `requirement_approvals.py`; the fourth renamed "Access review". With them, security-reviewer's note: `register_on_approved` called twice in `requirement_approvals.py` (harmless, a dict), once now. |
| 3 | minor · docs | The developer guide names `_confirmation(…)`, and TD-100 `RequirementService.approval_requests`. | **Fixed:** `export_control_confirmation` and `RequirementApprovalService.approval_requests`. Siblings: a grep of the docs for the moved and renamed names finds no other. |

### Sabotage checks

| Behavior | Change made (in its copy) | Caught by |
|---|---|---|
| The member-removed handler registers in every process | `project_members` removed from `wiring.py` | `test_importing_it_alone_fills_every_handler_registry[app.services.wiring]`, `[app.jobs.worker]` |
| A rejected re-open round's handler still registers from the new module | `register_on_rejected(…)` deleted | 3 in `test_approval_decisions.py`, and the 4 wiring cases |
| An org add refuses a project archived under the lock | The `archived_at` re-check removed | none: finding 1 (now the new race test) |

**Question raised:** whether the owner approved the row's new wording on `_check_person`. Answer:
it's a drift fix inside the row's scope, recorded above; nothing else was possible under the
layers.

## security-reviewer, pass 1

**Verdict:** ready. No findings, no questions. Compared every removed block with the new modules:
the same line for line but the two renames, every call site updated. The locks and checks in the
same order (members: `_lock_live`, DL-78's add order, the 404 outside the org; org adds: the
duplicate check, a 404 before any lock, `ensure` per project, `lock_all`, the archived re-check,
the confirmation under the lock; approvals: `decide`'s project, requirement, request holds, the
reloaded context, then `ensure`). No subclass method shadows the parent's. The handlers still
register (the wiring test). 6,156 tests marked `security` passed in its copy. Its notes for the
general review: the duplicate registration and two stray comments (finding 2).

## Open questions for the owner

None.
