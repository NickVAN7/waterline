# The simplicity audit's lens: sources and licenses

`.claude/agents/simplicity-auditor.md` ("The lens") holds sections of these prompts, copied
verbatim from their repositories at the commits below (DL-138); the rest of each file, once
vendored here whole, was deleted (the outside review's Package 4 item 8, S3-C0u). Updating them
is a design change that bumps the commit here.

| Sections | Source | Commit | License |
|---|---|---|---|
| "1. Map first", "2. Look for" (its Lean item), "3. Check before you report" | `DietrichGebert/ponytail`, `skills/ponytail-audit/SKILL.md` | `9cc65d03aa2da1db7121b912d03596409ee340b8` (v5.1.0) | MIT (Ponytail, below) |
| "The smallest complete change" | `DietrichGebert/ponytail`, `skills/ponytail/SKILL.md` | `9cc65d03aa2da1db7121b912d03596409ee340b8` (v5.1.0) | MIT (Ponytail, below) |
| The whole skill but "5. Scope to What Changed" and "Step 3: Apply Changes Incrementally" | `addyosmani/agent-skills`, `skills/code-simplification/SKILL.md` | `aeac41d4d005999432bb7312f7ff06383a91d59d` | MIT (agent-skills, below) |
| "2. Readability & Simplicity", "3. Architecture", "Structural Remedies" | `addyosmani/agent-skills`, `skills/code-review-and-quality/SKILL.md` | `aeac41d4d005999432bb7312f7ff06383a91d59d` | MIT (agent-skills, below) |
| "Red Flags", "Verification" | `addyosmani/agent-skills`, `skills/api-and-interface-design/SKILL.md` | `aeac41d4d005999432bb7312f7ff06383a91d59d` | MIT (agent-skills, below) |

Ponytail's hooks are not vendored.

## Ponytail's license

```
MIT License

Copyright (c) 2026 DietrichGebert

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## agent-skills' license

```
MIT License

Copyright (c) 2025 Addy Osmani

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
