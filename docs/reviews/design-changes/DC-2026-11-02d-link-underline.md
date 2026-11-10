# Review record: DC-2026-11-02d — A link in running text is underlined

- **Change:** the owner's answers to S2-C16's open questions (chat, Nov 2, 2026): UI-TOK-13, a
  link inside running text is underlined (DL-248); DOMPurify's allow-list and bare `www.`
  autolinks unchanged (recorded in `docs/reviews/s2/S2-C16.md`, no rule changed). Docs only: no
  built link sits in running text (every one is standalone), and `MarkdownView` already
  underlines its links.
- **Kind:** docs only (no tooling code, so no `checkpoint-reviewer`, DL-18).
- **Base commit:** `2f03d47` (S2-C16).
- **Reviewers:** `docs-consistency` (trigger `design-change`), on one snapshot (DL-105).
- **Totals:** 1 fix, fixed; 0 decisions for the owner.
- **Gates at close:** `uv run wl check` green; CI on the commit.

---

## What changed

- **Decisions recorded:** DL-248.
- **Docs:** ui-design-guide (UI-TOK-13, the WCAG 1.4.1 row); `frontend/CLAUDE.md` (UI, the rule
  now cites UI-TOK-13); `.claude/agents/ui-reviewer.md` (the token checklist);
  `docs/reviews/s2/S2-C16.md` (the owner's decisions after the report).

## docs-consistency, pass 1 (base `2f03d47`)

### Fixes

| # | Kind | Where | Finding | Resolution |
|---|---|---|---|---|
| 1 | internal | ui-design-guide | UI-TOK-13 sat under §3.5 "PrimeVue preset", which it isn't about | **Fixed:** moved to the end of §3.4 "Control states", after UI-TOK-11 |

### Decisions for the owner

None.
