---
target: requirement detail panel
total_score: 27
max_score: 40
na_heuristics:
p0_count: 0
p1_count: 3
target_identity: "file:/home/nick/scratch/impeccable-trial/waterline/frontend/src/views/requirement/RequirementDetail.vue"
target_fingerprint: "sha256:a7df58d8cf484fb6ca1a5a196c8b5b772aee58957b369d8057b3ce412224c58d"
target_path: /home/nick/scratch/impeccable-trial/waterline/frontend/src/views/requirement/RequirementDetail.vue
timestamp: 2026-11-16T18-04-41Z
slug: c-views-requirement-requirementdetail-vue-35059b7c
---
Method: dual-agent (A: design-review sub-agent · B: detector + browser sub-agent)

# Critique: requirement detail panel (RequirementDetail.vue in ItemPanel.vue), third run

Mode: Operate. Live: RQ-1/2/4/5/6 at 1440/1280/1024/390, light/dark, ~200% zoom; menus, Edit (cancelled), Tab order. After the trial's audit/adapt/polish/harden fixes and the Approval layout change. Owner-decided items (relative heading shift, 80rem breakpoint, empty-description note, AC warning on request) not repeated.

## Design Health Score
| # | Heuristic | Score | Key issue |
|---|---|---|---|
| 1 | Visibility of status | 3 | Header "Draft" vs tree "Awaiting approval" on RQ-4 |
| 2 | Match real world | 3 | Awaiting approval / Pending / Not decided for one state |
| 3 | User control | 3 | Cancel, discard confirm, Esc solid; no undo of status change |
| 4 | Consistency | 3 | Panel = page; Approval list now matches details; edit mode leaves orphan ⋯ |
| 5 | Error prevention | 3 | Confirms on Approve by hand / Cancel request; Delete to Trash, opens on Cancel |
| 6 | Recognition | 3 | Status menu doesn't show the current status |
| 7 | Flexibility | 2 | No shortcuts/next-previous; icon buttons Shift+Tab only |
| 8 | Minimalist | 2 | Flat hierarchy; AC alert loudest element |
| 9 | Error recovery | 3 | 403/409/422 plain, focus handled |
| 10 | Help | 2 | No link to the guide from the panel |
| **Total** | | **27/40** | Acceptable |

## Design specificity
Coherent and calm, category-interchangeable; "status above, trail below" only in section order. Detector: source 0; browser (CDP) skipped-heading h2→h4 (known, decided) at 1280 light/dark and 390; straggler ×2 per state in user markdown (advisory, low value); RQ-4 clean. Overlay failed: CSP lacks 'wasm-unsafe-eval'. Both reviewers saw the tree Status column overflow at 1280 (detector missed it).

## Priority issues
1. [P1] Approve by hand same weight as the normal flow; no next-step emphasis (ApprovalSection.vue:397-434). Accent the state's next action; Approve by hand a quiet override or into ⋯ (owner: DL-325, DL-161/212). clarify, layout.
2. [P1] Badge whitespace-nowrap app-wide (Badge.vue:22, trial change): tree Status overflows at 1280 (still split pane under 80rem); restriction badge overflows at 320 (ui-reviewer). Nowrap only in the tree status cell; rem column width. adapt.
3. [P1] Panel header hides Awaiting approval (RequirementsView.vue:290-297); one word for the waiting state (owner: DL-325/DL-376). clarify.
4. [P2] Flat hierarchy (title text-xl vs section text-lg); AC alert loudest (RequirementDetail.vue:454-455). typeset, quieter.
5. [P2] Keyboard path: icon buttons before the focused title, Shift+Tab only; no way back to the tree but Close (ItemPanel.vue:264-296). harden.

## Persona red flags
Alex: icon buttons only backwards; no item shortcuts. Sam: title focus box reads as a field at 200%; blocked Request approval's reason after Approve by hand. Lena: header says Draft while waiting; three words; Approve by hand beside own Cancel request; tree Status overflow at 1280.

## Minor
Edit mode ragged (orphan ⋯, title repeats field, grid reshuffles); empty live-region p adds a gap; History tabpanel Tab stop; "Last approved" repeats latest request; bare URL wraps 4 lines; status menu doesn't explain missing Approved.

## Questions
Why is the waterline invisible in the most-used surface? Should a lead approve by hand a request she just made without a reason? Does the panel still need the AC alert once the request warns?
