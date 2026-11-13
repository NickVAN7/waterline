# Waterline — Tech-Debt Log

Every known shortcut, with its reason and the checkpoint or slice that will fix it. The goal is
an empty log (every entry resolved); nothing is left unrecorded. Open entries come first. A
resolved entry moves to **Resolved**, at the end, shrunk to its heading, Added, and Status
(DL-313); its full text stays in git history and in the review record that resolved it.

Entry format:

```
### TD-<n>: <short title>
- **Added:** <checkpoint ID>
- **What:** <the shortcut or gap>
- **Why:** <reason it was accepted>
- **Fix by:** <checkpoint or slice>
- **Status:** open | resolved in <checkpoint ID>
```

---

### TD-12: Password minimum is 8 characters
- **Added:** S1 planning (Sept 30, 2026)
- **What:** `rules/password_policy.py` requires 8 characters. NIST accepts 8 only alongside a
  second factor; 12 is the intended minimum.
- **Why:** v1 runs locally for a few users; the owner chose 8 for now.
- **Fix by:** Slice 7 (before the first non-local deployment, and by the end of v1 at the
  latest; re-target if deployment moves later): raise the minimum to 12, and at sign-in
  (the only time the plaintext is available) set `must_change_password` when the entered
  password fails the current policy, so existing short passwords are changed at next sign-in.
- **Status:** open

### TD-13: End-to-end tests run on Chromium only; no local HTTPS
- **Added:** S1 planning (Sept 30, 2026)
- **What:** Production cookie settings (`__Host-session`, `Secure`) are kept in dev and test.
  Chromium treats `http://localhost` as secure; WebKit has historically not, so Playwright runs
  Chromium only, and the dev server works only at `localhost` (not a LAN IP or custom
  hostname).
- **Why:** Avoids an insecure-cookie switch that could reach production (build plan,
  implementation decision 9); cross-browser coverage matters little for a few local users.
- **Fix by:** Slice 7 (before the first non-local deployment, and by the end of v1 at the
  latest; re-target if deployment moves later): local HTTPS for the dev server (e.g.
  mkcert with Vite's `https` option) and end-to-end runs on Firefox and WebKit.
- **Status:** open

### TD-14: The pre-deployment items in design-doc §4 have no slice
- **Added:** S1 planning (Sept 30, 2026)
- **What:** Design-doc §4, "Before the first non-local deployment", lists work with no slice
  of its own: sign-in throttling (`login_attempt`), password re-entry for sensitive actions, the nightly expired-session cleanup, per-org session
  lengths, the reverse proxy forwarding `Host`, re-evaluating the `Origin` check against an
  allowed-origins setting, the admin audit-event screen, general API rate limiting (per IP at
  the reverse proxy, per user in the app for expensive endpoints; 429 `rate_limited` with
  `Retry-After`; added Oct 5, 2026), and a compliant deployment for export-controlled data
  (design-doc §3.1; added Oct 5, 2026). (The password minimum, local HTTPS, and the CSP's inline
  styles have their own entries, TD-12, TD-13, and TD-87.)
- **Why:** v1 runs locally for a few users; none of these matter until the app is deployed.
- **Fix by:** Slice 7 (before the first non-local deployment, and by the end of v1 at the
  latest; re-target if deployment moves later): build each item, or give it its own slice.
- **Status:** open

### TD-17: The app connects as the owner of its tables
- **Added:** S1-C1 (security review of the append-only follow-up)
- **What:** The app and Alembic use the same database URL, so the running app is the owner of
  every table (in Compose, `POSTGRES_USER`, a superuser). The `audit_event` append-only trigger
  (and, from S2-C3, `activity_log`'s, DL-193) stops ordinary `UPDATE` and `DELETE`, but SQL on the app's own connection could disable or
  drop the trigger first (or `TRUNCATE` the table), so the guard doesn't hold against, say, an
  injection.
- **Why:** v1 runs locally for a few users; splitting roles needs deployment-time setup
  (role creation, grants, a second URL) that isn't worth building before there's a deployment.
- **Fix by:** Slice 7 (before the first non-local deployment, with TD-14; re-target if
  deployment moves later): migrations run as the owner, the app as a role with only data rights
  on the app's tables (no `ALTER`, `DROP`, or `TRUNCATE`), with a test that the app's role can't
  disable the triggers.
- **Status:** open

### TD-19: npm advisory GHSA-vfj7-8cjw-p6xm (braces) is allowlisted
- **Added:** workflow review (DL-13, Oct 8, 2026)
- **What:** `wl audit` ignores GHSA-vfj7-8cjw-p6xm (high: stack-exhaustion denial of service
  in `braces` through deeply nested patterns), through its entry in `audit-allowlist.toml`.
  `braces` 3.0.3 comes only through `@vue/eslint-config-typescript` → `fast-glob` →
  `micromatch`, a dev dependency of the linter.
- **Why:** No fixed release exists: the advisory covers every `braces` version up to 3.0.3, the
  latest. npm's only "fix" downgrades `@vue/eslint-config-typescript` from 14.9.0 to 14.0.1.
  The vulnerable code only expands glob patterns from the repository's own ESLint
  configuration, never untrusted input, and never ships in the app.
- **Fix by:** Slice 3 (its tech-debt review): still no fixed `braces` (3.0.3 is the latest) (owner, S2-C22 tech-debt review, Nov 8, 2026)
- **Status:** open

### TD-20: What the git guard can't see
- **Added:** DC-2026-10-08 (review passes 3, 6, and 7; narrowed by DC-2026-10-08b and DL-31)
- **What:** The git guard (`.claude/hooks/guard_git.py`) checks the shell commands Claude runs. It
  doesn't see (1) a script or program that runs git itself or changes `.git/hooks/` (`bash
  <script>`, `python <file>`, a tool that commits, `uv run pre-commit uninstall`), (2) a write to a
  shell startup file (`~/.bashrc`: an exported `SKIP`, a `git` function) that changes later shells,
  or (3) a call that doesn't mention git redirecting to a target built by an expansion (`>>
  .gi$'t'/config`); blocking every expansion in a target would also block the common `>
  "$TMP/x"`. The deny-list guard's gaps (a `cd` in a subshell, exported variables, `include.path`,
  nested shells, run-time `gh api` arguments) are closed by the allow-list (DL-26), and so are
  review DC-2026-10-08b's (redirects into `.git/` or a git config file from a call that mentions
  git, read options that run or write, unquoted heredocs, expansions that hide a command, a glob
  in a redirect target). Claude's file tools editing `.git/` or a git config file are blocked by
  the protected-files hook (DL-31), and `.pre-commit-config.yaml` is the owner's (DL-30). Push and
  fetch configuration is left to the rulesets (DL-28). A program that writes a git config file
  without naming it is part of (1).
- **Why:** No command guard can read what another program does. GitHub's rulesets (DL-27) refuse
  pushes to `main`, force-pushes, and deletions whatever runs them; a skipped local hook is
  caught by CI's `wl check`.
- **Fix by:** Slice 7 (the owner decides whether this closes as won't-fix now that the
  rulesets are on).
- **Status:** open

### TD-28: A user's name is one field, so username suggestions guess first and last names
- **Added:** design change DL-66 (Oct 10, 2026)
- **What:** `user.name` is a single column, so the username suggestion (DL-66) takes the first and
  last word as first and last name. That guesses wrong for names like "Mary Ann van der Berg"
  (`mary-berg`), and gives nothing for a name with no Latin letters. Split the name into first-name
  and last-name fields (schema, API, forms, the suggestion rule, and existing rows).
- **Why:** the owner accepted the guess for now; the split touches the built `user` model and every
  form that edits a name.
- **Fix by:** Slice 7 (before the first non-local deployment, so no real accounts need their names
  split)
- **Status:** open

### TD-29: An account action's rank check reads the target's memberships without a lock
- **Added:** S1-C10
- **What:** `UserService.load` reads the target's memberships for the rank rule with no lock, so
  a role grant committing between the check and the action's commit can raise the target above
  the actor: an org admin's password reset could land on someone just made a workspace admin,
  handing the org admin a temporary password for a higher-ranked account (S1-C10 security
  review). The fix locks the target's user row before the memberships are read and makes every
  workspace and org role grant (the roster's add, create, role change, and handover) lock the
  same row, in one order with the owners' locks so a deactivation and a role change can't
  deadlock; with a race test.
- **Why:** the window is narrow and not attacker-controlled (the promotion is someone else's
  action), each reset ends the target's sessions and is audited, and the lock order needs its own
  design across the roster and the account actions.
- **Fix by:** Slice 7 (before the first non-local deployment, with "password re-entry for
  sensitive actions")
- **Status:** open

### TD-31: Other locked mutations check rights against the role loaded before the lock
- **Added:** S1-C13
- **What:** the `AuthzContext` is loaded at the start of a request. The restriction change
  re-reads the caller's own project role after taking the project's lock (`with_current_role`,
  owner decision in the S1-C13 security review), so a role removed while it waits is seen. The
  other mutations that wait on a lock (project update, archive, member adds, role changes and
  removals, and the workspace and org rosters) still check rights against the context as loaded:
  a caller whose role is removed while their request waits can still finish it. The window is
  milliseconds and needs a request already in flight.
- **Why:** the owner decided the restriction change in S1-C13 and chose to revisit the rest
  later.
- **Fix by:** Slice 3 (its tech-debt review re-checks it); accepted again (owner, S2-C22 tech-debt review, Nov 8, 2026); fix it when a checkpoint adds a locked mutation where the race would matter
- **Status:** open

### TD-37: My work has no "see all" for its sections
- **Added:** S1-C14a
- **What:** My work's projects section shows the first 10 projects (`GET /api/me/work`) and says
  how many there are, but has no "see all" list over `GET /api/me/work/{section}` (design-doc
  §11); a user on more than 10 projects finds the rest on each org's project list. From S2-C20b,
  the approvals section too (`/approvals`): past 10, the page says how many there are; an
  approval past the first 10 shows once an older one is decided. From S3-C0f each org's section
  links to its list (DL-359); from S3-C0j favorites are shown in full (DL-369), so approvals
  alone need one.
- **Why:** smallest complete change: no demo user is on more than two projects, and the org list
  already shows them all; no demo user has more than a few approvals. The "see all" list belongs with the sections that need one most.
- **Fix by:** S3-C29 (My work's "see all" for approvals; its route exists, so frontend only)
- **Status:** open

### TD-38: The project selector lists an org's first 200 projects
- **Added:** S1-C14a
- **What:** the project selector loads the current org's projects in one request at the API's
  page limit (200) and filters them in the browser, so an org with more than 200 projects
  shows only the first 200 there (all of them are on its project list).
- **Why:** smallest complete change: v1's orgs have tens of projects. A server-side search
  parameter would be new API.
- **Fix by:** S3-C17 (the selector's search, on S3-C13's server-side `?q=`)
- **Status:** open

### TD-41: Pickers of people load the first 200
- **Added:** S1-C15
- **What:** the replacement-owner picker (the roster's people), the create-org dialog's owner
  picker (the workspace's active users), and the create-project dialog's first-admin picker (the
  org's active members and the workspace's active staff, DL-152) each load one page at the API's limit (200) and
  offer those; a roster, workspace, or org with more people shows only the first 200 by name.
- **Why:** smallest complete change, as TD-38: v1's workspaces have tens of people, and a search
  would be new API (the lists have no text filter yet).
- **Fix by:** S3-C17 (one searchable person picker, on S3-C13's server-side `?q=`)
- **Status:** open

### TD-42: The own-row reset is hidden by a client-side check
- **Added:** S1-C15
- **What:** the server refuses an admin's reset of their own password (403, S1-C4 security
  review), but `allowed_actions` still carries `user.manage` on their own row, so
  `AccountActions` hides "Reset password" by comparing the row's id with the signed-in user's: a
  copy of a server rule in the client (frontend/CLAUDE.md).
- **Why:** removing it needs a separate authorization action for the reset, which `allowed_actions`
  leaves out on one's own row: a design change in `app/authz/` with spec tests, outside S1-C15
  (owner decision, S1-C15 review).
- **Fix by:** Slice 3 (its tech-debt review re-checks it) (owner, S2-C22 tech-debt review, Nov 8, 2026); the split comes back only as a design change (DL-73)
- **Status:** open

### TD-63: Settings saves are last-save-wins, with no optimistic lock
- **Added:** S1-C17 (repo-auditor's question)
- **What:** project, org, and workspace settings have no version check, so when two admins change
  the same field, the later save wins without either seeing the conflict. (TD-56 covers fields
  the saver didn't change.)
- **Why:** the owner judged it not an issue at Slice 1's scale.
- **Fix by:** Slice 7 (before the first non-local deployment) (owner, S2-C22 tech-debt review, Nov 8, 2026): still no issue at v1's scale
- **Status:** open

### TD-64: One action registry for every area
- **Added:** DC-2026-10-22 (DL-151)
- **What:** every area's actions are registered in one file, `authz/actions.py` (263 lines with
  Slice 1's actions), rather than per-area policy files; it grows with every area.
- **Why:** the owner kept the one registry Slice 1 built (DL-151), and expects it will likely
  need splitting as the app grows.
- **Fix by:** Slice 3 (its slice-end tech-debt review, and each one after: split it into per-area files once it passes about 600 lines, 387 at S2-C22, or a slice-end audit recommends it)
- **Status:** open

### TD-68: mutmut segfaults on one shape of `rules/rank.py`
- **Added:** S2-C2
- **What:** with mutmut 3.8.0 on Python 3.14.4, `wl backend mutate` crashed with a segmentation
  fault (exit 139, inside mutmut's trampoline reading `os.environ`, with `setproctitle` loaded)
  every time `rank_between` unpacked `_split(after)` into two names; calling `_split(after)`
  twice, as the module does now, passes. The crash is in the tool, not the code under test.
  From S2-C12 it is intermittent, the same code crashing on some runs (in mutmut's stats run)
  and passing on others: about half of six runs crashed, whatever the shape of
  `rules/approval_policy.py`'s new functions.
  After S2-C12 (on a new machine): the first `wl check` crashed in `mutmut run` (a fatal Python
  error, with `setproctitle`, `greenlet`, and SQLAlchemy's compiled extensions loaded), and the
  next, on the same tree, passed. Then, in a scratch copy, the gate's mutation sequence (clean,
  `mutmut run`, `export-cicd-stats`, `mutation_gate check`) passed 30 times out of 30: 10 as
  configured, 10 with `use_setproctitle = false`, and 10 with `process_isolation =
  "forkserver"`. Since the setup as configured didn't crash there either, the runs don't show
  whether either setting helps. What the copy lacked: mutmut running inside a full `wl check`,
  after about 8,000 tests with the Docker stack up, and the repository's long-used `.venv`.
  Ruled out: capping pytest-xdist (mutmut's pytest already runs with `-n 0`) and running the
  gate's steps one at a time (they already do). Capping `--max-children` (default: one per
  CPU) is unlikely to help, since the recorded crashes were in the single-process stats run,
  before any child is forked.
- **Why:** not worth chasing inside a checkpoint; the gate passes on the committed code. The
  owner chose to leave mutmut as configured until it crashes again (after S2-C12).
- **Fix by:** Slice 3 (its tech-debt review), or sooner at the next crash: then the reproduction plan below (owner, S2-C22 tech-debt review, Nov 8, 2026); no crash recorded since S2-C12
- **Status:** open

### TD-70: The requirement tree stops at 2,000 rows
- **Added:** S2-C5
- **What:** `GET /api/projects/{key}/requirements` returns at most 2,000 requirements in
  `(rank, id)` order, with `truncated: true` above it (DL-159). The cut is by rank across every
  level, so a truncated tree can hold a child whose parent was left out, and a requirement moved
  to the bottom of its level can fall past the cut and leave the tree on the next load (DL-256).
- **Why:** the tree is a ranked view, returned whole for drag-and-drop (build plan, "API
  conventions"); the owner judged 2,000 more than enough for v1 (DL-159), and accepted the moved
  row's case (DL-256).
- **Fix by:** Slice 7 (the end of v1), or sooner when a project nears 2,000 requirements: then paged (DL-159); reviewed (owner, S2-C22 tech-debt review, Nov 8, 2026)
- **Status:** open

### TD-73: The rank rewrite sends one UPDATE per sibling
- **Added:** S2-C7 (checkpoint-reviewer finding 4)
- **What:** a move with no rank between its neighbors (a tie or the 255-character cap, DL-204,
  DL-213) rewrites the parent's children with one `direct_update` each, so a rewrite among the
  tree's cap of 2,000 top-level requirements is about 2,000 round trips under the project's
  tree lock (DL-214), holding up other moves in that project for a second or two.
- **Why:** the rewrite is rare (only a tie or the cap triggers it) and correct as built; one
  statement (`UPDATE … FROM (VALUES …)`) needs `updated_at` held back by hand, outside the
  helper that does it now.
- **Fix by:** S3-C7 (one statement, shared with the task order's rewrite, DL-345)
- **Status:** open

### TD-76: The revision feed has no `(requirement_id, id)` index
- **Added:** S2-C9
- **What:** the build plan's feeds have `(scope, id)` indexes ("API conventions"); the revision
  list (`GET …/requirements/{number}/revisions`) is served by `requirement_revision`'s
  `UNIQUE(requirement_id, revision_number)` index and sorts the requirement's revisions by `id`.
- **Why:** a requirement has tens of revisions, not thousands, so the sort is cheap; an index is
  a migration for no measured gain.
- **Fix by:** Slice 7 (the end of v1), or sooner if a requirement's revisions number in the thousands: the index (owner, S2-C22 tech-debt review, Nov 8, 2026)
- **Status:** open

### TD-79: Each approver costs about eight queries
- **Added:** S2-C10 (checkpoint-reviewer finding 5)
- **What:** creating an approval request checks each approver in turn: `hold_access` (four
  queries), the user, and their authorization context (three), so 50 approvers are about 400
  round trips, made while the requirement is locked.
- **Why:** bounded by the 50-approver cap (DL-226), and a request names a handful in practice; a
  batched version needs `hold_access` and `authz_context` for many users at once, which nothing
  else needs yet.
- **Fix by:** Slice 7 (the end of v1), or sooner if requests name many approvers: batch the holds and the contexts (owner, S2-C22 tech-debt review, Nov 8, 2026)
- **Status:** open

### TD-83: A request created while someone loses access can deadlock with the change
- **Added:** S2-C13 (owner decision, DL-235)
- **What:** a path that takes someone's access away locks the projects of their pending rows and
  requests first, makes the change, then looks again (`ApprovalService.replace_for`) and locks
  the project of any request created in between. A removal "with their projects" also locks,
  in `ProjectRepository.memberships_in`, the project of a membership added after it read their
  projects (the add committed while the removal waited on their org or staff row). Those are
  the two places a project is locked after a person's rows. A request naming them in such a
  project, holding it and waiting on their rows, can deadlock with the change. Postgres aborts
  one of the two: a 500, and nothing it did is kept.
- **Why:** the window is a request created in the same moments as the person's removal,
  deactivation, or role change; the owner accepted it rather than a retry (DL-235).
- **Fix by:** Slice 7 (before the first non-local deployment): retry once on a deadlock, or confirm the window is still rare (owner, S2-C22 tech-debt review, Nov 8, 2026)
- **Status:** open

### TD-84: Finding a requester's pending requests has no index
- **Added:** S2-C13 (checkpoint-reviewer finding 4)
- **What:** `ApprovalRepository.projects_with_pending` filters `approval_request` on
  `requested_by` and `status`, and no index starts with `requested_by`, so each removal, role
  change, deactivation, or revocation scans the table twice (the lock and the look again). The
  table only grows: requests are cancelled, never deleted.
- **Why:** negligible at the expected volumes (one firm's requests); an index is a schema change,
  which goes through a design change (schema-doc).
- **Fix by:** Slice 7 (the end of v1), or sooner if `approval_request` grows large: an index on `(requested_by, status)`, through a design change (owner, S2-C22 tech-debt review, Nov 8, 2026)
- **Status:** open

### TD-86: npm overrides pin `minimatch` and `glob`
- **Added:** `658e50b` (`chore(deps):`, Oct 31, 2026; logged after the fact)
- **What:** `frontend/package.json` has `overrides` pinning `minimatch` 11.0.3 and `glob`
  14.0.3, past the versions their parent packages ask for, to clear `wl audit`
  (GHSA-g3hv-75wg-m249, GHSA-3g3m-2fjr-6pw4).
- **Why:** the parents hadn't released versions that pull the fixed ones; an override silently
  outlives its need, so it's logged here.
- **Fix by:** Slice 3 (its tech-debt review), and at any dependency bump before it: remove the `overrides`, reinstall, and rerun `uv run wl audit`; still needed at S2-C22 (removing them brings back the `minimatch` advisories) (owner, S2-C22 tech-debt review, Nov 8, 2026)
- **Status:** open

### TD-87: The CSP allows inline styles
- **Added:** DC-2026-11-02b (DL-246)
- **What:** the Content-Security-Policy has `style-src 'self' 'unsafe-inline'`, so an injected
  `<style>` or `style` attribute isn't blocked; scripts stay `'self'` only.
- **Why:** PrimeVue and the Vite dev server inject `<style>` tags, and a nonce needs a server
  that mints one per response; the Vite dev server is the only one today.
- **Fix by:** Slice 7 (before the first non-local deployment): its server sends the policy
  (`contentSecurityPolicy`, `frontend/vite.config.ts`, today sent only by the Vite dev server)
  with a per-response nonce (PrimeVue's `csp.nonce`, Vite's `html.cspNonce`) in place of
  `'unsafe-inline'`, if it can mint one
- **Status:** open

### TD-89: Opening branches near the 2,000-row cap pauses the page
- **Added:** DC-2026-11-02f (DL-253)
- **What:** PrimeVue TreeTable re-renders every visible row each frame, so a tree open near the
  cap pauses: "Expand all" took about 5.5 s to show 2,000 rows, with single pauses of up to about
  0.8 s. Since DL-271 and DL-272, "Expand requirement" opens no more than 500 rows under a
  requirement beyond its first level (TD-93), but opening branches by hand can still reach the
  cap.
- **Why:** v1 projects are far below the cap; a fix (virtual scrolling, or a widget that draws
  only the rows in view) is a widget change.
- **Fix by:** Slice 7 (the end of v1), or sooner if a project nears 1,000 requirements:
  measure again with the largest real project, and change the tree's rendering only if one
  nears the cap
- **Status:** open

### TD-96: The approver picker can't name an inherited project admin
- **Added:** DC-2026-11-05 (DL-278)
- **What:** the request dialog's approver picker lists the project's explicit members only, so an
  inherited project admin without a membership, whom design-doc §6.2 lets a request name, can't
  be picked in the UI; the API accepts them.
- **Why:** the members list already exists; a candidates endpoint for everyone §6.2 allows is a
  new endpoint the owner chose not to build in S2-C20 (DL-278).
- **Fix by:** S3-C17 (the approver picker becomes the searchable person picker, on S3-C13's candidates endpoint for everyone §6.2 allows)
- **Status:** open

### TD-97: "Show deactivated" sits above the people lists, outside a filter bar
- **Added:** DC-2026-11-06 (DL-295)
- **What:** the org members, project members, workspace staff, and workspace users lists show
  their "Show deactivated" checkbox above the list, not in a filter bar.
- **Why:** the filter bar is built in Slice 3 (build plan, API conventions, "Frontend"); S2-C21a
  needs only the one checkbox.
- **Fix by:** S3-C16 (the filter bar: the checkbox moves into it on the four lists)
- **Status:** open

### TD-98: The session list shows the 200 most recently active sessions only
- **Added:** S2-C21b
- **What:** Account settings' Sessions asks for one page of 200, the API's page limit, and never
  for the next, so a user with more live sessions doesn't see the rest, and "This session" may
  be among them. Sign out other sessions still ends all of them.
- **Why:** a user has a handful of live sessions (each ends after 7 idle days); paging a list
  nobody fills is code with no use yet.
- **Fix by:** Slice 7 (the operations screen), or sooner when someone has more than 200 live
  sessions: page the list (`Pagination`, `useListQuery`)
- **Status:** open

### TD-100: The approval-request list builds its page by hand
- **Added:** S2-C22 (repo-auditor finding 2)
- **What:** `RequirementService.approval_requests` builds `Page[ApprovalRequestItem](items=…,
  total=…, limit=…, offset=…)` itself rather than `page.with_items(rows)`, the helper TD-54
  added for every list.
- **Why:** S2-C20 code, fixed only when needed (DL-106); it behaves the same.
- **Fix by:** Slice 3 (its tech-debt review, S3-C33: no Slice 3 row touches approval reads)
- **Status:** open

### TD-101: The reporter and approver checks are near-copies
- **Added:** S2-C22 (repo-auditor finding 3)
- **What:** `RequirementService._check_reporter` and `_check_approver` take the same four steps
  (hold the access, get the user, load their context and authorize, check `is_active`); only the
  action and the error differ, so a change to one (TD-79's batching) has to be made in both.
- **Why:** S2-C11 and S2-C10 code, fixed only when needed (DL-106).
- **Fix by:** S3-C6 (one shared person check for reporter, approver, assignee, and reviewer)
- **Status:** open

### TD-102: A members list with no row actions still shows an Actions column
- **Added:** S2-C22 (user-guide-verifier finding 9)
- **What:** for someone who may change nobody (a project member), the roster's table keeps its
  "Actions" header over empty cells.
- **Why:** Slice 1 and S2-C17 roster code, fixed only when needed (DL-106); it's cosmetic.
- **Fix by:** S3-C16 (the filter bar's checkpoint, which reshapes the roster's table, TD-97)
- **Status:** open

### TD-104: The documentation has no search of its own
- **Added:** DC-2026-11-09-s2-retro-and-ui-polish (DL-342)
- **What:** the reader's guide (from S3-C0g) has no docs-only search.
- **Why:** deferred by the owner: the guide is small enough to browse from its nav, and Slice
  6's site-wide search covers the docs.
- **Fix by:** Slice 6 (the site-wide search): revisit a docs-only search as the docs grow
- **Status:** open

### TD-107: An icon button's tooltip is its `title`, which keyboard focus never shows
- **Added:** S3-C0d
- **What:** the side panel's Open full page, Copy link, and Close, ⋯ More actions, and
  `RowActions` before them, show their name on hover through the native `title` only: it doesn't
  appear on keyboard focus and can't be dismissed with Esc (WCAG 1.4.13), so a sighted keyboard
  user sees bare icons. Their accessible names are right.
- **Why:** the repo's one pattern for a tooltip; a focus-showing hint (the guide's `FieldHint`)
  isn't built yet, and building one is its own component (ui-reviewer, S3-C0d, finding 5).
- **Fix by:** S3-C33 (the tech-debt review: build the hint then, or before the first new icon button)
- **Status:** open

### TD-108: Just above 64rem, the split pane leaves the list little room
- **Added:** S3-C0d
- **What:** the split pane starts at 64rem and is 400 to 800px wide (DL-321, DL-322), so at
  1024px (or 1280px at 125% zoom), with the sidebar and padding, a 560px panel leaves the tree
  about 150px, and a stored 800px leaves none, the row then scrolling sideways. Since DL-356 the
  panel is beside `main` itself, so the page header (the `h1` and **New requirement**) and its
  alerts narrow with the tree.
- **Why:** kept as decided by the owner (2026-11-11, S3-C0d review, ui-reviewer finding 2):
  judged at slice verification, where the manual pass checks the requirements page at 1024 to
  1280px and zoomed, before a cap or a later breakpoint is chosen.
- **Fix by:** S3-C33 (slice verification's manual pass)
- **Status:** open

### TD-109: A dialog opened from the panel may stop being modal when the window crosses 64rem
- **Added:** S3-C0d
- **What:** Change restriction…, Delete…, and Request approval are `<dialog>`s inside the side
  panel's teleported content. If one is open when the window crosses 64rem, the move takes it
  out of the top layer: by the HTML spec it stays open but isn't modal any more, so the page
  behind isn't inert and its Esc may reach the panel instead (ui-reviewer, S3-C0d pass 2).
- **Why:** unconfirmed: it needs a real browser to see what happens, and crossing the width with
  a dialog open (a tablet turned, a zoom) is rare; the fix, if needed, is to close or reopen the
  nested dialog on the breakpoint change.
- **Fix by:** S3-C33 (the manual pass checks it at 1024px; fixed in the slice if it shows)
- **Status:** open

### TD-110: Focus on the trail's "…" or a middle crumb drops when the window crosses 40rem
- **Added:** S3-C0e
- **What:** the fold and the middle crumbs switch with CSS at 40rem (UI-SHL-14), so a resize or
  zoom across it while one of them has focus hides that control and focus falls to `<body>`.
- **Why:** it needs a resize while focus is on that one control; a fix (focus the nearest shown
  crumb when the media query flips) adds a listener to every page for a rare case (ui-reviewer,
  S3-C0e, note).
- **Fix by:** S3-C33 (the manual pass zooms across 40rem with focus on the trail; fixed if it
  shows)
- **Status:** open

### TD-113: UI-SVR-3 doesn't say SVAR's stylesheet must be imported, or that Willow's icons go blank
- **Added:** S3-C0i
- **What:** the S3-C0i spike found that a SVAR widget draws unstyled unless its own stylesheet
  (`@svar-ui/vue-grid/all.css`, and each widget's) is imported before our mapping, and that
  `<Willow :fonts="false">`, which UI-SVR-3 requires, also leaves out Willow's icons (an icon
  font from SVAR's CDN, which UI-STY-4 rules out), so a wrapper draws its own (in the spike, the
  grid's drag handle; for the board, any Willow icon its card shows). UI-SVR-3 says neither, and the first SVAR wrapper would find both again.
- **Why:** a rule change, outside a spike's scope (checkpoint-reviewer, S3-C0i, minor).
- **Fix by:** S3-C18 (the first SVAR wrapper, the board): UI-SVR-3 gains both, and the board's
  Willow icons are checked
- **Status:** open

### TD-114: No e2e opens a popover past eight links from the keyboard
- **Added:** S3-C0j
- **What:** the project selector and org menu show a **Filter** button past eight links
  (UI-SHL-6). Its spec opens one, runs axe, and checks focus; no e2e opens one from the keyboard,
  as `frontend/CLAUDE.md`'s overlay rule asks, because the e2e stack's demo data has no org with
  more than eight projects (`--manual-pass`'s `acme` has eleven).
- **Why:** the e2e stack counts what `--demo` builds; growing it means reworking its counts
  (ui-reviewer, S3-C0j, a coverage gap).
- **Fix by:** S3-C33 (slice verification's manual pass on `--manual-pass`), or the first e2e
  that needs a bigger org
- **Status:** open

---

## Resolved

### TD-1: pre-commit has no frontend or generated-file hooks
- **Added:** S0-C1
- **Status:** resolved in S0-C7 (Prettier and ESLint hooks on the frontend; `openapi-fresh` and
  `client-fresh` hooks fail when a generated file differs from what `wl gen-client` produces)

### TD-2: The 100% authz/rules coverage gate runs only through `wl`
- **Added:** S0-C1
- **Status:** resolved in S1-C3 (a `pytest_runtestloop` hook in `tests/conftest.py` fails the
  session below 100% for `app/authz/` and `app/rules/`; the CLI's separate `coverage report`
  step is gone, so `uv run pytest` and `wl backend test` give the same result)

### TD-3: A service cycle through `jobs/` isn't caught by import-linter
- **Added:** S0-C1
- **Status:** resolved in the Claude configuration change after S0-C2: the service layers
  contract checks import chains through any module, so a lower service reaching a higher one
  through `jobs/` breaks it (`lower-service-reaches-higher-through-jobs` in
  `tests/unit/test_import_contracts.py`).

### TD-4: The concurrency fixture can't yet support real race tests
- **Added:** S0-C2 (reopened at S0-C4)
- **Status:** resolved in S1-C2 (`run_in_parallel` with a start barrier and a time limit; a
  concurrency engine with a 25-connection pool and `lock_timeout`; `committing_factories`; an
  empty-tables check after every concurrency test, with a wiring test run in its own pytest
  process; the allocation race tests fail against a read-then-write allocator)

### TD-5: Factories generate random strings, not realistic fake values
- **Added:** S0-C2
- **Status:** resolved in S1-C1 (every model factory sets realistic Faker values: names,
  lowercase emails, slug-format usernames and slugs, project keys; tested in
  `tests/integration/test_factories.py`)

### TD-6: No gated check that `env.py` applies the autogenerate filter
- **Added:** S0-C4
- **Status:** resolved in S0-C5 (`test_models_and_migrations_have_not_drifted` runs
  `alembic check` through `env.py`; removing the filter fails it)

### TD-7: `direct_update` moves `updated_at` for rank writes
- **Added:** S0-C5
- **Status:** resolved in S0-C6 (`direct_update(..., touch_updated_at=...)`, a required
  keyword; tests for both rank and counter writes)

### TD-8: `session.get()` returns an object soft-deleted in the same session
- **Added:** S0-C5
- **Status:** resolved in S1-C1 (`get_by_id` in `app/repositories/base.py` always queries;
  tested against an object soft-deleted earlier in the same session)

### TD-9: Unhandled exceptions return a plain-text 500
- **Added:** S0-C6
- **Status:** resolved in S0-C7 (`UnhandledErrorMiddleware` in `app/core/errors.py`: 500
  `internal_error`, logged with its traceback; tests in `tests/api/test_errors.py`)

### TD-10: Pinia is installed but not yet proven wired
- **Added:** S0-C7
- **Status:** resolved in S1-C14 (`main.ts` mounts `createWaterlineApp()`, and
  `src/app/router.spec.ts` "resolves the current-user store through the Pinia instance it
  installs (TD-10)" signs in through that app and reads the store from its Pinia)

### TD-11: Dev containers run as root
- **Added:** S0-C7
- **Status:** resolved in S1-C17 (the tooling change DC-2026-10-21c, before its commit)

### TD-15: No branch protection on `main`
- **Added:** S0-C8
- **Status:** resolved in DC-2026-10-08b (the repository is public; GitHub rulesets require a
  pull request with a green `wl check` on `main`, and block force-pushes and deletion on every
  branch, DL-27)

### TD-16: The service-layer contract doesn't list `my_work`
- **Added:** journey decisions (Oct 7, 2026)
- **Status:** resolved in S1-C11 (`(my_work)` is in the layer-1 entry)

### TD-18: No property-based test for number allocation yet
- **Added:** S1-C2
- **Status:** resolved in S1-C3 (`test_any_interleaving_numbers_each_sequence_1_2_3`; an
  allocator that ignores the prefix fails it)

### TD-21: A user-level audit event's workspace is null when it's ambiguous
- **Added:** S1-C6
- **Status:** resolved in DL-48: left as it is until a second workspace is needed (the owner,
  after S1-C7), when the rules for several workspaces are decided (design-doc §4)

### TD-22: The spec tests check list scoping through their own copy of `scope_clause`
- **Added:** S1-C7
- **Status:** resolved in S1-C8 (the spec test uses `scope_clause`, and `scope_filter` is gone;
  owner-approved)

### TD-23: A race on the staff add reports its error on `user_id`
- **Added:** S1-C8
- **Status:** resolved in S1-C15 (the add race in S1-C12: `already_member` on the field the
  request used, `email` or `user_id`, through `Roster.add_user`'s `loc`, DL-80). The web forms
  read a field error by the end of its `loc`, so the nested create's race lands on the right field
  either way: the create-org dialog sends a bare `email` or `username` to the new owner's fields,
  with a test for each location

### TD-24: An intermittent Hypothesis error in an identifier property test
- **Added:** S1-C8
- **Status:** resolved in S1-C10 (it didn't recur in S1-C8a to S1-C10: closed with that note)

### TD-25: A rare deadlock between a staff change and an owner being added
- **Added:** S1-C8a
- **Status:** resolved in S1-C9 (staff and org members share one roster, `services/roster.py`;
  adding an owner takes the owners' lock first, proven by
  `test_adding_an_owner_queues_behind_a_change_holding_the_owners_lock`)

### TD-26: A no-op role change ignores `new_owner_id`, even an invalid one
- **Added:** S1-C8a
- **Status:** resolved in S1-C15: the role dialog sends nothing when the role is unchanged, so
  `new_owner_id` never travels with a no-op (`ChangeRoleDialog.spec.ts`, sabotage-checked)

### TD-27: Deactivation must wait behind a handover
- **Added:** S1-C8a
- **Status:** resolved in S1-C10 (a deactivation locks the owners of every workspace and org the
  user belongs to before its guard, proven by
  `test_a_deactivation_queues_behind_a_handover_to_the_same_person`)

### TD-30: Older race tests assert inside their task group
- **Added:** S1-C11
- **Status:** resolved in S1-C12 (`refusal()` and `refusal_types()` in
  `tests/support/concurrency.py` record a task's refusal as a value; the account, workspace, and
  auth race tests use them, and the versioning race test records its outcome with `suppress`; each
  asserts after its task group closes)

### TD-32: No page handles a 404 yet
- **Added:** S1-C14
- **Status:** resolved in S1-C14a: the project home shows the not-found page for an API 404, and
  an org page for an org slug the user doesn't see

### TD-33: A failed sign-out from the header says nothing
- **Added:** S1-C14
- **Status:** resolved in S1-C14a: the user menu's (and the no-access page's) sign-out reports a
  failure in an alert (`useSignOut`)

### TD-34: The new-password help can't show the minimum length
- **Added:** S1-C14
- **Status:** resolved in S1-C14a: `GET /api/auth/password-policy` and `PasswordRequirements`, on the
  forced change and account settings

### TD-35: The pending spinner's speed isn't a token
- **Added:** S1-C14
- **Status:** resolved in DL-92: a guide exception (UI-TOK-7); the spinner keeps `animate-spin`,
  to revisit if more animations need it

### TD-36: Route focus also moves on a query-only navigation
- **Added:** S1-C14
- **Status:** resolved in S1-C14a: a query-only navigation moves neither focus nor the title; the list
  announces its count instead

### TD-39: No `PageHeader` component yet
- **Added:** S1-C14a
- **Status:** resolved in S1-C15: `PageHeader`, on the admin pages and the earlier pages (My work,
  an org's projects, account settings, no access, sign in, change password). The project home
  keeps its project header (UI-SHL-6), and the status and not-found pages their own headings

### TD-40: An unavailable My work section fails the whole page
- **Added:** S1-C14a
- **Status:** resolved in S2-C14: each section's query runs in its own savepoint
  (`MyWorkService._section`), and the page gives the projects section its own error state, keyed
  on its failed loads in a row of either kind (the request or the section), so another section's
  failure leaves it showing

### TD-43: The two settings forms repeat their save handling
- **Added:** S1-C15a
- **Status:** resolved in S1-C16a

### TD-44: The first-admin picker lists only the org's members
- **Added:** S1-C16 (DL-112)
- **Status:** resolved in S2-C0c

### TD-45: The project header doesn't mark a deactivated lead
- **Added:** S1-C16
- **Status:** resolved in S1-C16a

### TD-46: The other create dialogs don't reload `/me` after a 403
- **Added:** S1-C16
- **Status:** resolved in S1-C16b

### TD-47: The older dialogs' alerts drop focus when dismissed
- **Added:** S1-C16a
- **Status:** resolved in S1-C16b

### TD-48: A change to export control made elsewhere isn't picked up by an open add dialog
- **Added:** S1-C16b (checkpoint review question)
- **Status:** resolved in S1-C16c

### TD-49: A project page's actions aren't in its header
- **Added:** S1-C16b (ui-reviewer note, UI-SHL-8)
- **Status:** resolved in S2-C0g (`ProjectHeader`'s actions slot, beside the `h1`)

### TD-50: Two other dialogs' last step isn't read with Done
- **Added:** S1-C16c (DL-118)
- **Status:** resolved in S1-C16d

### TD-51: The password reset's last step doesn't say the reset happened
- **Added:** S1-C16d (ui-reviewer note)
- **Status:** resolved in S2-C0h ("Password reset for <name>." read with Done)

### TD-52: No length limit on names and descriptions
- **Added:** S1-C17 (repo-auditor)
- **Status:** resolved in S2-C0c

### TD-53: The routers' error-response map is written out four times
- **Added:** S1-C17 (repo-auditor)
- **Status:** resolved in S2-C0c

### TD-54: Re-wrapping a page of rows is repeated five times
- **Added:** S1-C17 (repo-auditor)
- **Status:** resolved in S2-C0c, as `PageResult.with_items(rows)`: the roster builds its rows
  with one `await` over the page, which a per-item function can't

### TD-55: `anyio` is used by the app but declared only for development
- **Added:** S1-C17 (repo-auditor)
- **Status:** resolved in S2-C0c

### TD-56: A settings save sends every field, undoing another admin's change
- **Added:** S1-C17 (repo-auditor A1)
- **Status:** resolved in S2-C0h (`NameSlugSettings`, `ProfileForm`, and project settings' details send only what changed)

### TD-57: An update's change check reads an unlocked row
- **Added:** S1-C17 (repo-auditor A2)
- **Status:** resolved in S2-C0c

### TD-58: Removing the last row of the last page leaves an empty page
- **Added:** S1-C17 (repo-auditor A3)
- **Status:** resolved in S2-C0g (`useListQuery`'s `returnWhenEmpty`, on every paged list)

### TD-59: The username suggestion is copied in two dialogs
- **Added:** S1-C17 (repo-auditor A4)
- **Status:** resolved in S2-C0h (`useUsernameSuggestion`, in `NewAccountFields`)

### TD-60: The docs name per-area policy files; Slice 1 built one registry
- **Added:** S1-C17 (docs-consistency)
- **Status:** resolved in S2-C0c

### TD-61: The token contrast check runs only by hand
- **Added:** S1-C17 (docs-consistency)
- **Status:** resolved in S2-C22 (a docs consistency test runs `check_contrast.py` on the app's `tokens.css` in `wl check`)

### TD-62: The completed screen inventory isn't checked against the docs and built screens
- **Added:** S1-C17 (docs-consistency)
- **Status:** resolved in DC-2026-10-31: step 6's Built rows match the router; the items with no
  slice (DL-197, DL-200, DL-201) placed by the owner (DL-238, DL-239); the web rows' own re-cuts
  stay at each row's start (DL-139)

### TD-65: A project update locks its row twice
- **Added:** S2-C0c (checkpoint-reviewer)
- **Status:** resolved in S2-C22: kept as is, accepted (owner, S2-C22 tech-debt review, Nov 8, 2026); no other caller needs a non-locking `apply_changes`

### TD-66: "None" for a missing role is written in two views
- **Added:** S2-C0g (ui-reviewer finding 3's siblings)
- **Status:** resolved in S2-C22 (`NO_ROLE` from `labels.ts` in the per-project access review)

### TD-67: A drop between two tied ranks has no rank to take
- **Added:** S2-C2 (spec-test-writer question)
- **Status:** resolved in S2-C7

### TD-69: Ranks have no maximum length
- **Added:** S2-C2 (security-reviewer finding 1)
- **Status:** resolved in S2-C7

### TD-71: Creating a child doesn't hold its parent
- **Added:** S2-C5
- **Status:** resolved in S2-C8 (the parent held `FOR SHARE`; a delete locks a level of the
  subtree before reading the next, so a child created under a locked row is seen or waits)

### TD-72: The reporter and the restriction floor are checked without a lock
- **Added:** S2-C6
- **Status:** resolved in S2-C8 (the new reporter's user row and memberships held `FOR SHARE`;
  the project row held `FOR KEY SHARE`, not `FOR SHARE`, which would make every create wait on
  a move's tree lock, against DL-214; a raise's `FOR UPDATE` still conflicts with it; the
  export-control marking is TD-74)

### TD-74: A new reporter's inherited admin isn't held against marking the project export-controlled
- **Added:** S2-C8
- **Status:** resolved in S2-C12 (checkpoint-reviewer pass 2): the edit holds the project, then
  builds its target, so the reporter check sees the restriction a change committed meanwhile;
  race test `test_a_reporter_change_waiting_on_marking_export_controlled_refuses_an_inherited_admin`

### TD-75: `ListSpec.soft_deleted` and `?include_deleted` have no user
- **Added:** S2-C8 (checkpoint-reviewer finding 4)
- **Status:** resolved in S2-C22 (`soft_deleted` and `?include_deleted` removed with their tests; the trash keeps its own query)

### TD-77: The reporter and the trash's deleter carry no "deactivated" flag
- **Added:** S2-C9 (checkpoint-reviewer finding 1)
- **Status:** resolved in S2-C21 (`reporter_is_active` in S2-C18: `RequirementRead` carries it,
  and the requirement's page shows "Deactivated" after the reporter's name; `deleted_by_is_active`
  in S2-C21: `TrashItem` carries it, and the Trash page shows "Deactivated" after the deleter's
  name)

### TD-78: Each authorization spec test spells out every action a role holds
- **Added:** S2-C10 (owner, chat)
- **Status:** resolved in S2-C11 (`EXPECTED` and `project_actions` in `tests/support/authz.py`;
  the seven tests derive their lists from it, and `test_actions.py` checks each registered action
  against its row; owner-approved)

### TD-80: Deleting re-checks the rule against the project as first loaded
- **Added:** S2-C10 (security-reviewer finding 1's sibling)
- **Status:** resolved in S2-C22 (`lock_tree` reads the project row again, and create, edit, a restriction change, and move check their right again after the hold or the tree lock, as delete and restore do; a race test of each against marking the project export-controlled)

### TD-81: The replacement reads the requester's and approvers' access without holding it
- **Added:** S2-C12
- **Status:** resolved in S2-C13: every path that takes access away locks the projects of the
  person's pending rows and requests first (`ApprovalService.lock_projects`), so a replacement
  there waits for the change: `test_a_request_naming_someone_and_their_deactivation_never_deadlock`
  (the lock first) and `test_an_approvers_removal_waiting_on_the_requesters_org_removal_reads_them_gone`
  (the requester's projects in it)

### TD-82: A decision is checked against the approver's access as the request found it
- **Added:** S2-C12 (security-reviewer finding 2)
- **Status:** resolved in S2-C22 (`decide` loads the approver's whole authorization context again under its locks and refuses a deactivated account; race tests of a project removal, an org role change, a deactivation, and revoking system admin first)

### TD-85: A refused move can't tell the page to reload
- **Added:** S2-C15 (ui-reviewer finding 4)
- **Status:** resolved in S2-C17 (the tree emits `stale` on a 404 or 422 and `refused` on a
  403; the requirements page reloads the tree or the project, and the refusal stays, with focus
  on it if the move menu went)

### TD-88: The markdown components haven't been checked in a browser
- **Added:** S2-C16 (ui-reviewer findings 5 and the coverage gaps)
- **Status:** resolved in S2-C17a (the create dialog's end-to-end spec, both themes: axe on the
  form and on the rendered Preview, link-in-text-block and contrast included; the theme audit on
  the tabs and the rendered markdown; the selected tab's bar under forced colors; no sideways
  scroll at 320 px with a long address and a table. The task-list checkbox was replaced by a mark
  drawn in tokens, named "Done" or "Not done", rather than measured: the browser's disabled look
  isn't reachable by our tokens)

### TD-90: The members page's refused reload leaves focus on a first visit
- **Added:** S2-C17 (ui-reviewer pass 2, finding A's sibling)
- **Status:** resolved in S2-C22 (`replacedPage()` in `routeFocus.ts`, used by the members page, `RosterPage`'s refusal, `UsersView`'s refusal, and `RequirementDetail`'s `editGone`, with first-visit specs; UI-SHL-9 and `frontend/CLAUDE.md` say when)

### TD-91: A description's headings sit one level below the page's h1, not below its section
- **Added:** S2-C18 (ui-reviewer note)
- **Status:** resolved in S2-C20a (`MarkdownView`'s `level`; the requirement page passes
  `:level="2"`, so a description's `#` is an `h3` under "Description"); closed in S2-C22 by the
  owner

### TD-92: Closing the side panel drops an open edit
- **Added:** S2-C18b
- **Status:** resolved in S3-C0d: Close, Esc, Back, another item's ID, and Open full page ask
  **Discard your changes?** first (DL-323)

### TD-93: Expand all may not be the right action for the tree
- **Added:** DC-2026-11-04b (DL-270)
- **Status:** resolved in S2-C18c ("Expand requirement" in place of "Expand all", DL-271, DL-272)

### TD-94: "Expand requirement" announces nothing when it opens the whole branch
- **Added:** S2-C18c (ui-reviewer, minor)
- **Status:** resolved in S2-C22 (the owner: build it; the note says "Opened all 12 rows under
  PMT-RQ-1.", or "Opened 1 row under …")

### TD-95: Revisions' default From misses an approved revision past the first page
- **Added:** S2-C19a
- **Status:** resolved in S2-C20 (Revisions takes the approved revision's number from the
  requirement's read)

### TD-99: A row action's network failure has no Retry
- **Added:** S2-C21c
- **Status:** resolved in DC-2026-11-09-s2-retro-and-ui-polish (UI-FRM-7: a row or inline
  action's control is its own retry, DL-319)

### TD-103: TextField's slot shadows its `describedBy` prop
- **Added:** S2-C22 (CI lint warning, Slice 2 retro)
- **Status:** resolved in S3-C0a (the slot's IDs are `ids`, as in `PasswordField.vue`)

### TD-105: A project key's API error messages describe a slug
- **Added:** S3-C0c
- **Status:** resolved in S3-C0l: a key's 422 has its own messages (`PROJECT_KEY_MESSAGES`: at
  least 3, at most 6, only letters and digits)

### TD-106: The requirement's header has no Parent row yet
- **Added:** S3-C0d
- **Status:** resolved in S3-C0e: Parent (its ID linked, then its title; None at the top level),
  from the read's `ancestors` (DL-357)

### TD-111: No test loads a bundled guide image under the CSP
- **Added:** S3-C0g
- **Status:** resolved in S3-C0h: `csp.spec.ts` opens a guide page's screenshot, in each theme
  and with the theme chosen against the system's, and asserts it loads with no CSP violation

### TD-112: SidebarLink's transparent bar draws on every link under forced colors
- **Added:** S3-C0g
- **Status:** resolved in S3-C0j: the bar only on the current link, the others padded by its
  width; `shell.spec.ts` checks under forced colors that only the current link has it
