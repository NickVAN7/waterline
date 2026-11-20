---
target: requirement detail panel
total_score: 24
max_score: 40
na_heuristics:
p0_count: 0
p1_count: 2
target_identity: "file:/home/nick/scratch/impeccable-trial/waterline/frontend/src/views/requirement/RequirementDetail.vue"
target_fingerprint: "sha256:a7df58d8cf484fb6ca1a5a196c8b5b772aee58957b369d8057b3ce412224c58d"
target_path: /home/nick/scratch/impeccable-trial/waterline/frontend/src/views/requirement/RequirementDetail.vue
timestamp: 2026-11-14T01-33-21Z
slug: c-views-requirement-requirementdetail-vue-35059b7c
---
Method: dual-agent (A: design-review sub-agent · B: detector + browser sub-agent)

# Critique: requirement detail panel (RequirementDetail.vue in ItemPanel.vue)

Mode: Operate. Inspected source, six baseline shots, live trial app as Lena and Ella, RQ-1..RQ-6, edit mode, menus, approve-by-hand confirm, tab order. Nothing submitted.

## Design Health Score
| # | Heuristic | Score | Key issue |
|---|---|---|---|
| 1 | Visibility of system status | 2 | Header shows "Draft" while tree shows "Awaiting approval"; approval state ~600px down |
| 2 | Match system / real world | 3 | "Pending" in panel vs "Awaiting approval" in tree; "Rejected" vs "Reject" |
| 3 | User control and freedom | 3 | Solid discard guard, Esc layering, Trash |
| 4 | Consistency and standards | 2 | Status changes in two places; two key-value styles; tab strip white box on grey |
| 5 | Error prevention | 3 | No signal when setting Done/Rejected while a request is pending |
| 6 | Recognition rather than recall | 2 | Must scroll past description to learn approval; History lacks approval events |
| 7 | Flexibility and efficiency | 2 | No shortcuts; header icon buttons before focused title, unreachable by Tab |
| 8 | Aesthetic and minimalist | 2 | Same-weight actions; criteria Alert loudest on 6/6 |
| 9 | Error recovery | 3 | Specific refusal copy, focus handling |
| 10 | Help and documentation | 2 | Nothing explains Approve by hand / Approved · modified |
| Total | | 24/40 | Acceptable |

## Design Specificity Verdict
LLM: mostly category-interchangeable tracker detail stack; "status above the line, trail below" is not expressed in the composition. Domain-specific approval states exist but are flat text rows.
Deterministic scan: CLI clean (0 findings, 9 files). URL scan [] without a session (no evidence). Overlay: detect.js loaded but WebAssembly core blocked by trial CSP (no 'wasm-unsafe-eval'); no overlay.

## What's Working
1. Rigorous state and focus handling for 403/409/422/gone.
2. Domain-honest approval states (Approved · modified, Last approved: revision N).
3. Split pane that keeps context; accessible resizer; unsaved-edit guard.

## Priority Issues
- [P1] Approval state absent from the panel header (needs design-change vs DL-325/DL-326). clarify, layout.
- [P1] Approver and requester actions mixed: 5 buttons, two "Approve" verbs (ApprovalSection.vue:383-436). distill. UI-TOK-10 / DL-325 constraints.
- [P2] "No acceptance criteria" Alert outranks everything; DL-149 asks for a note. quieter.
- [P2] Edit mode breaks the header (lone ⋯) and splits metadata. layout.
- [P2] Trail is thin: History omits approval events; tab strip background. clarify, polish.

## Persona Red Flags
Alex: header icon buttons only by Shift+Tab; no shortcuts; 3-step status change; open row hidden under collapsed parent.
Sam: header+actions take ~340/400px at 640x400; "Awaiting approval" vs "Pending"; focus ring tight at scroll edge.
Lena: "Draft" on RQ-4; Approve by hand offered on approved RQ-5; Done/Rejected with pending request, no warning.
v2 steering approver: decide panel at y≈830 of 1600.

## Minor Observations
Parent wraps in 2-col dl at 560px; two key-value styles; "Revision: 1" alone; ⋯ trigger lighter; 375 overlay artifact.

## Questions to Consider
1. One composed status line at the top?
2. Is Approve by hand a header-level status action?
3. A decision-first arrangement for approvers?
4. Should the criteria check speak only at request time?
