"""The git guard hook (.claude/hooks/guard_git.py): what it allows, blocks, and asks about.

Rules from docs/build-plan.md ("Pull requests", "Claude configuration") and DL-12. Most tests
use a fake repository state; `GitRepo` is tested against real repositories at the end.
"""

import io
import json
import runpy
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import guard_git
import pytest

CWD = Path("/work/waterline")


@dataclass
class FakeRepo:
    branch: str | None = "s1"
    push_to: str | None = "origin/s1"
    head_pushed: bool = False
    # reset target -> whether moving there drops pushed commits (None: not a commit)
    drops: dict[str, bool | None] = field(default_factory=dict[str, bool | None])
    aliases: dict[str, str] = field(default_factory=dict[str, str])
    asked: list[tuple[str, Path]] = field(default_factory=list[tuple[str, Path]])

    def current_branch(self, cwd: Path) -> str | None:
        self.asked.append(("branch", cwd))
        return self.branch

    def push_destination(self, cwd: Path) -> str | None:
        return self.push_to

    def head_on_remote(self, cwd: Path) -> bool:
        return self.head_pushed

    def drops_pushed_commits(self, cwd: Path, target: str) -> bool | None:
        return self.drops.get(target)

    def alias(self, cwd: Path, name: str) -> str | None:
        return self.aliases.get(name)


def verdict(
    command: str, repo: FakeRepo | None = None, cwd: Path | None = CWD
) -> guard_git.Verdict:
    return guard_git.decide(command, cwd, repo or FakeRepo())


def block_message(command: str, repo: FakeRepo | None = None, cwd: Path | None = CWD) -> str:
    result = verdict(command, repo, cwd)
    assert result.block is not None, f"{command!r} was not blocked"
    return result.block


# --- Allowed ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "ls -la",
        "uv run wl check",
        "git status",
        "git log --oneline -5",
        "git diff HEAD~1 -- docs",
        "git add -A && git commit -m 'docs: x'",
        "git commit -am 'msg with -n and --no-verify in it'",
        "git commit -m -n",  # -m takes "-n" as the message
        "git commit --amend --no-edit",  # HEAD not pushed yet
        "git commit --fixup=amend:HEAD",
        "git commit -F - <<'EOF'\nIt's a message with git push -f in it\nEOF",
        "git commit -m \"$(cat <<'EOF'\nIt's fine: git push --force\nEOF\n)\"",
        "git push",
        "git push -u origin s1",
        "git push origin s1",
        "git push origin HEAD",
        "git push origin s1:s1",
        "git push --dry-run origin s1",
        "git push --follow-tags origin s1",
        "git push --no-force-with-lease origin s1",
        "git push -o ci.skip origin s1",
        "git push --push-option ci.skip origin s1",
        "git push --repo=origin s1",
        "git push origin -- s1",
        "git merge --ff-only origin/s1",
        "git merge --abort",
        "git rebase --abort",
        "git rebase --quit",
        "git reset",
        "git reset --hard",
        "git reset HEAD -- docs/a.md",
        "git reset docs/a.md docs/b.md",
        "git reset -p",
        "git reset --soft HEAD~1",  # drops only unpushed commits (FakeRepo.drops)
        "git reset docs/a.md",  # not a commit: resets a path
        "git -C /work/other status",
        "git -c color.ui=never log",
        "git --no-pager log",
        "git -c core.editor=true commit -m x",
        "git --version",
        "git",
        "git lfs ls-files",
        "git frobnicate",  # neither builtin nor alias: git rejects it
        "git st",  # alias for status
        "git -C ~/code/waterline status",
        "cd docs && git status",
        "cd && git status",
        "(cd backend && git status)",
        "FOO=1 git status",
        "env GIT_PAGER=cat git log",
        "env -i git status",
        "command -v git",
        "command git status",
        "which git gh",
        "grep -rn 'git push' docs",
        "echo git push --force",
        "time git status",
        "if git diff --quiet; then echo clean; fi",
        "git status | head -5",
        "git status 2>&1 | tail",
        "git log > /tmp/log.txt",
        "HASH=$(git rev-parse HEAD) && echo $HASH",
        "echo `git rev-parse HEAD`",
        "diff <(git show HEAD:a) a",
        "bash -c 'git status'",
        "bash -lc 'git log'",
        "sh -c -- 'git status'",
        "bash -o pipefail -c 'git log | head'",
        "bash scripts/release.sh",
        "bash <<'EOF'\ngit status\nEOF",
        "eval git status",
        "python3 - <<'EOF'\nprint('git push --force')\nEOF",
        "echo $((1 + 2)) git",
        "gh pr create --draft --base main --title x",
        "gh pr checks --watch",
        "gh pr view 9 --json state",
        "gh -R owner/repo pr view 9",
        "gh --repo=owner/repo pr list",
        "gh api repos/owner/repo/pulls/9",
        "gh api graphql -f query='query { viewer { login } }'",
        "gh",
        "gh --version",
        "# a comment mentioning git push -f\ngit status",
        "echo 'it'\\''s' && git status",
        'echo "a \\"quoted\\" git" && git status',
        "git log --format='%h %s' $REV",
        'git commit -m "line one\nline two"',
        "git \\\n  status",
        "echo $(printf '%s' \")\" \\)) && git status",
        'echo $(echo "a \\" b") && git status',
        "git -C ${HOME}/w status",
        "git status && bash scripts/release.sh",
        "git --namespace=x log",
        "git --namespace x log",
        "git push --verbos origin s1",
    ],
)
def test_allowed_commands_pass(command: str) -> None:
    repo = FakeRepo(drops={"HEAD~1": False, "docs/a.md": None}, aliases={"st": "status"})

    assert verdict(command, repo) == guard_git.ALLOW


def test_a_command_without_git_or_gh_never_asks_the_repository() -> None:
    repo = FakeRepo()

    verdict("git-free && ls && echo digits", repo)

    assert repo.asked == []


# --- Blocked: work on main --------------------------------------------------------------------

ON_MAIN = FakeRepo(branch="main", push_to="origin/main")


@pytest.mark.parametrize(
    "command",
    [
        "git commit -m x",
        "git add . && git commit -m x",
        "git commit --allow-empty -m x; git status",
        "bash -c 'git commit -m x'",
        "(git commit -m x)",
    ],
)
def test_commit_on_main_is_blocked(command: str) -> None:
    assert "`git commit` on `main`" in block_message(command, ON_MAIN)


@pytest.mark.parametrize("command", ["git merge s1", "git merge --no-ff origin/s1"])
def test_merge_on_main_is_blocked(command: str) -> None:
    assert "`git merge` on `main`" in block_message(command, ON_MAIN)


def test_merge_abort_on_main_is_allowed() -> None:
    assert verdict("git merge --abort", ON_MAIN) == guard_git.ALLOW


@pytest.mark.parametrize("command", ["git commit -m x", "git merge s1"])
def test_commit_and_merge_off_main_are_allowed(command: str) -> None:
    assert verdict(command, FakeRepo(branch="s1")) == guard_git.ALLOW


@pytest.mark.parametrize(
    ("command", "repo"),
    [
        ("git push origin main", FakeRepo()),
        ("git push origin HEAD:main", FakeRepo()),
        ("git push origin s1:main", FakeRepo()),
        ("git push origin refs/heads/s1:refs/heads/main", FakeRepo()),
        ("git push origin s1 main", FakeRepo()),
        ("git push --repo=origin main", FakeRepo()),
        ("git push", ON_MAIN),  # a bare push while on main
        ("git push", FakeRepo(branch="main", push_to=None)),  # ...even with no upstream
        ("git push origin", FakeRepo(branch="main", push_to=None)),
        ("git push origin HEAD", ON_MAIN),
        ("git push -u origin @", ON_MAIN),
        ("git push", FakeRepo(branch="s1", push_to="origin/main")),  # s1 pushes to main
        ("cd /tmp && git push origin main", FakeRepo()),
    ],
)
def test_push_to_main_is_blocked(command: str, repo: FakeRepo) -> None:
    assert "this push would update `main`" in block_message(command, repo)


# --- Blocked: force and destructive pushes ----------------------------------------------------


@pytest.mark.parametrize(
    ("command", "message"),
    [
        ("git push -f", "force push"),
        ("git push -fu origin s1", "force push"),
        ("git push --force origin s1", "force push"),
        ("git push --forc origin s1", "force push"),  # git accepts abbreviations
        ("git push --force-with-lease origin s1", "force push"),
        ("git push --force-with-lease=s1:abc origin s1", "force push"),
        ("git push --force-if-includes origin s1", "force push"),
        ("git push origin +s1", "force push"),
        ("git push origin +s1:s1", "force push"),
        ("git push --mirror origin", "--mirror"),
        ("git push --delete origin s1", "deleting a remote branch"),
        ("git push -d origin s1", "deleting a remote branch"),
        ("git push --del origin s1", "deleting a remote branch"),
        ("git push origin :s1", "deleting a remote branch"),
        ("git push --prune origin", "--prune"),
        ("git push --all origin", "`--all`"),
        ("git push --branches origin", "`--branches`"),
        ("git push origin 'refs/heads/*:refs/heads/*'", "can't tell where"),
        ("git push origin $BRANCH", "can't tell where"),
        ("git push origin $(git branch --show-current)", "can't tell where"),
        ("git status && git push -f origin s1", "force push"),
        ("git push origin s1 || git push -f origin s1", "force push"),
        ("sh -c 'git push --force'", "force push"),
        ("eval 'git push --force'", "force push"),
        ("bash <<'EOF'\ngit push --force\nEOF", "force push"),
        ("echo $(git push -f)", "force push"),
        ("git -C /work/other push -f", "force push"),
        ("GIT_TRACE=1 git push -f", "force push"),
    ],
)
def test_force_and_destructive_pushes_are_blocked(command: str, message: str) -> None:
    assert message in block_message(command)


# --- Blocked: rewriting pushed history ----------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "git rebase main",
        "git rebase -i HEAD~3",
        "git rebase --continue",
        "git rebase --onto main s1~2 s1",
        "git pull && git rebase origin/main",
    ],
)
def test_rebase_is_blocked(command: str) -> None:
    assert "`git rebase` rewrites history" in block_message(command)


@pytest.mark.parametrize(
    "command",
    ["git commit --amend --no-edit", "git commit --am -m x", "git commit -a --amend"],
)
def test_amending_a_pushed_head_is_blocked(command: str) -> None:
    message = block_message(command, FakeRepo(head_pushed=True))

    assert "HEAD is already on the remote" in message


def test_amending_an_unpushed_head_is_allowed() -> None:
    assert verdict("git commit --amend --no-edit", FakeRepo(head_pushed=False)) == guard_git.ALLOW


@pytest.mark.parametrize(
    "command",
    [
        "git reset --hard HEAD~2",
        "git reset HEAD~2",
        "git reset --keep HEAD~2",
        "git reset -q HEAD~2",
    ],
)
def test_reset_that_drops_pushed_commits_is_blocked(command: str) -> None:
    message = block_message(command, FakeRepo(drops={"HEAD~2": True}))

    assert "would drop commits that are already on the remote" in message


def test_reset_to_a_target_only_known_at_run_time_is_blocked() -> None:
    message = block_message("git reset --hard $(git merge-base HEAD origin/s1)")

    assert "can't tell which commit `git reset` moves to" in message


# --- Blocked: skipping hooks ------------------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "git commit --no-verify -m x",
        "git commit --no-veri -m x",
        "git commit -n -m x",
        "git commit -anm x",
        "git commit -nothing",  # -n, then -o, -t (takes "hing")
        "git push --no-verify origin s1",
        "git merge --no-verify s1",
        "git -c core.hooksPath=/dev/null commit -m x",
        "git -c core.hookspath=/dev/null push",
        "git --config-env=core.hooksPath=EMPTY commit -m x",
        "git --config-env core.hooksPath=EMPTY commit -m x",
    ],
)
def test_skipping_hooks_is_blocked(command: str) -> None:
    message = block_message(command)

    assert "hook" in message


# --- Aliases ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("alias", "message"),
    [
        ("push --force", "force push"),
        ("!git push -f", "force push"),
        ("!f() { git push --force; }; f", "force push"),
        ("rebase -i", "`git rebase` rewrites history"),
    ],
)
def test_an_alias_is_checked_as_what_it_runs(alias: str, message: str) -> None:
    assert message in block_message("git p origin s1", FakeRepo(aliases={"p": alias}))


def test_an_alias_defined_on_the_command_line_is_blocked() -> None:
    assert "an alias defined with `git -c`" in block_message("git -c alias.p=push p -f")


def test_aliases_nested_too_deeply_are_blocked() -> None:
    repo = FakeRepo(aliases={"a": "a"})

    assert "nested too deeply" in block_message("git a", repo)


# --- Merging a pull request asks the owner ------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "gh pr merge 9 --merge --delete-branch",
        "gh pr merge --squash",
        "gh -R owner/repo pr merge 9",
        "gh pr checks 9 && gh pr merge 9 --merge",
        "gh api -X PUT repos/owner/repo/pulls/9/merge",
        "gh api --method PUT /repos/{owner}/{repo}/pulls/9/merge -f merge_method=merge",
        "gh api graphql -f query='mutation { mergePullRequest(input: {}) { clientMutationId } }'",
        "gh api graphql -F query=@q.graphql -f x=enablePullRequestAutoMerge",
        "gh api graphql --input mutation.json",
    ],
)
def test_merging_a_pull_request_asks_the_owner(command: str) -> None:
    result = verdict(command)

    assert result.block is None
    assert result.ask is not None
    assert "the owner's call" in result.ask


def test_a_block_wins_over_an_ask() -> None:
    result = verdict("gh pr merge 9 && git push -f")

    assert result.block is not None
    assert "force push" in result.block


# --- Can't tell which repository -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("command", "cwd"),
    [
        ("git commit -m x", None),
        ("cd $DIR && git commit -m x", CWD),
        ("cd - && git push", CWD),
        ("popd && git commit -m x", CWD),
        ("git -C $DIR commit -m x", CWD),
        ("git --git-dir=/elsewhere/.git commit -m x", CWD),
        ("git --work-tree /elsewhere commit -m x", CWD),
        ("git p", None),  # an alias lookup needs the repository
    ],
)
def test_a_command_whose_repository_is_unknown_is_blocked(command: str, cwd: Path | None) -> None:
    assert "can't tell which repository" in block_message(command, cwd=cwd)


def test_git_dash_c_points_the_checks_at_that_repository() -> None:
    repo = FakeRepo()

    verdict("cd /a && git -C ../b commit -m x", repo)

    assert repo.asked == [("branch", Path("/b"))]


# --- Can't parse with confidence (fail closed) --------------------------------------------------


@pytest.mark.parametrize(
    ("command", "reason"),
    [
        ("git commit -m 'unclosed", "an unclosed '"),
        ('git commit -m "unclosed', 'an unclosed "'),
        ("echo $(git push", "an unclosed `(`"),
        ("echo `git push", "an unclosed backtick"),
        ("echo ${HOME && git status", "an unclosed ${"),
        ("git commit -F - <<EOF\nno end", "a heredoc without its closing 'EOF' line"),
        ("git commit -F - <<EOF", "a heredoc without its closing 'EOF' line"),
        ('echo "$(cat <<EOF\nno end)" && git status', "a heredoc without its closing 'EOF' line"),
        ("git --frobnicate status", "the git option `--frobnicate`"),
        ("ls | xargs git push", "`xargs` may run `git`"),
        ("find . -exec git add {} ;", "`find` may run `git`"),
        ("uv run git push", "`uv` may run `git`"),
        ("sudo /usr/bin/git push", "`sudo` may run `git`"),
        ("env -S 'git push -f'", "`env -S`"),
        ("echo git push -f | bash", "`bash` reading its commands from stdin"),
        ("git status; bash -c", "`bash -c` without a command"),
        ("git $SUB", "a git subcommand that's only known at run time"),
        ("gh pm 9", "`gh pm` (an alias or extension?)"),
        ("gh $CMD", "`gh $…` (an alias or extension?)"),
        ("eval " * 7 + "git status", "commands nested too deeply"),
    ],
)
def test_a_command_it_cannot_parse_is_blocked(command: str, reason: str) -> None:
    message = block_message(command, FakeRepo(aliases={}))

    assert f"({reason})" in message
    assert "simple commands" in message


# --- The hook's input and output -----------------------------------------------------------------


def run_main(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    stdin: str,
    repo: FakeRepo | None = None,
) -> tuple[int, str, str]:
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    code = guard_git.main(repo or FakeRepo())
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def hook_input(command: object, cwd: object = str(CWD)) -> str:
    return json.dumps({"tool_name": "Bash", "tool_input": {"command": command}, "cwd": cwd})


def test_a_blocked_command_exits_2_with_the_reason_on_stderr(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out, err = run_main(monkeypatch, capsys, hook_input("git push --force"))

    assert (code, out) == (2, "")
    assert err.startswith("Blocked by the git guard: a force push rewrites pushed history.")


def test_an_allowed_command_exits_0_silently(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run_main(monkeypatch, capsys, hook_input("git status")) == (0, "", "")


def test_a_merge_prints_an_ask_decision(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out, err = run_main(monkeypatch, capsys, hook_input("gh pr merge 9 --merge"))

    assert (code, err) == (0, "")
    output = json.loads(out)["hookSpecificOutput"]
    assert output["hookEventName"] == "PreToolUse"
    assert output["permissionDecision"] == "ask"
    assert "the owner's call" in output["permissionDecisionReason"]


def test_input_without_a_cwd_cannot_check_the_branch(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code, _, err = run_main(monkeypatch, capsys, hook_input("git commit -m x", cwd=None))

    assert code == 2
    assert "can't tell which repository" in err


@pytest.mark.parametrize(
    "stdin",
    [json.dumps({"tool_input": {}}), json.dumps({}), hook_input(["git", "push", "-f"])],
)
def test_input_without_a_command_string_is_let_through(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], stdin: str
) -> None:
    assert run_main(monkeypatch, capsys, stdin) == (0, "", "")


def test_input_that_is_not_json_is_blocked(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code, _, err = run_main(monkeypatch, capsys, "not json")

    assert code == 2
    assert "isn't JSON" in err


# --- GitRepo against real repositories ----------------------------------------------------------


def git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", "user.name=T", "-c", "user.email=t@example.com", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


@pytest.fixture
def clone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A clone of a bare remote, on branch `s1` tracking `origin/s1`, with two pushed commits
    and one unpushed one. Global and system git config are ignored."""
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    remote, work = tmp_path / "remote.git", tmp_path / "work"
    git(tmp_path, "init", "--quiet", "--bare", "--initial-branch=main", str(remote))
    git(tmp_path, "clone", "--quiet", str(remote), str(work))
    git(work, "switch", "--quiet", "-c", "s1")
    git(work, "commit", "--quiet", "--allow-empty", "-m", "one")
    git(work, "commit", "--quiet", "--allow-empty", "-m", "two")
    git(work, "push", "--quiet", "-u", "origin", "s1")
    git(work, "commit", "--quiet", "--allow-empty", "-m", "three (unpushed)")
    git(work, "config", "alias.st", "status --short")
    return work


def test_git_repo_reads_the_current_branch_and_push_destination(clone: Path) -> None:
    repo = guard_git.GitRepo()

    assert repo.current_branch(clone) == "s1"
    assert repo.push_destination(clone) == "origin/s1"


def test_git_repo_reports_no_branch_when_detached_or_outside_a_repository(
    clone: Path, tmp_path: Path
) -> None:
    git(clone, "switch", "--quiet", "--detach")
    repo = guard_git.GitRepo()

    assert repo.current_branch(clone) is None
    assert repo.current_branch(tmp_path) is None
    assert repo.push_destination(tmp_path) is None


def test_git_repo_knows_whether_head_is_pushed(clone: Path) -> None:
    repo = guard_git.GitRepo()

    assert repo.head_on_remote(clone) is False
    git(clone, "reset", "--quiet", "--hard", "HEAD~1")
    assert repo.head_on_remote(clone) is True


@pytest.mark.parametrize(
    ("target", "drops"),
    [
        ("HEAD", False),
        ("HEAD~1", False),  # drops only the unpushed commit
        ("HEAD~2", True),  # drops a pushed one too
        ("origin/s1", False),
        ("not-a-commit.txt", None),
    ],
)
def test_git_repo_knows_whether_a_reset_drops_pushed_commits(
    clone: Path, target: str, drops: bool | None
) -> None:
    assert guard_git.GitRepo().drops_pushed_commits(clone, target) is drops


def test_git_repo_reads_aliases(clone: Path) -> None:
    repo = guard_git.GitRepo()

    assert repo.alias(clone, "st") == "status --short"
    assert repo.alias(clone, "nope") is None


def test_git_repo_fails_closed_when_git_cannot_run(
    clone: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PATH", "")

    with pytest.raises(guard_git.Unparseable, match="couldn't ask git"):
        guard_git.GitRepo().current_branch(clone)


def test_the_real_repository_state_drives_the_verdict(clone: Path) -> None:
    repo = guard_git.GitRepo()

    assert guard_git.decide("git commit --amend --no-edit", clone, repo) == guard_git.ALLOW
    assert guard_git.decide("git reset --hard HEAD~2", clone, repo).block is not None
    git(clone, "switch", "--quiet", "-c", "main")
    assert guard_git.decide("git commit -m x", clone, repo).block is not None


def test_the_script_runs_main_with_the_real_repository(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(hook_input("git push --force")))

    with pytest.raises(SystemExit) as exit_info:
        runpy.run_path(guard_git.__file__, run_name="__main__")

    assert exit_info.value.code == 2
    assert "force push" in capsys.readouterr().err


# --- Review DC-2026-10-08 findings ----------------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "git switch main && git merge s1",
        "git checkout main && git commit -m x",
        "git checkout main; git push",
        "git switch -c x && git push origin HEAD",
        "git checkout -b x && git commit --amend --no-edit",
        "git switch main && git reset --hard HEAD~1",
        "git co main && git commit -m x",  # an alias for checkout
        "git switch main && bash -c 'git commit -m x'",
    ],
)
def test_a_branch_switch_earlier_in_the_command_makes_the_branch_unknown(command: str) -> None:
    repo = FakeRepo(branch="s1", drops={"HEAD~1": False}, aliases={"co": "checkout"})

    assert "can't tell which branch it runs on" in block_message(command, repo)


@pytest.mark.parametrize(
    "command",
    [
        "git checkout -- docs/a.md && git commit -m x",  # restores a path; HEAD doesn't move
        "git switch s1",
        "git switch main && git status",
        "git switch --help && git commit -m x",
        "git switch -h && git commit -m x",
    ],
)
def test_commands_around_a_branch_switch_that_dont_depend_on_it_are_allowed(command: str) -> None:
    assert verdict(command, FakeRepo(branch="s1")) == guard_git.ALLOW


@pytest.mark.parametrize(
    "command",
    [
        "SKIP=ruff-backend git commit -m x",
        "env SKIP=ruff-backend git commit -m x",
        "GIT_CONFIG_PARAMETERS=\"'core.hooksPath=/dev/null'\" git commit -m x",
        "GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.hooksPath GIT_CONFIG_VALUE_0=x git push",
        "export SKIP=ruff-backend && git commit -m x",
        "git config core.hooksPath /dev/null",
        "git config --local core.hooksPath /dev/null",
        "git config set core.hookspath /dev/null",
    ],
)
def test_other_ways_to_skip_hooks_are_blocked(command: str) -> None:
    assert "skip" in block_message(command)


@pytest.mark.parametrize(
    "command",
    [
        "git config --get core.hooksPath",
        "git config --unset core.hooksPath",
        "git config user.name x",
        "SKIP=x echo hi && git status",
        "export PAGER=cat && git log",
    ],
)
def test_reading_hook_settings_and_unrelated_variables_are_allowed(command: str) -> None:
    assert verdict(command) == guard_git.ALLOW


@pytest.mark.parametrize(
    "command",
    [
        "git push origin {s1,main}",
        "git push origin s{1..2}",
        "git push origin ma$'in'",
        'git push origin $"main"',
    ],
)
def test_brace_expansion_and_special_quoting_are_unknown(command: str) -> None:
    assert "can't tell where" in block_message(command)


@pytest.mark.parametrize(
    ("command", "reason"),
    [("git status $'unclosed", "an unclosed $'"), ("git status $'a\\'", "an unclosed $'")],
)
def test_an_unclosed_ansi_c_quote_is_blocked(command: str, reason: str) -> None:
    assert f"({reason})" in block_message(command)


@pytest.mark.parametrize(
    "command",
    [
        "git log --format='{a,b}'",
        "{ git status; }",
        'git log --format="{a,b}"',
        "git commit -m $'two\\nlines'",
    ],
)
def test_quoted_braces_and_command_groups_are_allowed(command: str) -> None:
    assert verdict(command) == guard_git.ALLOW


@pytest.mark.parametrize(
    "command",
    [
        "gh api -X POST repos/o/r/merges -f base=main -f head=s1",
        "gh api graphql -F query=@merge.graphql",
    ],
)
def test_other_merge_api_calls_ask_the_owner(command: str) -> None:
    result = verdict(command)

    assert result.block is None
    assert result.ask is not None


@pytest.mark.parametrize(
    "command",
    [
        "git cherry-pick abc123",
        "git revert HEAD",
        "git am fix.patch",
        "git pull origin s1",
        "git pull",
    ],
)
def test_commands_that_make_commits_on_main_are_blocked(command: str) -> None:
    assert "on `main`" in block_message(command, ON_MAIN)


@pytest.mark.parametrize(
    ("command", "repo"),
    [
        ("git pull --ff-only", ON_MAIN),
        ("git cherry-pick --abort", ON_MAIN),
        ("git cherry-pick abc123", FakeRepo(branch="s1")),
        ("git pull origin main", FakeRepo(branch="s1")),
    ],
)
def test_fast_forward_pulls_and_work_off_main_are_allowed(command: str, repo: FakeRepo) -> None:
    assert verdict(command, repo) == guard_git.ALLOW


# --- Review DC-2026-10-08, pass 2 ---------------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "bash -c 'git switch main' && git commit -m x",
        "x=$(git switch main); git commit -m x",
        "git switch main && echo $(git commit -m x)",
        "git switch main && echo $(git push)",
        "git commit -m x && git switch main",  # order within a line can't be trusted
        "gh pr checkout 3 && git push",
        "gh co 3 && git commit -m x",
    ],
)
def test_a_branch_switch_anywhere_in_the_line_makes_the_branch_unknown(command: str) -> None:
    assert "can't tell which branch it runs on" in block_message(command, FakeRepo(branch="s1"))


@pytest.mark.parametrize(
    "command",
    [
        "SKIP=ruff-backend bash -c 'git commit -m x'",
        "env SKIP=ruff-backend sh -c 'git commit -m x'",
        "SKIP=ruff-backend eval git commit -m x",
        "git pull --no-verify",
        "git am --no-verify fix.patch",
        "git config --add core.hooksPath /dev/null",
    ],
)
def test_more_ways_to_skip_hooks_are_blocked(command: str) -> None:
    assert "hook" in block_message(command)


@pytest.mark.parametrize(
    "command",
    [
        "GIT_CONFIG_NOSYSTEM=1 git status",
        "git config core.hooksPath",  # no value: reads it
        "git config --show-origin core.hooksPath",
        "git config --get-all core.hooksPath",
        "git config --get-regexp core.hooksPath",
        "git config get core.hooksPath",
        "git config --list",
        "git config -l",
        "git config list",
        "git config --unset-all core.hooksPath",
        "git config unset core.hooksPath",
    ],
)
def test_reading_or_unsetting_hook_settings_is_allowed(command: str) -> None:
    assert verdict(command) == guard_git.ALLOW


@pytest.mark.parametrize(
    "command",
    [
        "git push origin {'main',s1}",
        'git push origin {"main",s1}',
        "git push origin {a,{main,b}}",
        "git push origin {'a b',main}",  # a quoted space doesn't end the expansion
    ],
)
def test_brace_expansion_with_quotes_or_nesting_is_unknown(command: str) -> None:
    assert "can't tell where" in block_message(command)


@pytest.mark.parametrize(
    "command",
    [
        "git log {x}",  # not an expansion: no comma or ..
        "git log {a\\,b}",  # an escaped comma
        "echo {a,b && git status",  # stops at a space: not an expansion
        "git push origin s1 {a,b",  # never closed
        "git push origin \\{main,x\\}",  # escaped braces are literal text
    ],
)
def test_braces_that_bash_does_not_expand_are_literal(command: str) -> None:
    assert verdict(command) == guard_git.ALLOW


def test_an_unclosed_quote_inside_braces_is_blocked() -> None:
    assert "(an unclosed ')" in block_message("echo {'a && git status")


@pytest.mark.parametrize(
    "command",
    [
        "git pull --ff-only --no-ff origin main",  # the last fast-forward flag wins
        "git pull --ff-only origin s1",  # fast-forwards main to another branch
        "git pull --ff origin main",
    ],
)
def test_pulls_on_main_other_than_fast_forwarding_main_are_blocked(command: str) -> None:
    assert "on `main`" in block_message(command, ON_MAIN)


@pytest.mark.parametrize(
    "command",
    [
        "git pull --ff-only origin main",
        "git pull --no-ff --ff-only",
        "git pull --ff-only origin refs/heads/main",
        "git cherry-pick --quit",
        "git cherry-pick --skip",
    ],
)
def test_fast_forwarding_main_and_abandoning_on_main_are_allowed(command: str) -> None:
    assert verdict(command, ON_MAIN) == guard_git.ALLOW


@pytest.mark.parametrize(
    "command",
    [
        "gh api graphql --field=query=@m.graphql",
        "gh api graphql -Fquery=@m.graphql",
        "gh api graphql --raw-field=query=@m.graphql",
        "gh api graphql -fquery=@m.graphql",
    ],
)
def test_a_graphql_query_read_from_a_file_asks_the_owner(command: str) -> None:
    assert verdict(command).ask is not None


# --- Review DC-2026-10-08, pass 3 ---------------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "git config core.hooksPath get",
        "git config core.hooksPath unset",
        "git config core.hooksPath list",
    ],
)
def test_a_subcommand_word_as_the_value_still_sets_hooks_path(command: str) -> None:
    assert "setting `core.hooksPath`" in block_message(command)


def test_a_commit_where_no_branch_is_checked_out_is_blocked() -> None:
    command = "git worktree add ../w main && git -C ../w commit -m x"

    message = block_message(command, FakeRepo(branch=None))

    assert "no branch is checked out at /work/w" in message


@pytest.mark.parametrize(
    "command",
    [
        "git switch -C main",
        "git checkout -B main origin/s1",
        "git switch -c main",
        "git branch -f main s1",
        "git branch -M s1 main",
        "git fetch . s1:main",
        "git fetch origin +s1:refs/heads/main",
        "git pull origin s1:main",
        "git update-ref refs/heads/main HEAD",
    ],
)
def test_moving_the_local_main_branch_is_blocked(command: str) -> None:
    assert "would move the local `main` branch" in block_message(command)


@pytest.mark.parametrize(
    "command",
    [
        "git switch -c s2",
        "git branch -f s1-old s1",
        "git branch main-notes",
        "git fetch origin main",
        "git fetch origin main:refs/remotes/origin/main",
        "git branch --list main",
    ],
)
def test_other_branch_changes_are_allowed(command: str) -> None:
    assert verdict(command) == guard_git.ALLOW


def test_writing_head_with_symbolic_ref_is_a_branch_switch() -> None:
    message = block_message("git symbolic-ref HEAD refs/heads/main && git commit -m x")

    assert "can't tell which branch it runs on" in message


def test_reading_head_with_symbolic_ref_is_not_a_switch() -> None:
    assert verdict("git symbolic-ref HEAD && git commit -m x") == guard_git.ALLOW


@pytest.mark.parametrize(
    "command",
    [
        "gh api -X PATCH repos/o/r/git/refs/heads/main -f sha=abc",
        "gh api repos/o/r/git/refs/heads/main",
        "gh api -X PUT repos/o/r/contents/README.md -f message=x -f content=eA==",
        "gh api --method=DELETE repos/o/r/contents/a.md -f sha=abc",
    ],
)
def test_api_writes_to_main_ask_the_owner(command: str) -> None:
    result = verdict(command)

    assert result.block is None
    assert result.ask is not None
    assert "can change `main`" in result.ask


@pytest.mark.parametrize(
    "command",
    [
        "gh api repos/o/r/contents/README.md",
        "gh api -X PATCH repos/o/r/git/refs/heads/s1 -f sha=abc",
        "gh api --method GET repos/o/r/contents/a.md",
        "gh api -XGET repos/o/r/contents/a.md",
    ],
)
def test_api_reads_and_other_branches_do_not_ask(command: str) -> None:
    assert verdict(command) == guard_git.ALLOW


@pytest.mark.parametrize("command", ["git cherry-pick --continue", "git am --continue"])
def test_continuing_on_main_makes_a_commit_and_is_blocked(command: str) -> None:
    assert "on `main`" in block_message(command, ON_MAIN)


# --- Review DC-2026-10-08, pass 4 ---------------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "git config core.hooksPath --get",  # legacy form: everything after the key is a value
        "git config core.hooksPath x --get",
        "git config core.hooksPath y --unset",
        "git config core.hooksPath z --list",
        "git config --local core.hooksPath /dev/null",
    ],
)
def test_legacy_config_words_after_the_key_are_values(command: str) -> None:
    assert "setting `core.hooksPath`" in block_message(command)


@pytest.mark.parametrize(
    "command",
    [
        "git config user.name core.hooksPath",  # sets another key
        "git config --get core.hooksPath",
        "git config",
        "git config unset core.hooksPath",
    ],
)
def test_config_that_does_not_set_hooks_path_is_allowed(command: str) -> None:
    assert verdict(command) == guard_git.ALLOW


@pytest.mark.parametrize(
    "command",
    [
        "git switch -Cmain",
        "git switch --force-create=main",
        "git switch --create=main",
        "git switch --create main",
        "git switch -qC main",
        "git checkout -Bmain origin/s1",
        "git branch -fM main",
        "git branch --force main s1",
        "git branch --move=s1 main",
        "git worktree add -B main ../w",
        "git worktree add -bmain ../w",
    ],
)
def test_attached_and_bundled_forms_of_moving_main_are_blocked(command: str) -> None:
    assert "would move the local `main` branch" in block_message(command)


@pytest.mark.parametrize(
    "command",
    ["git switch -Cs2", "git worktree add -b s2 ../w", "git worktree list", "git branch -d s1-old"],
)
def test_creating_or_listing_other_branches_is_allowed(command: str) -> None:
    assert verdict(command) == guard_git.ALLOW


@pytest.mark.parametrize(
    "command",
    ["git reset --hard origin/s1", "git reset --soft abc123", "git update-ref HEAD abc123"],
)
def test_moving_main_to_another_commit_is_blocked_on_main(command: str) -> None:
    assert "would move the local `main` branch" in block_message(command, ON_MAIN)


@pytest.mark.parametrize(
    "command",
    [
        "git reset --hard origin/main",
        "git reset --hard HEAD",
        "git reset --hard main",
        "git reset --hard refs/remotes/origin/main",
    ],
)
def test_resetting_main_to_main_is_allowed(command: str) -> None:
    assert verdict(command, ON_MAIN) == guard_git.ALLOW


@pytest.mark.parametrize(
    ("command", "repo"),
    [
        ("git reset --hard origin/s1", FakeRepo(branch="s1")),
        ("git update-ref HEAD abc123", FakeRepo(branch="s1")),
        ("git update-ref refs/heads/s2 abc123", ON_MAIN),
    ],
)
def test_moving_other_branches_is_allowed(command: str, repo: FakeRepo) -> None:
    assert verdict(command, repo) == guard_git.ALLOW


def test_update_ref_reading_stdin_is_blocked() -> None:
    message = block_message("echo 'update refs/heads/main abc' | git update-ref --stdin")

    assert "(`git update-ref --stdin` reads its updates from stdin)" in message


def test_an_attached_method_is_read() -> None:
    result = verdict("gh api -XPUT repos/o/r/contents/a.md -f message=x")

    assert result.ask is not None
    assert "can change `main`" in result.ask


# --- Review DC-2026-10-08, pass 5 ---------------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "git config -f .git/config core.hooksPath /dev/null",
        "git config --file .git/config core.hooksPath /dev/null",
        "git config --comment hi core.hooksPath y",
        "git config --type bool core.hooksPath x",
        "git config set --local core.hooksPath x",
    ],
)
def test_an_option_value_before_the_key_does_not_hide_a_write(command: str) -> None:
    assert "setting `core.hooksPath`" in block_message(command)


@pytest.mark.parametrize(
    "command",
    [
        "git config -f .git/config --get core.hooksPath",
        "git config get --local core.hooksPath",
        "git config get core.hooksPath --show-origin",  # a read subcommand, a word after the key
    ],
)
def test_reads_with_options_are_allowed(command: str) -> None:
    assert verdict(command) == guard_git.ALLOW


def test_update_ref_with_a_reason_still_moves_head_on_main() -> None:
    message = block_message("git update-ref -m reason HEAD abc123", ON_MAIN)

    assert "would move the local `main` branch" in message


# --- Review DC-2026-10-08, pass 6 ---------------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "git config --comment --get core.hooksPath /dev/null",
        "git config --get core.hooksPath pattern",  # a rare read, blocked to fail closed
    ],
)
def test_any_word_after_the_key_in_the_legacy_form_is_a_write(command: str) -> None:
    assert "setting `core.hooksPath`" in block_message(command)


@pytest.mark.parametrize("command", ["$(echo git) push origin main", "G=git; $G push origin main"])
def test_a_command_name_known_only_at_run_time_is_blocked(command: str) -> None:
    assert "(a command whose name is only known at run time)" in block_message(command)


@pytest.mark.parametrize(
    "command", ["GIT_DIR=/x/.git git commit -m x", "GIT_WORK_TREE=/x git commit -m x"]
)
def test_git_dir_from_the_environment_makes_the_repository_unknown(command: str) -> None:
    assert "`GIT_" in block_message(command)
    assert "names another repository" in block_message(command)


def test_git_dir_on_a_command_that_needs_no_repository_state_is_allowed() -> None:
    assert verdict("GIT_DIR=/x/.git git log") == guard_git.ALLOW
