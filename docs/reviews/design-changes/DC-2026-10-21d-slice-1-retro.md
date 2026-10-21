# Review record: DC-2026-10-21d — the Slice 1 retro's decisions

- **Change:** docs only. These are the owner's decisions at the S1-C17 review and the Slice 1 retro
  (`docs/reviews/s1/S1-retro.md`): DL-124 to DL-131.
  - **DL-124:** S2-C0, a pre-checkpoint at Slice 2's start. It covers TD-56 to TD-60 and TD-62,
    the two missed scheduled items, and the owner's `ui-feedback.md`.
  - **DL-125:** the review-tier trial's verdict, "not exercised", with the S1-C8/S1-C9 exception
    removed.
  - **DL-126:** every design change gets a review record.
  - **DL-127 to DL-131:** the retro's five adopted proposals:
    - DL-127: try-it scripts are checked against the owner's dev stack;
    - DL-128: a fix lists the siblings it checked;
    - DL-129: a new dependency names its license;
    - DL-130: owner decisions are explained in the report, and none is left out;
    - DL-131: small follow-ups to built code are bundled.

  It also ticks the build plan's last "Done when" item, "CI is green": CI passed on S1-C17's
  commit `a56aed5`.
- **Base commit:** `a56aed5`
- **Files:** `docs/decision-log.md`, `docs/build-plan.md`, `docs/developer-guide.md`, `CLAUDE.md`,
  `.claude/skills/checkpoint/SKILL.md`, `.claude/skills/design-change/SKILL.md`
- **Reviewers:** `docs-consistency` (trigger `design-change`). There's no tooling code, so
  `checkpoint-reviewer` doesn't run (DL-18).
- **Totals:** 8 fixes, all applied; 3 decisions for the owner.
- **Gates:** `uv run wl check` green.

---

## docs-consistency (base `a56aed5`)

| # | Kind | Where | Finding | Resolution |
|---|---|---|---|---|
| 1 | superseded | build plan, "Design changes outside a checkpoint" | Still says each change to built code becomes a new checkpoint (DL-131). | **Fixed:** review answers are bundled (DL-131). |
| 2 | superseded | developer guide, section 11, "Design changes" | The same. | **Fixed:** the same. |
| 3 | superseded | build plan, "Claude configuration" (`design-change` skill) | "a new inserted checkpoint for built product code" | **Fixed:** review answers bundled, DL-131. |
| 4 | superseded | build plan and developer guide, the design-change record | A record comes only from a tooling review. | **Fixed:** every design change gets one (DL-126); DL-126's "Applies to" extended. |
| 5 | internal | `design-change` skill, step 7 | Every record "with its Sabotage checks table", which a docs-only change doesn't have. | **Fixed:** for tooling code. |
| 6 | superseded | `design-change` skill, step 8 | Ties the record to tooling commits. | **Fixed:** each commit carries its record, docs-only or tooling. |
| 7 | contradiction | DL-43's "Superseded by" | It was "none", though DL-126 supersedes it. | **Fixed:** DL-126 (in part). |
| 8 | contradiction | DL-131's "Supersedes"; DL-8 and DL-18 | The links between them were missing. | **Fixed:** DL-131 supersedes DL-8 and DL-18 in part. Their "Superseded by" filled in, and DL-131's "Applies to" extended. The scope follows DL-131 as the owner adopted it ("review answers"), so the skill's step 4 row was narrowed back to review answers (decision 1). |

**Decisions for the owner:**

1. **What bundling covers.** Does it cover every change to built code, or only review answers?
   - **Applied:** review answers only, as the owner adopted the retro's proposal 5 ("Collect
     review answers that change built code").
   - **Still to confirm:** whether other changes to built code should be bundled too.
2. **`ui-feedback.md` isn't in the repository.** The build plan's S2-C0 note and DL-124 name
   it, but it's untracked.
   - **Options:** the owner commits it; the note says "to be added before S2-C0"; or Slice 2's
     plan copies its items into S2-C0.
3. **The `new-area` skill's check.** The build plan has it verified against the `project` area
   "at the start of Slice 2". Should it be part of S2-C0, or Slice 2's first feature checkpoint?

**The owner's answers (Oct 21, 2026):**
1. Review answers only, as applied.
2. The owner moved the file to `docs/ui-feedback.md`, committed with these answers; the S2-C0
   note points there.
3. In S2-C0 (DL-132).

**Outside the change's scope:** `uv run wl seed --help` doesn't list `--demo`, although the
developer guide documents it.
