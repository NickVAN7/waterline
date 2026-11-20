"""PreToolUse hook (Bash): the git guard, a small allow-list (DL-391). Stops the direct form of a
forbidden git or gh command and keeps git usage to one plain command per call. Evasion (scripts,
`bash -c`, redirects) is out of scope: GitHub's rulesets (DL-27), CI, and the `wl check`
repository-state step cover it. Exit 2 blocks (stderr to Claude); an "ask" asks the owner."""

import json
import re
import shlex
import subprocess
import sys
from collections.abc import Callable
from itertools import pairwise
from pathlib import Path

# fmt: off
ONE_COMMAND = ("a call that involves git or gh must be that one command and nothing else: no "
    "`&&`, `;`, `|`, `$(...)`, or redirects. Use `git -C <path>` for another directory, and `git "
    "commit -F - <<'EOF'` for a message. Otherwise, ask the owner to run it (`! <command>`).")
OWNER_DECIDES = ("Merging a pull request, or writing to GitHub through the API, is the owner's "
    "call (DL-25). Allow it only if the owner said to.")
OPERATORS = {"&&", "||", ";", "|", "&", "(", ")", ">", ">>", "<", "<<", "<<<", ">&", "&>", "|&"}
STARTERS = OPERATORS | {"eval", "xargs", "env"}  # a word after one of these runs as a command
# Any flags: the reads, and the everyday writes that touch only the working tree and the index.
FREE = {"status", "log", "diff", "show", "blame", "reflog", "ls-files", "ls-tree", "rev-parse",
        "rev-list", "describe", "grep", "cat-file", "shortlog", "merge-base", "for-each-ref",
        "show-ref", "check-ignore", "fetch", "add", "rm", "mv", "restore"}
LISTING = {"-a", "--all", "-r", "--remotes", "-v", "-vv", "--list", "-l", "--show-current"}
# A flag git reads as one in `long` (or abbreviated, or longer: `--force-with-lease`), or `short`.
refuses: Callable[[list[str], set[str], str], bool] = lambda flags, long, short: any(  # noqa: E731
    any(r.startswith(n) or n.startswith(r) for r in long) if n[:2] == "--" and n != "--"
    else bool(set(n[1:]) & set(short)) for n in (f.split("=", 1)[0] for f in flags))
RULES: dict[str, Callable[[list[str], list[str]], bool]] = {  # (rest, flags): allowed forms
    "switch": lambda _, f: not refuses(f, {"--force-create"}, "C"),  # -C moves a branch (owner)
    "hash-object": lambda _, f: not f,  # no `-w` (DL-29): the spec-test hashes
    "remote": lambda r, _: r in ([], ["-v"], ["--verbose"]),
    "branch": lambda _, f: set(f) <= LISTING,  # a listing, or `git branch <new-name>`
    "stash": lambda r, _: not r or r[0].startswith("-")
             or r[0] in ("list", "show", "push", "pop", "apply", "drop"),
    "config": lambda r, _: r in (["--list"], ["-l"], ["list"])
              or (len(r) == 2 and r[0] in ("--get", "get")),
    "checkout": lambda r, f: len(r) == 1 and not f,  # one branch, no flags
    "pull": lambda _, f: f in ([], ["--ff-only"]),
    **dict.fromkeys(("merge", "rebase", "cherry-pick", "revert", "am"),
                    lambda r, _: r == ["--abort"]),  # `--abort` only (owner, Nov 18)
}
PUSH_REFUSED = {"--force", "--delete", "--mirror", "--no-verify"}  # and `-f`, `-d`, as `refuses`
GH_ALLOWED = {tuple(pair.split()) for pair in (
    "pr create", "pr view", "pr list", "pr checks", "pr diff", "pr status", "pr ready", "pr edit",
    "run list", "run view", "run watch", "run rerun", "repo view", "issue list", "issue view")}
GH_API_READ = {"--paginate", "--jq", "-q", "--silent", "-i", "--include", "--verbose"}
# fmt: on
HEREDOC = re.compile(r"<<-?[ \t]*(['\"]?)(\w+)\1([^\n]*)\n.*?\n[ \t]*\2[ \t]*(?:\n|$)", re.S)


def git_out(cwd: Path | None, *args: str) -> str | None:
    cmd = ["git", *(["-C", str(cwd)] if cwd else []), *args]  # a read; None when git can't say
    run = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=5)  # noqa: S603
    return run.stdout.strip() if run.returncode == 0 else None


def decide(command: str, cwd: Path | None = None) -> tuple[str, str] | None:
    heredocs = HEREDOC.findall(command)  # their bodies are data; a line break ends a command
    text = HEREDOC.sub(r"\3\n", command).replace("\n", "\n; ").rstrip("; \t\n")
    lexer = shlex.shlex(text, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        words = list(lexer)
    except ValueError:
        return ("block", ONE_COMMAND) if command.split()[:1] in (["git"], ["gh"]) else None
    prev = ["", "", *words]  # prev[i + 1] is the word before words[i], prev[i] the one before it
    starts = {i for i, w in enumerate(words) if i == 0 or w.startswith("`") or prev[i + 1]
              in STARTERS or (prev[i + 1] == "-c" and prev[i] in ("bash", "sh"))}  # fmt: skip
    if not any(Path(words[i].lstrip("`$(").split(" ")[0]).name in ("git", "gh") for i in starts):
        return None
    shaped = [w in OPERATORS or "$" in w or "`" in w or i in starts for i, w in enumerate(words)]
    if words[0] not in ("git", "gh") or any(shaped[1:]):
        return ("block", ONE_COMMAND)
    if words[0] == "gh":
        return ("block", ONE_COMMAND) if heredocs else check_gh(words[1:])
    return check_git(words[1:], [quote for quote, *_ in heredocs], cwd)


def check_git(args: list[str], heredocs: list[str], cwd: Path | None) -> tuple[str, str] | None:
    while args[:1] in (["-C"], ["--no-pager"]):
        cwd = (cwd or Path()) / Path(args[1]).expanduser() if args[0] == "-C" and args[1:] else cwd
        args = args[2:] if args[0] == "-C" else args[1:]
    sub, rest = (args[0], args[1:]) if args else ("", [])
    flags, pairs = [w for w in rest if w.startswith("-")], list(pairwise(rest))
    if heredocs and not (sub == "commit" and ("-F", "-") in pairs and all(heredocs)):
        return ("block", f"a quoted heredoc is allowed only for `git commit -F -`. {ONE_COMMAND}")
    if sub not in ("commit", "push"):
        allowed = not sub or sub in FREE or (sub in RULES and RULES[sub](rest, flags))
        return None if allowed else ("block", f"`git {sub}` in this form: ask the owner.")
    here = git_out(cwd, "symbolic-ref", "--quiet", "--short", "HEAD")
    if sub == "commit":
        values = {b for a, b in pairs if a in ("-m", "--message", "-F", "--file")}
        if refuses([f for f in flags if f not in values], {"--no-verify"}, "n"):
            return ("block", "`git commit --no-verify` (or `-n`) skips the hooks (DL-24).")
        if here == "main":
            return ("block", "`git commit` on `main`: commit on the slice branch instead.")
        if "--amend" in flags and not git_out(cwd, "rev-list", "-1", "HEAD", "--not", "--remotes"):
            return ("block", "`git commit --amend`: HEAD is on the remote. Commit a fix instead.")
        return None
    targets = [w for w in rest if not w.startswith("-")][1:]  # after the remote
    if refuses(flags, PUSH_REFUSED, "fd") or any(":" in t or "+" in t for t in targets):
        return ("block", "this `git push` could force, delete, or name another ref (DL-23, DL-24).")
    if not targets or {"HEAD", "@"} & set(targets):  # the current branch, and where it goes
        sent = git_out(cwd, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{push}")
        targets += [here or "main", sent.split("/", 1)[-1] if sent else "main"]
    to_main = any(t == "main" or t.endswith("/main") for t in targets)  # `refs/heads/main` too
    return ("block", "a push to `main`: that's the owner's merge.") if to_main else None


def check_gh(args: list[str]) -> tuple[str, str] | None:
    repo = {i + 1 for i, w in enumerate(args) if w in ("-R", "--repo")}
    words = [w for i, w in enumerate(args) if i not in repo and not w.startswith(("-R", "--repo"))]
    if words[:2] == ["auth", "status"]:  # `--show-token` would print the token
        return None if len(words) == 2 else ("block", "`gh auth status` takes no options here.")
    if not words or words == ["--version"] or tuple(words[:2]) in GH_ALLOWED:
        return None
    if words[:1] == ["api"]:
        rest = [w for i, w in enumerate(words[1:]) if i == 0 or words[i] not in ("--jq", "-q")]
        endpoints = [w for w in rest if not w.startswith("-")]
        plain = {w for w in rest if w.startswith("-")} <= GH_API_READ and len(endpoints) == 1
        return None if plain and endpoints != ["graphql"] else ("ask", OWNER_DECIDES)
    if words[:2] == ["pr", "merge"]:  # it, and every gh api call but a plain read, ask (DL-25)
        return ("ask", OWNER_DECIDES)
    return ("block", f"`gh {' '.join(words[:2])}` isn't in the allow-list: ask the owner.")


def main() -> int:
    try:
        data: dict[str, dict[str, object]] = json.load(sys.stdin)
        command, cwd = (data.get("tool_input") or {}).get("command"), data.get("cwd")
        where = Path(cwd) if isinstance(cwd, str) else None
        verdict = decide(command, where) if isinstance(command, str) else None
    except (json.JSONDecodeError, OSError, subprocess.TimeoutExpired) as exc:  # fail closed
        verdict = ("block", f"couldn't check the command: its input, or git's answer ({exc}).")
    if verdict and verdict[0] == "ask":
        why = {"hookEventName": "PreToolUse", "permissionDecision": "ask"}
        print(json.dumps({"hookSpecificOutput": {**why, "permissionDecisionReason": verdict[1]}}))
    elif verdict:
        print(f"Blocked by the git guard: {verdict[1]}", file=sys.stderr)
    return 2 if verdict and verdict[0] == "block" else 0


if __name__ == "__main__":
    sys.exit(main())
