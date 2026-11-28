"""S3-C0n (DL-374, DL-380): set up the Impeccable trial in a scratch directory.

    python3 docs/spikes/S3-C0n-impeccable/setup.py <empty directory>

Makes `<dir>/remote.git`, a bare copy of this repository standing in for GitHub (nothing the trial
pushes leaves the machine), and `<dir>/waterline`, a clone of it on a new `trial` branch from this
repository's current branch. In the clone only:

- its own Compose project and ports (`.env`), so its stack runs beside the dev stack;
- the Impeccable settings Claude Code's sessions and hooks get (`.claude/settings.local.json`'s
  `env`): telemetry, update checks, and live mode's copy-edit agent off, the engine's cache inside
  the clone, the detector's browser;
- `.gitignore` entries for Impeccable's state, and `connect-src`/`script-src` for live mode's
  server (`http://localhost:8400`) in `frontend/vite.config.ts`'s CSP, committed on `trial`;
- the trial's screenshot spec (`trial.shot.ts`) and the frontend and backend dependencies.

It installs nothing from Impeccable: the plugin is installed by the owner afterwards, from the
clone (README, "Set up"), which is the consent to its hooks.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]

LIVE_ORIGIN = "http://localhost:8400"
# The commit tag skill-v4.8.0 named when its source was reviewed (README).
REVIEWED_COMMIT = "414603bf14c7a344edb466bb1f85690c77ce8b7d"
# Compose reads these from the clone's .env; the dev stack keeps 5432, 8000, and 5173.
CLONE_ENV = {
    "COMPOSE_PROJECT_NAME": "waterline-trial",
    "POSTGRES_PORT": "5442",
    "API_PORT": "8010",
    "WEB_PORT": "5183",
}
IGNORED = [".impeccable/", ".impeccable-home/"]


def step(message: str) -> None:
    print(f"==> {message}", flush=True)


def run(*args: str, cwd: Path | None = None) -> None:
    print("    $", " ".join(args), flush=True)
    subprocess.run(args, cwd=cwd, check=True)


def playwright_chromium() -> Path | None:
    """The newest Chromium Playwright downloaded for `wl e2e`, for `impeccable detect <url>`."""
    found = sorted(
        (Path.home() / ".cache" / "ms-playwright").glob("chromium-*/chrome-linux64/chrome"),
        key=lambda p: int(p.parts[-3].removeprefix("chromium-")),
    )
    return found[-1] if found else None


def write_env(clone: Path) -> None:
    """The clone's .env: the template, with the clone's own Compose project and ports, and only
    the PrimeUI key from this repository's .env (nothing else of it reaches the plugin's
    working directory)."""
    real = REPO / ".env"
    licence = [
        line
        for line in (real.read_text().splitlines() if real.exists() else [])
        if line.startswith("VITE_PRIMEUI_LICENSE=")
    ]
    replaced = {*CLONE_ENV, "VITE_PRIMEUI_LICENSE"}
    keep = [
        line
        for line in (REPO / ".env.example").read_text().splitlines()
        if line.split("=", 1)[0].strip() not in replaced
    ]
    added = [f"{key}={value}" for key, value in CLONE_ENV.items()]
    target = clone / ".env"
    target.write_text(
        "\n".join([*keep, "", "# The Impeccable trial (S3-C0n)", *added, *licence[-1:]]) + "\n"
    )
    target.chmod(0o600)
    print(
        f"    from .env.example; {', '.join(added)}; PrimeUI key: {'yes' if licence else 'MISSING'}"
    )


def allow_live_server(vite_config: Path) -> None:
    """Add live mode's server to the CSP's script-src, and a connect-src for it."""
    text = vite_config.read_text()
    old = "  \"script-src 'self'\",\n"
    new = f"  \"script-src 'self' {LIVE_ORIGIN}\",\n  \"connect-src 'self' {LIVE_ORIGIN}\",\n"
    if text.count(old) != 1 or "connect-src" in text:
        sys.exit(f"{vite_config}: the CSP isn't as expected; edit it by hand")
    vite_config.write_text(text.replace(old, new))


def write_claude_env(clone: Path, browser: Path | None) -> None:
    """Environment for every Claude Code session in the clone, its hooks and commands included.
    The plugin's local-scope install adds `enabledPlugins` to the same file."""
    env = {
        # Live mode's copy-edit Apply would launch `claude --permission-mode bypassPermissions`
        # (or `codex --dangerously-bypass-approvals-and-sandbox`): off (owner, S3-C0n).
        "IMPECCABLE_LIVE_COPY_AGENT": "off",
        "IMPECCABLE_NO_TELEMETRY": "1",
        "DO_NOT_TRACK": "1",
        "IMPECCABLE_NO_UPDATE_CHECK": "1",
        "IMPECCABLE_NO_STALENESS_CHECK": "1",
        # The engine downloads into the clone, not ~/.impeccable.
        "IMPECCABLE_HOME": str(clone / ".impeccable-home"),
        # Live mode looks for the app here (the clone's web port), not the dev stack's 5173.
        "IMPECCABLE_DEV_URL_CANDIDATES": f"http://localhost:{CLONE_ENV['WEB_PORT']}/",
    }
    if browser:
        env["IMPECCABLE_BROWSER"] = str(browser)
    path = clone / ".claude" / "settings.local.json"
    path.write_text(json.dumps({"env": env}, indent=2) + "\n")
    for key, value in env.items():
        print(f"    {key}={value}")


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    target = Path(sys.argv[1]).expanduser().resolve()
    if target.exists() and any(target.iterdir()):
        sys.exit(f"{target} isn't empty")
    for tool in ("git", "uv", "npm", "docker"):
        if not shutil.which(tool):
            sys.exit(f"{tool} isn't on PATH")
    target.mkdir(parents=True, exist_ok=True)
    remote, clone = target / "remote.git", target / "waterline"

    step(f"A bare remote and a clone, on a new branch `trial` (from {REPO})")
    run("git", "clone", "--bare", "--quiet", str(REPO), str(remote))
    run("git", "clone", "--quiet", str(remote), str(clone))
    run("git", "switch", "--quiet", "-c", "trial", cwd=clone)

    step("The clone's .env (its own Compose project and ports; mode 600)")
    write_env(clone)

    step("Impeccable's settings for Claude Code in the clone (.claude/settings.local.json)")
    browser = playwright_chromium()
    write_claude_env(clone, browser)
    if not browser:
        print("    MISSING: no Playwright Chromium under ~/.cache/ms-playwright, so `impeccable")
        print("    detect <url>` finds no browser. `wl e2e` installs one (developer guide).")

    step("Project-level telemetry off as well (.impeccable/config.json, for runs outside Claude)")
    (clone / ".impeccable").mkdir()
    (clone / ".impeccable" / "config.json").write_text('{\n  "telemetry": false\n}\n')

    step(f".gitignore entries ({', '.join(IGNORED)}) and live mode's CSP allowance ({LIVE_ORIGIN})")
    with (clone / ".gitignore").open("a") as gitignore:
        gitignore.write("\n# The Impeccable trial (S3-C0n): its state and engine cache\n")
        gitignore.write("".join(f"{entry}\n" for entry in IGNORED))
    allow_live_server(clone / "frontend" / "vite.config.ts")

    step("The trial's screenshots (frontend/e2e/screenshots/trial.shot.ts)")
    shot = "frontend/e2e/screenshots/trial.shot.ts"
    shutil.copy(HERE / "trial.shot.ts", clone / shot)

    step("Commit the setup on `trial`")
    run("git", "add", ".gitignore", "frontend/vite.config.ts", shot, cwd=clone)
    run("git", "commit", "--quiet", "-m", "trial: Impeccable trial setup (S3-C0n)", cwd=clone)

    step("Dependencies (the developer guide's first-time setup)")
    run("uv", "sync", "--all-packages", "--quiet", cwd=clone)
    run("uv", "sync", "--directory", "backend", "--quiet", cwd=clone)
    run("npm", "ci", "--prefix", "frontend", "--silent", cwd=clone)

    print()
    print(f"Ready: {clone}  (origin is {remote}, not GitHub)")
    print("Next, from the clone (README, 'Set up'):")
    print(f"  cd {clone}")
    print("  claude plugin marketplace remove impeccable   # an earlier, unpinned add")
    print("  claude plugin marketplace add pbakaus/impeccable#skill-v4.8.0")
    print("  claude plugin install impeccable@impeccable --scope local   # turns its hooks on")
    print(f"  then check the installed commit is {REVIEWED_COMMIT} (README, 'Set up', step 2)")
    print(
        f"  uv run wl up && uv run wl seed --manual-pass   # http://localhost:{CLONE_ENV['WEB_PORT']}"
    )
    print("  claude")


if __name__ == "__main__":
    main()
