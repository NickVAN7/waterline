# Review record: Slice 1 plan — readiness review (Sept 30, 2026)

Decisions from the owner's Slice 1 readiness review, applied to the repository docs as a design
change outside a checkpoint (build plan, "Design changes outside a checkpoint"). The edits are
in `build-plan.md` (the Slice 1 section, the slice overview, implementation decisions 9–10,
"API conventions", the feature map and cross-area rules, the repository layout, tooling),
`design-doc.md` (revision note 5, §3, §4, §5, §10.1), `schema-doc.md` (`user`, slugs, the ERD,
`audit_event`, known limitations), `testing-strategy.md`, and `tech-debt.md` (TD-12, TD-13).

## Fixes (gaps and inconsistencies in the Slice 1 section)

| # | Fix |
|---|---|
| F1 | `must_change_password` gate exempts `GET /api/auth/me`, change-password, and sign-out |
| F2 | `authorize()` checks the archived project first (denies mutations even for system admins); unarchive is the one exception |
| F3 | Web screens added: org settings (rename, slug), reactivate and sign-out-everywhere on the users page, account actions on the org members page, role changes on the staff page |
| F4 | Username is part of the account-creation form (design-doc §4 listed only name and temporary password) |
| F5 | End-to-end tests (Playwright) are in the Slice 1 section and its "Done when", with CI running them against a seeded stack |
| F6 | `wl seed` has a non-interactive mode and refuses to run when a workspace exists |
| F7 | Module gating is tested through a test-only gated router in `tests/support/` |
| F8 | Module guidance's "holds data" warning goes through a per-module hook (returns false until the module's slice ships) |
| F9 | The rank rule for account actions is a pure function in `rules/` (test-first, 100% coverage, mutation-tested) |
| F10 | Emails are stored lowercase and compared case-insensitively; a CHECK enforces lowercase |

## Decisions

| # | Decision |
|---|---|
| D1 | System admin is granted and revoked only by app CLI commands (`grant-system-admin`, `revoke-system-admin`), with the last-active-system-admin guard; no UI |
| D2 | Removing an org member (or workspace staff) offers to also remove their project memberships in that org (for staff: in the workspace), checked by default |
| D3 | Org and workspace slugs can't use a reserved list of top-level browser routes; a test checks every top-level route is reserved |
| D4 | No email-change feature in v1; the fallback is a manual database edit (the lowercase CHECK applies) |
| D5 | Production cookie settings (`__Host-session`, `Secure`) in every environment; no insecure-cookie switch. API tests use an `https://` base URL; Playwright runs Chromium only in v1; the dev server is reached at `localhost`. Safari/WebKit coverage and local HTTPS are logged as tech debt (TD-13) |
| D6 | Mutating requests without an `Origin` header are rejected. **Superseded in part** (see "Applied with changes"): the check compares `Origin` with the request's `Host` (no allowed-origins setting), per the owner's decisions after S0-C7 |
| D7 | A separate, workspace-scoped `audit_event` table records admin and security events, written by `log_admin_event()`, built in Slice 1, with no screen yet. `activity_log` stays project-scoped work history |

## Conventions (set in Slice 1, copied by every later slice)

| # | Convention |
|---|---|
| C1 | Lists: offset paging by default (`limit`/`offset`, `{items, total, limit, offset}`), cursor paging for append-only feeds, ranked views unpaged with a cap; sort allowlist with `id` tiebreaker; declared, typed filters combined with AND (OR within a field) from one filter bar; unknown query parameters → 422; scoping before paging |
| C2 | Uniqueness, CHECK, and user-triggerable FK violations → 422 with field details; service pre-check plus database constraint translated through a constraint-name registry; unmapped `IntegrityError` → 500 |
| C3 | Single-entity reads carry `allowed_actions` evaluated through `authorize()`; action names exported as an OpenAPI enum; per-request authorization context; per-row actions only where needed (member lists); data-dependent rules get their own fields; actions not allowed are hidden, not disabled |
| C4 | Project items by key and number; orgs and users by UUID; memberships by scope plus user; `/api/workspaces/{workspace_id}` (plural); bodies reference entities by UUID; browser URLs keep the org slug |
| C5 | Sign-in: one `invalid_credentials` error with a dummy-hash check for unknown emails; `account_inactive` only after a correct password; emails lowercased; sign-in response has the `/me` shape; hashes upgraded on sign-in. Password policy: 8–256 characters (raise the minimum to 12 before the first non-local deployment), no composition rules, not the email or username, new differs from current; no breached-password check for now |

## Applied with changes

The plan was written against the Project's copy of the docs; the repository was ahead of it.

1. **`Origin` check (D6, plan §4.6, §3.7, Checkpoint 5).** The owner's decisions after S0-C7
   (committed in `bc4dc34`: `Origin` host and port compared with the request's `Host`, no
   allowed-origins setting, the exemption list, `origin_rejected` / `unsupported_media_type`,
   the check order, fail-closed cases, no state-changing `GET`) were kept. **Owner decision:**
   keep the `Host` comparison, and re-evaluate it against an allowed-origins setting once the
   application and API are more mature (added to design-doc §4, "Before the first non-local
   deployment"). So: the plan's CSRF replacement text (§4.6) was not applied, only its
   additions; the Docker Compose note on allowed origins (§3.7) was not added; Checkpoint 5
   and the Slice 1 "Authentication" bullet describe the `Host` comparison.
2. **Tech-debt numbers.** TD-9 to TD-11 were already taken, so the plan's TD-9 and TD-10 are
   **TD-12** (password minimum) and **TD-13** (Chromium only, no local HTTPS).
3. **Tech-debt deadlines.** The log accepts only a checkpoint or slice as "Fix by" (the docs
   consistency tests check deadlines). **Owner decision:** TD-12 and TD-13 target **Slice 7**
   (before the first non-local deployment, and by the end of v1 at the latest; re-targeted if
   deployment moves later).
4. **Carry-in list.** TD-10 (Pinia wiring, owner decision after S0-C7) and TD-11 (root dev
   containers) are also due in Slice 1: TD-10 lands in Checkpoint 13 with the current-user
   store; TD-11 is the owner's decision at Checkpoint 16.
5. **Testing strategy.** The plan's "Mutations without an `Origin` header are rejected" was not
   added separately: the existing `Origin`-check bullet already lists that case with its tests.

## Developer-guide notes (added by the Slice 1 checkpoints that introduce them)

- **Reach the dev server at `localhost`.** The session cookie is `Secure`; browsers only accept
  it over plain HTTP on `localhost`/`127.0.0.1`. A LAN IP or custom hostname breaks sign-in
  (TD-13). (Checkpoint 5)
- **API tests use the shared client fixture** (`https://testserver`); an `http://` base URL
  makes signed-in tests silently unauthenticated. (Checkpoint 5)
- **Changing a user's email** (no feature in v1): update `user.email` directly in the
  database, in lowercase (a CHECK rejects anything else). (Checkpoint 1)
- **Seeding non-interactively** and the **system-admin commands** (`grant-system-admin`,
  `revoke-system-admin`). (Checkpoint 6)
- **Backend layout:** `audit/` gains `log_admin_event()` in Slice 1 (`log_change()` still
  arrives in Slice 2). (Checkpoint 4)

## docs-consistency passes

### Pass 1 (base `bc4dc34`)

**Fixes** (all applied)

| # | Where | Finding | Resolution |
|---|---|---|---|
| 1 | build plan, "Naming" | "UUIDs stay internal" contradicted "Identifiers" | **Fixed:** the bullet covers project items and points to "Identifiers" |
| 2 | security reviewer, check 1 | Forced-change exemptions missed `/me` and the error code; `account_inactive` ordering missing | **Fixed** |
| 3 | security reviewer, check 3 | `authorize()` order lacked the archive check first | **Fixed** |
| 4 | backend/CLAUDE.md, design-doc §5, build plan | `log_admin_event()` missing from the mutation order and single-writer rules | **Fixed** |
| 5 | schema-doc, known limitations | "No screen in v1" vs "before the first non-local deployment" | **Fixed:** "no screen yet" |
| 6 | design-doc §4 | Password re-entry listed "changing email", which v1 doesn't have | **Fixed:** "once that feature exists" |
| 7 | build plan, Slice 1 "Done when" | "The viewer sees it but not its settings" contradicted §5 | **Owner decision 8** below |
| 8 | build plan, Checkpoint 5 row and "Projects" | "C5" and "C2" read as checkpoint numbers | **Fixed:** section references |
| 9 | build plan, Checkpoint 12 row | "End-to-end tests" before Playwright exists | **Fixed:** API tests |
| 10 | build plan, feature map | `project` row missed its `on_member_removed` registrations | **Fixed** |
| 11 | `new-area` skill | Didn't mention the API conventions | **Fixed:** a scope step points to them |
| 12 | developer guide, backend layout | `audit/` will gain `log_admin_event()` | **Deferred to Checkpoint 4** (the guide describes what's built); added to the notes above |

**Owner decisions** (all as recommended)

1. **Constraint 422s** use the S0-C6 shape: `validation_error`, `details.fields` entries
   `{loc, message, type}` (e.g. `type: "taken"`). Build plan, "Errors from constraints".
2. **Removing a member with their projects** also removes memberships on archived projects: a
   second exception to the archive check (design-doc §5, build plan, security reviewer).
3. **Audit events:** a user-level event carries the workspace it happened in, and the org when
   the actor acted as that org's owner/admin (design-doc §10.1, schema-doc); the seed records
   `workspace_created` (new action value), `user_created`, `system_admin_granted`, and
   `workspace_member_added`; Slice 1 has no read endpoint (SQL only).
4. **Security review** for Slice 1 Checkpoints 1–15; the `checkpoint` skill's trigger adds
   `rules/account_rank.py` and `rules/password_policy.py`.
5. **Pre-deployment items** in design-doc §4 are tracked by TD-14 (Slice 7).
6. **Reserved slugs:** the list is exported through the OpenAPI schema and a frontend test
   checks the router's top-level routes against it; workspace slugs are reserved only to keep
   root-level workspace URLs possible (design-doc §3, Checkpoint 13).
7. **System-admin commands** run as `wl admin <command>`, a pass-through to the app CLI (build
   plan CLI table and "Authentication"; root `CLAUDE.md`).
8. **Viewers** can't change project settings (restored), matching design-doc §5.

### Pass 2 (base `bc4dc34`, after pass 1's fixes and decisions)

**Fixes** (all applied)

| # | Where | Finding | Resolution |
|---|---|---|---|
| 1 | build plan, Slice 1 "Before starting" | Read as an open precondition, though TD-1, TD-7, and both Claude files are done | **Fixed:** marked as met |
| 2 | build plan, repository layout and "Developer CLI" | The app CLI was invoked only by `wl seed` | **Fixed:** `wl admin <command>` and the system-admin commands added |
| 3 | design-doc §10.1 "What's recorded" | Missed workspace creation (`workspace_created`) | **Fixed** |

**Decisions for the owner** (open; not needed until the Slice 1 checkpoints named)

1. **Security review on Slice 1 checkpoints whose diff misses the skill's trigger** (likely
   C2, C3's `identifiers.py`, C4, C13–C15): (a) the skill and agent also run it when the
   slice's section lists the checkpoint; (b) widen the skill's path list; (c) narrow the build
   plan to the skill's trigger (contradicts owner decision 4).
2. **Membership removals on archived projects:** (a) keep only the two exceptions and reword
   the rationale; (b) also allow a project admin's direct member removal; (c) allow any
   reduction of access (removal or demotion). Needed by Checkpoint 7.
3. **"New password differs from the current one" on admin resets:** (a) self-change only; (b)
   also admin resets (one more Argon2 verification). Needed by Checkpoint 3.
4. **Feed paging by `id` or by event time:** (a) page by `id` and index `(scope, id)`; (b)
   order by the time column with a `(time, id)` cursor; (c) keep both. Needed by Checkpoint 1
   (indexes) and 4 (cursor helper).
5. **When TD-2 is fixed:** (a) Checkpoint 3, rewording TD-2's "Fix by"; (b) Checkpoint 7,
   moving it in the build plan. Needed by Checkpoint 3.
