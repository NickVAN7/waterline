---
target: requirement detail panel
total_score: 24
max_score: 40
na_heuristics:
p0_count: 0
p1_count: 3
target_identity: "file:/home/nick/scratch/impeccable-trial/waterline/frontend/src/views/requirement/RequirementDetail.vue"
target_fingerprint: "sha256:a7df58d8cf484fb6ca1a5a196c8b5b772aee58957b369d8057b3ce412224c58d"
target_path: /home/nick/scratch/impeccable-trial/waterline/frontend/src/views/requirement/RequirementDetail.vue
timestamp: 2026-11-15T17-54-23Z
slug: c-views-requirement-requirementdetail-vue-35059b7c
---
Method: dual-agent (A: design-review sub-agent · B: detector + browser sub-agent)

# Critique: requirement detail panel (RequirementDetail.vue in ItemPanel.vue)

Mode: Operate. Same bytes as the 2026-11-14 run, reviewed independently (that snapshot not read). Inspected live as Lena and Ella, RQ-1..RQ-6, 1280/375, light/dark, edit mode, menus, confirms, tab order. Nothing submitted.

## Design Health Score
| # | Heuristic | Score | Key issue |
|---|---|---|---|
| 1 | Visibility of system status | 2 | Header "Draft" on RQ-4 vs tree "Awaiting approval" (DL-376); pending request ~600px down |
| 2 | Match system / real world | 3 | Honest copy; "Approve by hand", "Re-open approval" unexplained |
| 3 | User control and freedom | 3 | Discard guard on Close/Esc/swap; edit form's Cancel discards dirty edits unprompted |
| 4 | Consistency and standards | 2 | Header vs tree badge; two Approve verbs; bare-word status menu; two dl styles; tab slab |
| 5 | Error prevention | 3 | Confirms on reject-without-comment, approve by hand, delete; blocked reasons shown |
| 6 | Recognition rather than recall | 2 | Approved · modified never shows what changed |
| 7 | Flexibility and efficiency | 2 | Header icon buttons before focused title (unreachable by Tab); no shortcuts |
| 8 | Aesthetic and minimalist | 2 | Criteria Alert on 6/6 and loudest; lone ⋯ in edit mode |
| 9 | Error recovery | 3 | Specific refusal copy with next step, focus to alert |
| 10 | Help and documentation | 2 | No link to guide's approvals/revisions pages |
| Total | | 24/40 | Acceptable |

## Design Specificity Verdict
LLM: half-specific; domain primitives (bound revision, re-approval diff, Approved · modified) are real but sit 600-1000px down; composition is a stock tracker detail stack; "status above, trail below" holds only for the status word.
Deterministic scan: CLI [] over 31 files but regex-only for .vue (element rules did not run; suggests detector.extensions {ext: .vue, engine: html}) — not a real clean. URL scan: sign-in redirect only. CDP scans (signed in): skipped-heading (Description h2 -> h4 via MarkdownView :level=2, RequirementDetail.vue:454-461; real, UI-MD-1/UI-SHL-8) on RQ-2 1280/375; cramped-padding on p-tabpanels (RequirementDetail.vue:484 px-0; likely false positive, UI-SHL-7) on all 3 states.
Overlay: detect.js loaded, WebAssembly core blocked by trial CSP (no 'wasm-unsafe-eval'); no overlay.

## What's Working
1. Accessibility engineering: focus, Esc layering, live regions, sr-only prefixes, coherent dark theme.
2. Real traceability primitives (DecidePanel.vue:91-112, ApprovalSection.vue:324-327, inline compare).
3. Copy discipline: named confirm buttons, visible blocked reasons, criteria as a note (DL-149).

## Priority Issues
- [P1] Approval state absent from the header and contradicts the tree (RequirementsView.vue:290-299, RequirementDetail.vue:370-375). Add Awaiting approval badge; "Your decision is needed" line; "Changed since revision N · See changes". Design change vs DL-325. clarify, layout.
- [P1] Approver decision buried among 5 actions, two Approve verbs (ApprovalSection.vue:383-435). Decide first; group requester/admin actions or move Approve by hand to ⋯ (DL-325/326 if moved). distill, layout.
- [P1] Tree clips Status badges beside split pane at 1280 ("Awaitin / approv"); h1 wraps. Rem min-width for Status column, named scroll region. No design change. adapt.
- [P2] Edit mode: dirty Cancel unguarded (extends DL-323); lone ⋯ (RequirementDetail.vue:368); stale heading; tabs/dl below form. harden.
- [P2] Criteria Alert fatigue (RequirementDetail.vue:455-457), flat 20px headings, h2->h4 skip in description. quieter, typeset.

## Persona Red Flags
Alex: header buttons unreachable by forward Tab; Tab falls to body after History; 6-10 Tabs to decide; no shortcuts; status menu doesn't mark current.
Sam: sibling h2s; double "History"; h2->h4 skip; clipped tree at 200% zoom; dt/dd split at 375.
Lena: Approve by hand vs Request approval unexplained; modified state needs Revisions trip; nested open row not revealed in tree.
v2 steering approver: opens on metadata and engineering warning; "Draft" reads as not-ready; no "you are asked to sign off"; no summary beside Approve/Reject.

## Minor Observations
Tabs white slab on grey (UI-STY-6); tab labels 14px; Compare h3 = h2 size; status menu omits Approved silently; two dl styles; short description textarea; orphan middle-dot in clipped column.

## Questions to Consider
1. Why is "waiting on you / changed since approval" never in the header while Priority and Reporter always are?
2. Panel shape by the viewer's role in this item?
3. Does Approve by hand belong beside the formal flow or in ⋯?
4. Lead Approved · modified with the diff and a keep / re-request choice?
