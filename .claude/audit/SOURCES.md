# Vendored audit prompts

Prompts the `simplicity-auditor` agent reads as plain files (never loaded as skills), copied
verbatim from their repositories at the commits below (DL-138). Updating them is a design change
that bumps the commit here.

| File | Source | Commit | License |
|---|---|---|---|
| `ponytail/ponytail-audit.md` | `DietrichGebert/ponytail`, `skills/ponytail-audit/SKILL.md` | `9cc65d03aa2da1db7121b912d03596409ee340b8` (v5.1.0) | MIT, `ponytail/LICENSE` |
| `ponytail/ponytail.md` | `DietrichGebert/ponytail`, `skills/ponytail/SKILL.md` | `9cc65d03aa2da1db7121b912d03596409ee340b8` (v5.1.0) | MIT, `ponytail/LICENSE` |
| `agent-skills/code-simplification.md` | `addyosmani/agent-skills`, `skills/code-simplification/SKILL.md` | `aeac41d4d005999432bb7312f7ff06383a91d59d` | MIT, `agent-skills/LICENSE` |
| `agent-skills/code-review-and-quality.md` | `addyosmani/agent-skills`, `skills/code-review-and-quality/SKILL.md` | `aeac41d4d005999432bb7312f7ff06383a91d59d` | MIT, `agent-skills/LICENSE` |
| `agent-skills/api-and-interface-design.md` | `addyosmani/agent-skills`, `skills/api-and-interface-design/SKILL.md` | `aeac41d4d005999432bb7312f7ff06383a91d59d` | MIT, `agent-skills/LICENSE` |

Ponytail's hooks are not vendored. What the agent uses from each file is set in
`.claude/agents/simplicity-auditor.md`.
