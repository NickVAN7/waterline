"""S3-C0b (DL-316): set up the git guard's trial in a scratch directory.

    python3 docs/spikes/S3-C0b-guard-trial/setup.py <empty directory>

Makes `<dir>/remote.git`, a bare copy of this repository standing in for GitHub, so nothing the
trial pushes leaves the machine, and `<dir>/waterline`, a clone of it on `main` whose Claude Code
settings are this folder's `settings.json`: permission rules and a hook refusing commits on
`main` in place of the git guard. Start the trial session with `claude` inside `<dir>/waterline`.
"""

import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


def run(*args: str, cwd: Path | None = None) -> None:
    subprocess.run(args, cwd=cwd, check=True)


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    target = Path(sys.argv[1]).resolve()
    if target.exists() and any(target.iterdir()):
        sys.exit(f"{target} isn't empty")
    target.mkdir(parents=True, exist_ok=True)
    remote, clone = target / "remote.git", target / "waterline"
    run("git", "clone", "--bare", "--quiet", str(REPO), str(remote))
    run("git", "clone", "--quiet", str(remote), str(clone))
    run("git", "switch", "--quiet", "main", cwd=clone)
    shutil.copy(HERE / "settings.json", clone / ".claude" / "settings.json")
    shutil.copy(HERE / "refuse_main_commit.py", clone / ".claude" / "hooks" / "refuse_main_commit.py")
    print(f"Ready: cd {clone} && claude   (its origin is {remote}, not GitHub)")


if __name__ == "__main__":
    main()
