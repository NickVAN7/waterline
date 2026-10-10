# Review record: DC-2026-10-10 — § references in the UI design guide and its reviewer

- **Change:** the UI design guide design change (DL-61 to DL-65) adds `docs/ui-design-guide.md`
  and `.claude/agents/ui-reviewer.md`, which number their own sections. The docs consistency
  test read every `§N` as a design-doc section, so 26 of their references failed, and others
  passed only because design-doc happens to share the number. Now: `guide §N` (or
  `ui-design-guide §N`) names a guide section anywhere; a bare `§N` in the guide is its own; a bare
  `§N` in the reviewer is its own or the guide's; `design-doc §N` (either case) in both still
  means the design doc. `design_doc_sections()` becomes `numbered_sections(path)`. Developer
  guide section 9 documents it.
- **Base commit:** `f63d4c8` (`s1`); the pass reviewed the uncommitted changes on the
  `design/ui-guide` branch.
- **Reviewers:** `checkpoint-reviewer`. `security-reviewer` wasn't run: test-only tooling, nothing
  security-relevant.

Severity: **blocker**: wrong behavior, security, data integrity, or a failing gate. **major**:
missing tests, a convention violation, or doc drift. **minor**: small issues worth fixing or
logging.

**Author's checks** (evidence, not verification): six bad references appended one at a time
(`guide §7.9` and a bare `§7.1` in the build plan, `§11` and `design-doc §99` in the guide, `§6.9`
and `design-doc §7.1` in the reviewer) each failed the named test; the files were restored
byte-identical.

---

## checkpoint-reviewer, pass 1 — verdict: ready

| # | Severity | Area | Location | Finding | Resolution |
|---|---|---|---|---|---|
| 1 | minor | correctness | `test_docs_consistency.py:716`, `:726` | The `design-doc` prefix and lookbehind were case-sensitive, while the repo writes "Design-doc §N" at a sentence start (`tech-debt.md`, `developer-guide.md`). A "Design-doc §7.2" in the guide would have been checked against the guide's own §7.2 and passed, though design-doc has no §7.2. | **Fixed.** Both patterns use `[Dd]esign-doc`. Appending "Design-doc §7.2" to the guide now fails `test_every_section_reference_resolves_to_a_design_doc_heading`. |

The fix changes a test pattern only, so no second pass (the `checkpoint` skill, step 5).

**Sabotage checks** (in a temporary copy, deleted afterwards)

| Behavior | Source | Change made | Tests run | Caught by |
|---|---|---|---|---|
| A bare § in the UI guide resolves to its own headings | developer guide section 9 | `ui-design-guide.md:47` `§7.1` → `§7.9` | `test_docs_consistency.py -k section_reference` | `test_every_ui_guide_section_reference_resolves_to_its_heading` |
| `design-doc §N` in the UI files resolves against the design doc | same | `ui-reviewer.md:16` `design-doc §1` → `design-doc §99` | same | `test_every_section_reference_resolves_to_a_design_doc_heading` |
| `guide §N` elsewhere resolves against the UI guide | same | `frontend/CLAUDE.md:91` `guide §9` → `guide §11` | same | `test_every_ui_guide_section_reference_resolves_to_its_heading` |
| A bare § in the reviewer resolves to its or the guide's headings | same | `ui-reviewer.md:32` `§2.8` → `§2.9` | same | `test_every_ui_guide_section_reference_resolves_to_its_heading` |
| The UI files are left out of the bare design-doc check | test logic | `_OWN_NUMBERING` exclusion dropped | same | `test_every_section_reference_resolves_to_a_design_doc_heading` |

**Questions raised** (open for the owner):
1. In `ui-reviewer.md`, a bare `§N` passes if either the reviewer or the guide has that heading,
   and both have sections 1 to 5, so "§2" is ambiguous to a reader and a mistyped own reference
   can pass. Should the reviewer write `guide §N` for the guide's sections, so its bare `§N` is
   checked against its own headings only? (A change to the reviewer's text, so not made here.)
2. Outside the UI files, `guide §N` means the UI guide; "developer guide §9" would be checked
   against the UI guide and could pass. The developer guide tells writers to use "section N" for
   itself. Is that enough, or should only `ui-design-guide §N` count (`frontend/CLAUDE.md` uses the
   short `guide §9`, from the change note's text)?
