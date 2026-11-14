"""S3-C0b trial hook (DL-316): refuse a Bash call that would commit or merge on `main` (DL-21).

The rest of the git guard's outcomes are left to the trial's permission rules
(`settings.json`) and GitHub's rulesets (DL-27). A PreToolUse hook: it reads the tool call as
JSON on stdin and exits 2 with a message to block it. `--self-test` checks the decision alone.
"""

import json
import re
import subprocess
import sys

# A git call (any options before the subcommand) whose subcommand writes a commit on the branch.
_WRITES_A_COMMIT = re.compile(r"\bgit\b[^;&|\n]*?\b(commit|merge|cherry-pick|revert|am|pull)\b")


def refuses(command: str, branch: str) -> bool:
    match = _WRITES_A_COMMIT.search(command)
    if branch != "main" or not match:
        return False
    # DL-21: `git pull --ff-only` is how main is updated; it never writes a commit.
    return not (match.group(1) == "pull" and "--ff-only" in command)


def _branch(cwd: str) -> str:
    result = subprocess.run(
        ["git", "-C", cwd, "branch", "--show-current"], capture_output=True, text=True
    )
    return result.stdout.strip()


def main() -> None:
    call = json.load(sys.stdin)
    command = call.get("tool_input", {}).get("command", "")
    if refuses(command, _branch(call.get("cwd", "."))):
        print("Refused: no commits or merges on main (DL-21). Switch to the slice branch.", file=sys.stderr)
        sys.exit(2)


def _self_test() -> None:
    assert refuses('git commit -m "x"', "main")
    assert refuses("git -C . commit --allow-empty -m x", "main")
    assert refuses("git status && git merge s3", "main")
    assert refuses("git pull origin main", "main")
    assert not refuses('git commit -m "x"', "s3")
    assert not refuses("git pull --ff-only", "main")
    assert not refuses("git status", "main")
    assert not refuses("git log --oneline", "main")
    assert not refuses("npm run commit-lint", "main")
    print("self-test passed")


if __name__ == "__main__":
    _self_test() if sys.argv[1:] == ["--self-test"] else main()
