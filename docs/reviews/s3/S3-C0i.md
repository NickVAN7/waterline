# Review record: S3-C0i — Backlog widget spike

- **Checkpoint:** Slice 3, Checkpoint 0i (group `s3-polish`; PR #12)
- **Base commit:** `6ee2e5e` (DC-2026-11-12d, the last commit before the checkpoint; DL-17)
- **Reviewers:** `checkpoint-reviewer` alone: the diff is a spike folder under `docs/spikes/` and
  two doc edits, no `frontend/src/` or `frontend/e2e/` (no `ui-reviewer`, DL-62) and nothing
  security-relevant (no `security-reviewer`).
- **Totals:** checkpoint-reviewer ready after fixes, 2 minor, 1 question. 1 fixed, 1 logged
  (TD-113); 0 rejected.
- **Gates at close:** `wl check` green; CI on the commit.

---

## Before the reviewer

The spike, `docs/spikes/S3-C0i-backlog/`, measures DL-344's checklist on SVAR DataGrid and
PrimeVue DataTable (`results.md`, `results.json`, four screenshots), with a runnable demo for the
owner. On the way, the implementing session's own runs found and fixed three spike errors before
the numbers were kept: the owner's PrimeUI key wasn't read (a license notice); SVAR's stylesheet
wasn't imported (the grid unstyled, its drag off target), which the S2-C0b spike missed too; and
a wrapper class named `fixed` collided with Tailwind's `position: fixed`.

## checkpoint-reviewer, pass 1 (base `6ee2e5e`)

Verdict: ready after fixes.

| # | Severity | Rule | Finding | Resolution |
|---|---|---|---|---|
| 1 | minor | docs | For the recommended option, `measure.mjs` pressed Tab once, which lands on the virtual scroller's container, so `results.json` recorded no row reached by the arrows; its tab-stop count looked only inside the table (1, against the table's 2). | **Fixed:** a second Tab when the first stop isn't a row, the tab stops counted across the widget's root, the measurements rerun (now 2, and the arrows move between rows); the Shift+Tab finding marked as checked by hand. |
| 2 | minor | docs | UI-SVR-3 doesn't say a SVAR widget's own stylesheet must be imported, or that Willow's icons go blank under `:fonts="false"`; S2-C0b's results don't say their SVAR numbers were unstyled. | **Logged** as TD-113, Fix by S3-C18 (the first SVAR wrapper): a rule change is outside a spike. S2-C0b's `results.md` gains a note pointing here. |

**Sabotage checks:** none: the checkpoint adds no app behavior a test could catch (a spike, no
product code). The reviewer instead reran the claims that drive the choice against the running
demo: SVAR's Space dropping focus to `<body>` (Enter and the modified arrows don't), and
DataTable's two tab stops, arrows, and Shift+Tab under the virtual scroller. Both confirmed.

**Question:** the build plan says the spike's result is a decision-log entry deciding S3-C19 and
UI-SVR-2's backlog line; does it come in its own commit once the owner chooses? **Answer:** yes.
DL-344 has the owner see both before choosing, so the entry follows the owner's choice as a
`docs:` design change (it changes S3-C19's row and UI-SVR-2, not this checkpoint's own; DL-362).

## Owner decisions and open questions

Made during the checkpoint: none.

Open for the owner: the backlog's widget, SVAR DataGrid or PrimeVue DataTable (DL-344),
after trying both (`results.md`, "See it yourself"); recommended: DataTable with row reorder and
its virtual scroller.
