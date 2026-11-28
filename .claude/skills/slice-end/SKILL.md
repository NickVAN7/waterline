---
name: slice-end
description: The extra steps at a Waterline slice's last checkpoint — the schema markers, the slice-end reviewers (docs-consistency, repo-auditor, simplicity-auditor, fresh-clone-verifier, user-guide-verifier), the slice retro, and the merge. Use together with the checkpoint skill at the last checkpoint of every slice.
---

# A slice's last checkpoint

Follow the `checkpoint` skill as usual; each step here joins the `checkpoint` step it names
(DL-393).

## With step 2 (gates)

Search `docs/schema-doc.md` for `Added in Slice <n>.` (this slice's number) and confirm each
marked column is in its model. The docs consistency tests require these columns only once this
checkpoint is committed, so `wl check` can't catch a miss yet.

## With step 4 (review)

- **In the parallel step with the reviewers, on the same snapshot** (DL-108, DL-392):
  - `docs-consistency`, with trigger `slice-end` and, as the base, the previous slice's last
    checkpoint commit (the root commit for Slice 0). It reports **Fixes** and **Decisions**.
  - `repo-auditor`, with the slice ID and the checkpoint ID (DL-41). It audits the whole
    repository, not this diff, and runs no tests.
  - `simplicity-auditor` (DL-138). It audits the whole repository for overengineering and
    reports only. The review record gets its own `## simplicity-auditor` section (a docs
    consistency test requires that heading in the slice's last record, DL-165).
- **Once those have finished,** run `uv run wl down` (so ports are free) and invoke
  `fresh-clone-verifier` with the repository's absolute path and the checkpoint ID. Its findings
  are fixed in `docs/developer-guide.md` like any other finding.
- **With the dev stack still down,** invoke `user-guide-verifier` with the repository's absolute
  path, the checkpoint ID, and the slice whose "Done when" list to walk (DL-124). Its findings
  are fixed in `docs/behavior-reference.md` or the guide under `docs/user-guide/`, or in the app
  when the app is what's wrong. Run `uv run wl up` again afterwards.

## With step 5 (findings)

- `docs-consistency` **Fixes** are resolved like any finding. Its **Decisions** are not yours:
  leave them undecided and put them in the report for the owner.
- `repo-auditor` findings: fix one only when the fix is within the slice's scope. Otherwise log
  it (minor), or put it in the report as a proposed design change (major or blocker). Its
  questions go to the owner, and its findings feed the retro.
- `simplicity-auditor` findings are never fixed in the checkpoint: each goes to the owner, who
  decides it, and feeds the retro; the next slice's C0 applies the accepted ones.
- Re-reviews and the review record follow `checkpoint` step 5.

## With step 6 (commit and push)

The commit message's slice-only lines (fresh-clone verification, docs consistency, repository
audit) are filled in. Then the merge, which waits for the owner:
- Any changes the owner decides in the retro are applied first, on the slice branch, with the
  `design-change` skill and green CI (DL-19).
- Before asking, check that every commit is linked to a GitHub account (`gh api
  repos/<owner>/<repo>/pulls/<n>/commits --paginate --jq '.[] | [.sha[0:7], .author.login] |
  @tsv'`: no empty login) and, once the PR is marked ready, its merge state (`gh pr view <n>
  --json mergeStateStatus,reviewDecision`), and report a block or an unlinked commit: the ruleset
  then requires an approval the owner can't give on their own PR (DL-33).
- On the owner's say-so, mark the PR ready (`gh pr ready`) and merge it with a merge commit (`gh
  pr merge --merge`; the branch stays, since GitHub blocks deleting any branch, DL-27), never
  squash or rebase. The git guard asks the owner to confirm the merge (DL-25).

## With step 7 (report)

Add the **slice retro**: what each reviewer caught, what escaped to the owner, which skills and
agents never triggered, the verdict of any process trial, the `repo-auditor` findings left for
the owner (with the design changes they propose), and every `simplicity-auditor` finding for the
owner to decide. The owner decides what changes; each change that changes or supersedes a
written rule, or sets a process, gets a decision-log entry (DL-312), and each is applied on the
slice branch before the merge (DL-19).
