"""The git guard (.claude/hooks/guard_git.py), a small allow-list (DL-391): it stops the direct
form of a forbidden git or gh command and keeps git to one plain command per call; evasion is out
of its scope (its docstring).

The table runs against a stand-in for the repository's state (a branch other than `main`, HEAD
not pushed); the three rules that depend on the state run against real git at the end.
"""

import io
import json
import runpy
import subprocess
from pathlib import Path

import guard_git
import pytest

ALLOW, BLOCK, ASK = "allow", "block", "ask"


@pytest.fixture(autouse=True)
def on_a_slice_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    """The repository's state, for the table: on `s3`, HEAD not pushed, pushing to `origin/s3`."""
    answers = {"symbolic-ref": "s3", "rev-list": "abc123", "rev-parse": "origin/s3"}

    def git_out(_cwd: Path | None, *args: str) -> str | None:
        return answers[args[0]]

    monkeypatch.setattr(guard_git, "git_out", git_out)


def verdict(command: str) -> str:
    result = guard_git.decide(command, Path("/work"))
    return result[0] if result else ALLOW


# --- When the guard looks at all (rule 1), and one plain command per call (rule 2) -------------


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        # Only text: git as data, never as the program run.
        ("uv run wl check", ALLOW),
        ("grep -rn 'git push' docs", ALLOW),
        ("cat .git/config", ALLOW),
        ("echo use git switch", ALLOW),
        ("python3 - <<'PY'\nprint('git push origin main')\nPY", ALLOW),
        ("cat <<EOF\ngit push\nEOF", ALLOW),
        ("uv run git status", ALLOW),  # git not after a listed wrapper: evasion is out of scope
        ("FOO=1 git status", ALLOW),  # the same
        ('grep -n "unbalanced', ALLOW),  # shlex can't read it, and it isn't git
        # git run, but not as the one command of the call.
        ("git status && git log", BLOCK),
        ("git status; ls", BLOCK),
        ("git status | head -5", BLOCK),
        ("git status || true", BLOCK),
        ("git status &", BLOCK),
        ("cd backend && git status", BLOCK),
        ("(git status)", BLOCK),
        ("ls\ngit status", BLOCK),  # a line break ends a command
        ("# push it\ngit push --force origin s3", BLOCK),  # a comment ends at its line's end
        ("ls # note\ngit push --force origin s3", BLOCK),
        ("git status  # a note", ALLOW),
        ("env git status", BLOCK),
        ("bash -c 'git status'", BLOCK),
        ("sh -c 'git push origin main'", BLOCK),
        ("eval git status", BLOCK),
        ("ls | xargs git add", BLOCK),
        ("echo $(git rev-parse HEAD)", BLOCK),
        ("echo `git rev-parse HEAD`", BLOCK),
        ("x=$(gh pr list)", BLOCK),
        # A direct git or gh command with an operator, a substitution, or a redirect in it.
        ("git log $REV", BLOCK),
        ("git push origin ma$'in'", BLOCK),
        ("git log `cat rev`", BLOCK),
        ("git show HEAD:docs/x.webp > /tmp/x.webp", BLOCK),
        ("git log < notes.txt", BLOCK),
        ('git commit -m "unbalanced', BLOCK),
        # The one heredoc allowed: a quoted one, for `git commit -F -`.
        ("git commit -F - <<'EOF'\nfix: a $(message) with `ticks`\nEOF", ALLOW),
        ('git commit --file - <<"EOF"\nfix\nEOF', BLOCK),  # only `-F -`
        ("git commit -F - <<EOF\nfix\nEOF", BLOCK),  # unquoted: bash runs its `$(...)`
        ("git tag -F - <<'EOF'\nv1\nEOF", BLOCK),
        ("gh pr create --body-file - <<'EOF'\nbody\nEOF", BLOCK),
    ],
)
def test_the_guard_looks_only_at_git_and_gh_run_alone(command: str, expected: str) -> None:
    assert verdict(command) == expected


# --- Allowed by subcommand, not by flag (rule 3) -----------------------------------------------


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("git", ALLOW),
        ("git -C", ALLOW),  # git prints its usage
        ("git --no-pager log --oneline -S text -- docs", ALLOW),
        ("git -C ~/scratch/clone diff --output=x.diff", ALLOW),  # reads: any flags
        ("git reflog show main", ALLOW),
        ("git hash-object docs/x.md", ALLOW),  # no `-w`: the spec-test hashes (DL-29)
        ("git switch s3", ALLOW),
        ("git switch -c s4", ALLOW),
        ("git switch --discard-changes s3", ALLOW),
        *((f"git {sub} --any-flag", ALLOW) for sub in sorted(guard_git.FREE)),
        ("git remote", ALLOW),
        ("git remote -v", ALLOW),
        ("git remote add up https://example.com/x.git", BLOCK),
        ("git branch", ALLOW),
        ("git branch -vv --list 's*'", ALLOW),
        ("git branch --show-current", ALLOW),
        ("git branch s4", ALLOW),
        *((f"git branch {flag} s3", BLOCK) for flag in ("-d", "-D", "-m", "-M", "-f", "-c")),
        ("git stash", ALLOW),
        ("git stash -u -m park", ALLOW),
        *((f"git stash {sub}", ALLOW) for sub in ("list", "show", "push", "pop", "apply", "drop")),
        ("git stash clear", BLOCK),
        ("git config --get core.hooksPath", ALLOW),
        ("git config get user.name", ALLOW),
        ("git config --list", ALLOW),
        ("git config -l", ALLOW),
        ("git config list", ALLOW),
        ("git config core.hooksPath /tmp", BLOCK),
        ("git config --unset core.hooksPath", BLOCK),
        ("git config --get", BLOCK),  # a key, or it's not the read form
        ("git checkout s3", ALLOW),
        ("git checkout main", ALLOW),
        ("git checkout -- docs/x.md", BLOCK),  # `git restore` does it
        ("git checkout -b s4", BLOCK),
        ("git checkout s3 -- docs", BLOCK),
        ("git pull", ALLOW),
        ("git pull --ff-only origin s3", ALLOW),
        ("git pull --rebase", BLOCK),
        *(
            (f"git {sub} --abort", ALLOW)
            for sub in ("merge", "rebase", "cherry-pick", "revert", "am")
        ),
        *(
            (f"git {sub}", BLOCK)
            for sub in (
                "merge s2",
                "rebase main",
                "cherry-pick abc",
                "revert HEAD",
                "am x.patch",
                "reset --soft HEAD~1",
                "reset -- docs/x.md",
                "reset",
                "clean -fd",
                "filter-branch",
                "worktree add ../w",
                "update-ref refs/heads/main HEAD",
                "tag v1",
                "submodule update",
                "hash-object -w docs/x.md",
                "switch -C s3 HEAD~3",
                "switch --force-create s3",
                "switch --force-c s3",
                "branch --verbose",
                "gc",
                "notes add",
            )
        ),
    ],
)
def test_git_subcommands_and_their_forms(command: str, expected: str) -> None:
    assert verdict(command) == expected


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("git commit -m 'checkpoint(S3-C0o): x'", ALLOW),
        ("git commit -a -q -m x", ALLOW),
        ("git commit -am x", ALLOW),
        ("git commit -m -n", ALLOW),  # `-n` there is the message
        ("git commit --amend --no-edit", ALLOW),  # HEAD isn't pushed here
        ("git commit --no-verify -m x", BLOCK),
        ("git commit -n -m x", BLOCK),
        ("git commit -anm x", BLOCK),
        ("git commit --no-verif -m x", BLOCK),  # git takes an abbreviated long option
        ("git push", ALLOW),  # the current branch, `s3`, to `origin/s3`
        ("git push -u origin s3", ALLOW),
        ("git push origin", ALLOW),
        ("git push origin HEAD", ALLOW),
        ("git push origin @", ALLOW),  # `@` is `HEAD`
        ("git push --tags origin s3", ALLOW),
        ("git push origin main", BLOCK),
        ("git push origin s3 main", BLOCK),
        *(
            (f"git push {flag} origin s3", BLOCK)
            for flag in (
                "--force",
                "-f",
                "--force-with-lease",
                "--force-if-includes",
                "--delete",
                "-d",
                "--mirror",
                "--no-verify",
            )
        ),
        ("git push origin s3:main", BLOCK),
        ("git push origin +s3", BLOCK),
        ("git push --force-with-lease=s3 origin s3", BLOCK),
        ("git push -uf origin s3", BLOCK),
        ("git push --forc origin s3", BLOCK),
        ("git push origin refs/heads/main", BLOCK),
        ("git push --dry-run origin s3", ALLOW),
        ("git push origin :s3", BLOCK),
    ],
)
def test_commit_and_push_refuse_what_skips_hooks_forces_or_reaches_main(
    command: str, expected: str
) -> None:
    assert verdict(command) == expected


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("gh", ALLOW),
        ("gh --version", ALLOW),
        *((f"gh {' '.join(pair)} --json x", ALLOW) for pair in sorted(guard_git.GH_ALLOWED)),
        ("gh run rerun 44183264002 --failed", ALLOW),  # added (DL-391)
        ("gh -R NickVAN7/waterline pr view 12", ALLOW),
        ("gh pr view 12 --repo=NickVAN7/waterline", ALLOW),
        ("gh auth status", ALLOW),
        ("gh auth status --show-token", BLOCK),
        ("gh api repos/o/r/pulls/12/commits --paginate --jq '.[].sha'", ALLOW),
        ("gh api repos/o/r/pulls/12 -X PATCH -f title=x", ASK),
        ("gh api graphql -f query=x", ASK),
        ("gh api", ASK),
        ("gh pr merge 12 --merge", ASK),
        ("gh repo delete o/r", BLOCK),
        ("gh secret set X", BLOCK),
    ],
)
def test_gh_commands(command: str, expected: str) -> None:
    assert verdict(command) == expected


# --- The trial's friction log (docs/spikes/S3-C0b-guard-trial/friction-log.md) ------------------

# Each recorded command shape, as a command, with the new verdict. Entries 4 and 9's shapes are
# a path and a rerun; 20 and 31 were scripts ending in a git call.
FRICTION = [
    (1, "git checkout main", ALLOW),
    (2, "python3 -c \"print('the git guard')\"", ALLOW),
    (3, "diff -ruN -x .git reviewed-1 reviewed-2", ALLOW),
    (4, "ls docs/spikes/S3-C0b-git-trial", ALLOW),
    (5, "ls /tmp/x; find /tmp -name remote.git", ALLOW),
    (6, "git reflog show main", ALLOW),
    (7, "cat >> README.md <<'EOF'\nthe git guard\nEOF", ALLOW),
    (8, "python3 - note.md <<'PY'\nprint('git')\nPY", ALLOW),
    (9, "gh run rerun 1 --failed", ALLOW),
    (10, "f=$(git ls-files | grep check_contrast.py); grep x $f", BLOCK),
    (11, "cd docs; sed -n 1,5p x.md; git log -1", BLOCK),
    (12, "git log -S 'text' -- docs/decision-log.md", ALLOW),
    (13, "python3 - <<'PY'\nprint('the git guard')\nPY", ALLOW),
    (14, "cd backend; git diff --stat", BLOCK),
    (15, "sed -n 1p x; npx vue-tsc --build; git -C /w status", BLOCK),
    (16, "python3 - <<'PY'\nprint(\"the git guard's decision\")\nPY", ALLOW),
    (17, "grep -n x y; git -C /w diff --stat", BLOCK),
    (18, "cd frontend && python3 - <<'PY'\nprint(1)\nPY\ngit rm src/x.vue", BLOCK),
    (19, "python3 - <<'PY'\nprint('git -C <repo> diff')\nPY", ALLOW),
    (20, "npx vitest run x.spec.ts; git stash", BLOCK),
    (21, "python3 - <<'PY'\nprint('the parked stash, git stash pop')\nPY", ALLOW),
    (22, "cat > /tmp/s.py <<'EOF'\nprint('the git guard')\nEOF", ALLOW),
    (23, "python3 - <<'PY'\nprint('Listed through git')\nPY", ALLOW),
    (24, "curl -s http://localhost:8000/api/health; gh run list", BLOCK),
    (25, "cd /w && git status", BLOCK),
    (26, "R=/w; git -C $R show HEAD", BLOCK),
    (27, "sed -n 1p x; grep y z; git -C /w hash-object x", BLOCK),
    (28, "python3 - <<'PY'\nprint(1)\nPY\ngit diff --stat", BLOCK),
    (29, "grep x build-plan.md; git log --oneline -1; git status -s", BLOCK),
    (30, "python3 - <<'PY'\nprint(\"the git guard's decision\")\nPY", ALLOW),
    (31, "cp x y; uv run pytest; cp y x; git -C /w diff --stat", BLOCK),
    (32, "diff -ruN a b > $D/fix.diff", ALLOW),
    (33, "diff -ruN -x .git a b", ALLOW),
    (34, "grep -rn ensure_hook_git_excludes /tmp/impeccable", ALLOW),
    (35, "curl -sL https://api.github.com/repos/o/r/git/ref/tags/v1 -o /tmp/t.json", ALLOW),
    (36, "python3 - <<'PY'\nprint('git add .gitignore')\nPY", ALLOW),
    (37, "cat >> docs/decision-log.md <<'EOF'\n.git/info/exclude\nEOF", ALLOW),
    (38, "sha256sum x; git diff --stat HEAD -- frontend", BLOCK),
    (39, "docker ps; git -C /c log -1; git -C /c status; ls", BLOCK),
    (40, "ls; find . -not -path '*/.git/*'", ALLOW),
    (41, "cd /c && ls; find . | grep -v '/\\.git/'", ALLOW),
    (42, "git -C /c diff --output=/s/trial.diff", ALLOW),
    (43, "cd /w && grep -rln acceptance src; ls; git log --oneline -1 -- t.diff", BLOCK),
    (44, "wc -l x && grep -n '^diff --git' results/trial.diff", ALLOW),
    (45, "S=/s && git -C /w show HEAD:x.webp > $S/x.webp; ls", BLOCK),
    (46, "python3 - <<'PY'\nprint(1)\nPY\ngit -C /w diff --stat", BLOCK),
    (47, "D=/s && uv run wl review-copy $D/r2; diff -ruN -x .git $D/r1 $D/r2 > $D/fix.diff", ALLOW),
    (48, "tail /tmp/ci.out; gh pr view --json number,url", BLOCK),
    (49, "python3 - <<'PY'\nprint('git and gh')\nPY\ngrep -n x y", ALLOW),
    (50, "ls; git status", BLOCK),
    (51, "grep -n x y && git rev-parse HEAD", BLOCK),
]


@pytest.mark.parametrize(
    ("entry", "command", "expected"), FRICTION, ids=[f"#{n}" for n, *_ in FRICTION]
)
def test_each_friction_log_command_gets_the_new_verdict(
    entry: int, command: str, expected: str
) -> None:
    """The blocks the trial logged that only mentioned git now pass; a second command in the
    same call still blocks, as one plain git command per call is the rule (rule 2)."""
    assert verdict(command) == expected


def test_every_friction_log_entry_is_in_the_table() -> None:
    log = (Path(__file__).parents[4] / "docs/spikes/S3-C0b-guard-trial/friction-log.md").read_text()
    entries = {
        int(line.split("|")[1]) for line in log.splitlines() if line[:3].strip("| ").isdigit()
    }
    assert entries == {n for n, *_ in FRICTION}


# --- The hook entry point ------------------------------------------------------------------------


def run_hook(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], stdin: str
) -> tuple[int, str, str]:
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    code = guard_git.main()
    out = capsys.readouterr()
    return code, out.out, out.err


def hook_input(command: object) -> str:
    return json.dumps({"tool_input": {"command": command}, "cwd": "/work"})


def test_a_blocked_command_exits_2_with_the_reason(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out, err = run_hook(monkeypatch, capsys, hook_input("git push origin main"))

    assert (code, out) == (2, "")
    assert err.startswith("Blocked by the git guard: a push to `main`")


def test_a_merge_asks_the_owner(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out, err = run_hook(monkeypatch, capsys, hook_input("gh pr merge 12 --merge"))

    assert (code, err) == (0, "")
    decision = json.loads(out)["hookSpecificOutput"]
    assert decision["permissionDecision"] == "ask"
    assert decision["permissionDecisionReason"] == guard_git.OWNER_DECIDES


@pytest.mark.parametrize("stdin", [hook_input("git status"), hook_input(None), json.dumps({})])
def test_an_allowed_or_non_bash_input_passes_silently(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], stdin: str
) -> None:
    assert run_hook(monkeypatch, capsys, stdin) == (0, "", "")


def test_input_that_isnt_json_blocks(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code, _, err = run_hook(monkeypatch, capsys, "not json")

    assert code == 2
    assert "couldn't check the command" in err


@pytest.mark.parametrize("error", [OSError("no git"), subprocess.TimeoutExpired("git", 5)])
def test_a_commit_blocks_when_git_cannot_answer(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], error: Exception
) -> None:
    """Fail closed: a commit or push whose rule needs the repository's state isn't let through."""

    def cannot(_cwd: Path | None, *_args: str) -> str | None:
        raise error

    monkeypatch.setattr(guard_git, "git_out", cannot)
    code, _, err = run_hook(monkeypatch, capsys, hook_input("git commit -m x"))

    assert code == 2
    assert "couldn't check the command" in err


def test_the_script_runs_as_a_hook(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(hook_input("git status")))

    with pytest.raises(SystemExit) as stopped:
        runpy.run_path(guard_git.__file__, run_name="__main__")

    assert stopped.value.code == 0


# --- The three rules that depend on the repository's state, against real git -------------------


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout


@pytest.fixture
def clone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A clone of a bare remote: `main` pushed, then `s1` tracking `origin/s1` with one pushed
    commit. Global and system git config are ignored; the table's stand-in state is undone."""
    monkeypatch.undo()
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    remote, work = tmp_path / "remote.git", tmp_path / "work"
    git(tmp_path, "init", "--quiet", "--bare", "--initial-branch=main", str(remote))
    git(tmp_path, "clone", "--quiet", str(remote), str(work))
    git(work, "config", "user.name", "T")
    git(work, "config", "user.email", "t@example.com")
    git(work, "commit", "--quiet", "--allow-empty", "-m", "base")
    git(work, "push", "--quiet", "origin", "main")
    git(work, "switch", "--quiet", "-c", "s1")
    git(work, "commit", "--quiet", "--allow-empty", "-m", "pushed")
    git(work, "push", "--quiet", "-u", "origin", "s1")
    return work


def real(command: str, cwd: Path) -> str:
    result = guard_git.decide(command, cwd)
    return result[0] if result else ALLOW


def test_a_commit_on_main_is_blocked_in_real_git(clone: Path) -> None:
    assert real("git commit -m x", clone) == ALLOW
    git(clone, "switch", "--quiet", "main")

    assert real("git commit -m x", clone) == BLOCK
    assert real("git -C work commit -m x", clone.parent) == BLOCK  # `-C` names the repository


def test_an_amend_is_blocked_once_head_is_pushed_in_real_git(clone: Path) -> None:
    assert real("git commit --amend --no-edit", clone) == BLOCK  # `pushed` is on origin/s1
    git(clone, "commit", "--quiet", "--allow-empty", "-m", "unpushed")

    assert real("git commit --amend --no-edit", clone) == ALLOW


@pytest.mark.parametrize(
    "command", ["git push", "git push origin", "git push origin HEAD", "git push origin @"]
)
def test_a_push_that_reaches_main_is_blocked_in_real_git(clone: Path, command: str) -> None:
    assert real(command, clone) == ALLOW  # `s1` to `origin/s1`
    git(clone, "switch", "--quiet", "main")

    assert real(command, clone) == BLOCK


def test_a_branch_with_no_push_destination_is_blocked_from_a_bare_push(clone: Path) -> None:
    git(clone, "switch", "--quiet", "-c", "s2")  # no upstream: a bare push goes nowhere known

    assert real("git push", clone) == BLOCK
    assert real("git push -u origin s2", clone) == ALLOW


def test_the_guard_asks_git_in_its_own_directory_when_the_hook_names_none(
    clone: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    git(clone, "switch", "--quiet", "main")
    monkeypatch.chdir(clone)

    assert guard_git.decide("git commit -m x") is not None
