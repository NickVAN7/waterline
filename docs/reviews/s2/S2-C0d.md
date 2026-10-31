# Review record: S2-C0d — Restriction, export control, modules

- **Checkpoint:** Slice 2, Checkpoint 0d (group `s2-prep`; PR #11)
- **Base commit:** `cc586ab` (S2-C0c's commit)
- **Reviewers:** `security-reviewer`, then `checkpoint-reviewer`, then `ui-reviewer`, on one
  snapshot (DL-105).
- **Totals:** `security-reviewer`: no findings. `checkpoint-reviewer`: 1 finding (minor), fixed;
  2 questions for the owner. `ui-reviewer`: 1 finding (major), fixed, and 2 notes, no change (the
  second a question for the owner); 3 coverage gaps, 2 closed. `ui-reviewer` pass 2 (the fix
  diff): 1 note, fixed.
- **Gates at close:** `uv run wl check` green (4,381 backend tests, 412 of 412 mutants killed,
  759 frontend tests); CI on the checkpoint commit.

---

## Spec tests

`spec-test-writer` ran at the start of the checkpoint, against stubs: `rules/restriction.py`
(`effective()` always `Restriction()`, `change()` always neither) and `rules/modules.py`
(`seed_modules` always every module), each flipped to the opposite fixed answer and restored.
The authorization policy changes only its names (DL-134), so `app/authz/` wasn't stubbed: its
spec tests changed only the names, and passed against the renamed policy. **DL-134 is the owner's
approval of the spec-test changes the rename needs** (removing the `restricted` cases and
re-expressing them with the remaining levels). DL-136 replaces the old
`test_a_new_project_is_seeded_with_its_types_v1_defaults_only`, where software seeded `sprints`
and `github`.

A second run (same agent): mutation testing left two survivors in `seed_modules`, since nothing
has shipped, so no test reached a shipped default. The agent added the positive case (`github`
shipped through a patched `_SHIPPED`), shown to fail against both mutants.

### Behavior table

| # | Behavior | Source | Test | Fails against |
|---|---|---|---|---|
| 1 | Effective level is the stricter of the two; None with None is None; None with Internal is Internal (9 level pairs) | §3.1 "Effective restriction" | `test_the_effective_level_is_the_stricter_of_the_two` | Stub (`Restriction()`): 8 rows. Flip (Confidential): the rows that don't expect Confidential |
| 2 | Effective categories are the union | §3.1 | `test_the_effective_categories_are_the_union_of_both` | Stub: rows 1–5. Flip: every row |
| 3 | None with Internal is Internal, with both categories, in both orders | §3.1 (owner, Oct 12) | `test_none_with_internal_is_internal_with_both_categories` | Both answers |
| 4 | An item never goes below its project's restriction | §3.1 | `test_an_item_cannot_go_below_its_projects_restriction` | Both answers |
| 5 | Property: effective is never lower than the project and keeps its categories | testing strategy | `test_effective_is_never_lower_...` | Stub |
| 6 | Property: exactly the stricter level and exactly the union | §3.1 | `test_effective_is_exactly_the_stricter_level_...` | Both answers |
| 7 | A higher level raises, a lower lowers; None to Internal and the same level are neither | §3.1, DL-82 | `test_a_level_change_raises_or_lowers_by_rank` | Stub: raise and lower rows. Flip: every row |
| 8 | An added category raises, a removed one lowers, a swap does both, the same set is neither | §3.1, DL-82 | `test_a_category_change_raises_when_added_...` | Stub: rows 0–6. Flip: every row but the swap |
| 9 | Level and category changes combine (re-expressed without Restricted) | build plan, "The classification API" | `test_level_and_category_changes_combine` | Stub: every row. Flip: rows 2–5 |
| 10 | Property: raises and lowers exactly by rank and categories, None ranking as Internal | DL-82 | `test_change_raises_and_lowers_exactly_...` | Both answers |
| 11 | Nothing has shipped, so every type seeds no modules | §1.1, DL-136 | `test_a_new_project_is_seeded_with_its_types_shipped_defaults_only` | Stub (`list(ProjectModule)`) |
| 12 | Recommended still lists the defaults, v2 included | §1.1 | `test_each_type_recommends_its_default_modules_v2_included` | Not stubbed (already built) |
| 13 | No module is available yet | §1.1, DL-136 | `test_no_module_is_available_yet` | Not stubbed (already built) |
| 14 | Authorization and API: the action and endpoint renames only | DL-134 | the authz files below | Not flip-tested (authz not stubbed) |
| 15 | With `github` shipped and `sprints` not, software seeds exactly `[github]` | §1.1, DL-136 | `test_a_new_project_is_seeded_with_its_types_defaults_that_have_shipped[software]` | `ProjectModule(m)` → `ProjectModule(None)`; `is_available(m)` → `is_available(None)` |
| 16 | With `github` shipped, erp and general still seed `[]` | §1.1, DL-136 | the same test, `[erp]`, `[general]` | Not run against an edit |
| 17 | A shipped module is available | §1.1, DL-136 | `test_a_shipped_module_is_available` | Not run against an edit |

### Files

| File | New / extended | git hash-object |
|---|---|---|
| `backend/tests/unit/rules/test_restriction.py` | Extended (was `test_classification.py`) | `051dc8e5aaeea6cc6aa08fe868c5eb574dde1858` |
| `backend/tests/unit/rules/test_modules.py` | Extended | `1b305f13d80000dc87fa5f2a318b189fd9f9c44a` |
| `backend/tests/unit/authz/test_restriction_actions.py` | Extended (was `test_classification_actions.py`) | `6d7023b315dcca41176aac521f9309686a909f8f` |
| `backend/tests/api/authz/test_restriction.py` | Extended (was `test_classification.py`) | `895c51c7d837412c30454e9299b492a27d901058` |
| `backend/tests/unit/authz/test_actions.py` | Extended (names) | `2468bbc9b1bd89a628136087313623d8ae0ccf88` |
| `backend/tests/unit/authz/test_authorize.py` | Extended (names) | `3434a626b871d6e96ad8023d40d909a26b8bf4c8` |
| `backend/tests/unit/authz/test_project_actions.py` | Extended (names) | `609eee20ebd36d201e50535d92269ff72cf1abbf` |
| `backend/tests/api/authz/test_projects.py` | Extended (names) | `facdfd3e5e4ff7533aa3b177e816719d525f8f75` |

The spec tests' docstrings cite the build plan's sections by their Slice 1 names ("Classification
& export control", "The classification API", "The classification actions"), which the build plan
keeps as built in Slice 1.

## Outside the row's scope, and why

- `ExportControlDialog` (and its spec) is deleted, with the create dialog's and settings' flows
  that marked or removed export control and their refusal handling for `members_changed`: once
  the UI doesn't offer export control (DL-133), nothing can open them. The members page's
  confirmation, and `useFormErrors`' `refetchNeeded`, stay.
- The sidebar's "Not available yet" entries for an enabled unshipped module are gone: no project
  can hold one now (DL-136's migration and the 422), and UI-SHL-6 lists a module page only once
  it has shipped and is enabled.
- `design-doc.md`'s review summary (§0, item 6) said "data classification": a drift fix inside
  DL-134's rename.

---

## security-reviewer, pass 1 (base `cc586ab`) — verdict: ready

No findings. Its question, for the correctness reviewer: the old `audit_event` rows keep
`classification_level` and `classification_categories` in `details`, since DL-134 rewrites only
the action ("dev data only"). Nothing reads those keys yet. Recorded here; no change.

## checkpoint-reviewer, pass 1 (base `cc586ab`) — verdict: ready

| # | Severity | Finding | Resolution |
|---|---|---|---|
| 1 | minor | **"Not available yet" is read twice for an unshipped module** (`ModuleFields.vue`): the text is in the checkbox's label, so its name, and `aria-describedby` pointed at it again. Fix: drop the `-unavailable` id from the description, and the specs' assertions of it. | **Fixed:** the description is only the turned-off warning; the specs assert the reason is in the box's label and that there's no description. Siblings: no other control's description repeats its label (grepped `aria-describedby` in the diff). |

**Sabotage checks** (in a throwaway copy of the snapshot):

| Behavior | Source | Change made | Caught by |
|---|---|---|---|
| PATCH refuses enabling an unshipped module (422 `module_unavailable`, nothing changed, no event) | DL-136 | `_enabled(...)` in the update path → a plain dedupe | `test_an_update_enabling_an_unshipped_module_is_refused` |
| The migration turns `audit_event`'s append-only trigger back on | DL-134; schema-doc `audit_event` | Deleted the `ENABLE TRIGGER` line | `test_the_upgrade_leaves_audit_event_append_only` |
| Settings keeps an `export_controlled` it doesn't show | DL-133 | `fillRestriction` filtered it out | `offers no export control, and keeps the one it doesn't show (DL-133)`; `sends a level change without asking, …` |

**Questions** (open, below): the per-person access review's Access column; the error type for a
v2 module.

## ui-reviewer, pass 1 (base `cc586ab`) — verdict: pass with findings

| # | Severity | Finding | Resolution |
|---|---|---|---|
| 1 | major | **After an export-control refusal, the restriction form can't be saved until the page is reloaded** (`ProjectSettingsView.vue`, `saveRestriction`; `useSettingsSave`): the form holds `export_controlled` without showing it. A project loaded export-controlled and changed elsewhere is refused with `confirmation_required`; the reload keeps what was typed, the hidden category included, so every save after fails the same way, and the alert asks for a confirmation the form doesn't offer (UI-FRM-7, UI-FBK-3). Fix: send `export_controlled` from the project as last read, never from the form; our own words for that refusal; a spec that saves a second time. | **Fixed:** `saveRestriction` builds the categories from the form's, without `export_controlled`, plus it when the project as last read has it; `exportControlChanged` replaces the server's words on `export_control_confirmed` with "This project's export control changed since you opened it. It has been read again: save again."; the DL-116 spec saves again after the reload and succeeds. Sabotage check (main session's, evidence only): sending the form's categories fails three specs. Rule added to `frontend/CLAUDE.md` (UI). Siblings: the create dialog starts with no categories and never holds a hidden one; the members page reads export control from the loaded project. |
| 2 | note | An unavailable module's checkbox has the browser's disabled look (UI-TOK-10 allows the native `disabled`; the app's checkboxes are all native). | No change; for the manual pass. |
| 3 | note | The restriction badge has no context word for screen readers ("Internal" read alone), as UI-FBK-6 and DL-137 specify. | No change; a question for the owner, below. |

**Coverage gaps it named:** the second save after the DL-116 reload (closed with finding 1); the
badge's icon (closed: `RestrictionBadge.spec.ts` checks each tone's icon path); no e2e test of
Settings (left: the Vitest spec runs axe on it).

**Needs the manual pass** (S2-C22): the disabled checkboxes in both themes and forced colors,
and a screen reader in browse mode; the header's badges at 320 px and 400% zoom; the access
review without its Access column.

## ui-reviewer, pass 2 (the fix diff, `reviewed-1` to `reviewed-2`) — verdict: pass

Finding 1's fix checked and holds: the next save after the DL-116 reload sends what the server
has. (Its report said notes 2 and 3 were left "as the owner decided": the owner hasn't decided
them; they stay open below.)

| # | Severity | Finding | Resolution |
|---|---|---|---|
| 1 | note | **`exportControlChanged` rewrote the message whatever the refusal's type, and dropped any `details` but `fields`**: only `confirmation_required` can come back today. Fix: match that type, as `refetchNeeded` does, and keep `details`. | **Fixed** (second pass, no third): it matches `confirmation_required` on `export_control_confirmed` and spreads `error.details`. Siblings: none; the one rewrite of a server message. |

**Needs the manual pass** (S2-C22): the refusal's alert read once with focus on it; an
unavailable module read as one name plus "dimmed", nothing twice.

---

## Open questions for the owner

1. **The per-person access review's Access column** (`checkpoint-reviewer`). DL-133 says "the
   access review's Access column shows only on an export-controlled project"; S2-C0d applied it
   to the per-project review. The per-person review (`AccessReviewView.vue`) still shows Access on
   every project row. Options: hide it on each row that isn't export-controlled (recommended:
   those rows all say "Content and management", which tells the reader nothing), or keep it.
2. **The error type for a v2 module** (`checkpoint-reviewer`). Design-doc §1.1 says an unshipped
   module is refused with `module_unavailable`, "v1 and v2 modules alike"; a v2 module (`raid`)
   is still refused with type `enum` at `["body", "enabled_modules", 0]`, since it isn't a
   `ProjectModule` value until its slice ships. Options: keep `enum` (recommended: the request is
   refused either way, and the alternative adds every v2 value to the API's enum early), or add
   the v2 values so they reach the `module_unavailable` check.
3. **A context word on the restriction badge** (`ui-reviewer`, note 3). "Internal" read alone is
   ambiguous; UI-FBK-6 and DL-137 specify only the level and categories. Options: a visually
   hidden "Restriction: " prefix (recommended: small, and clearer to screen-reader users), or none.
