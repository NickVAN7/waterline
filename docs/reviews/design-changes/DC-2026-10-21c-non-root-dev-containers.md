# Review record: DC-2026-10-21c — non-root dev containers (TD-11)

- **Change:** tooling (DL-18), the owner's TD-11 decision at S1-C17 ("add a non-root user"): the
  backend and frontend dev images run as a non-root user with the host's user and group IDs
  (`HOST_UID`, `HOST_GID` build arguments, defaulting to 1000), which `wl` passes from the host
  (`subprocess_env`); and `wl up` creates `frontend/node_modules` as the developer before Docker
  would create that mount point as root. Built while S1-C17 was parked (DL-20); the docs it
  changes (the developer guide's setup and troubleshooting notes, TD-11) follow in the S1-C17
  commit, where they were parked.
- **Base commit:** `0ea55d2`
- **Files:** `backend/Dockerfile`, `frontend/Dockerfile`, `docker-compose.yml`,
  `tools/cli/src/waterline_cli/runner.py`, `tools/cli/src/waterline_cli/steps.py`,
  `tools/cli/tests/test_runner.py`, `tools/cli/tests/test_commands.py`
- **Reviewers:** `checkpoint-reviewer`, two passes (the first had a major finding fixed).
- **Totals:** 3 findings (1 blocker, 2 major): 2 fixed, 1 in the S1-C17 commit (docs).
- **Gates:** `uv run wl check` green (tooling 759 tests, 100% coverage); `uv run wl e2e` green
  (72, on the new images built through `wl`).

---

## Checks by the implementing session

- The dev stack rebuilt and healthy; `id` in the api and web containers is the host's (1000:1000);
  a file the web container writes into the mount is the developer's on the host; `/app/node_modules`
  is `node`'s, so Vite writes its cache.
- Both images built with `HOST_UID=1001 HOST_GID=1001` (another runner's IDs): the users take them.
- Sabotage: each `setdefault` removed from `subprocess_env` → caught (`test_runner.py`).

## checkpoint-reviewer, pass 1 (base `0ea55d2`) — verdict: ready after fixes

| # | Severity | Area | Location | Finding | Resolution |
|---|---|---|---|---|---|
| 1 | major | docs | `docker-compose.yml` (the anonymous `node_modules` volume), the developer guide, TD-11 | **What:** Docker, as root, creates the volume's mount point `frontend/node_modules` on the host owned by root when `wl up` runs before the host's `npm ci`; the image's user doesn't change that (reproduced). **Fix:** keep the guide's notes and resolve TD-11 only in part, or have `wl up` create the folder first. | **Fixed:** `wl up` runs `mkdir -p frontend/node_modules` first; its dry-run test updated. |

**Sabotage checks:** a set `HOST_UID` overwritten → caught; `HOST_GID` from `getuid` → caught.
Also built both images with `HOST_UID=1234 HOST_GID=20` (a group Debian already has): both take
the IDs, `node_modules` writable, Vite starts.

## checkpoint-reviewer, pass 2 (re-review, the fix diff) — verdict: ready after fixes

The `mkdir` step resolves pass 1's finding (run from the repo root, as the host user, before
Compose; `node_modules/` is ignored by git). **Sabotage check:** the step removed → caught.

| # | Severity | Area | Location | Finding | Resolution |
|---|---|---|---|---|---|
| 2.1 | blocker | conventions | `steps.py` | **What:** a missing trailing comma fails `ruff format --check`. | **Fixed:** `wl fmt` (no further pass, DL-105). |
| 2.2 | major | docs | the developer guide (setup's "before `wl up`", the root-owned paragraph, the `EACCES` row), TD-11 | **What:** they describe the problem the fix removes. | **In the S1-C17 commit**, where those docs were parked: the ordering note and paragraph go, the row covers only a folder made as root before this change, TD-11 resolved. |
