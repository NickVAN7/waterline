"""The git guard (.claude/hooks/guard_git.py), an allow-list (DL-26) that keeps Claude from
committing or merging on `main` (DL-21), pushing to `main` (DL-22), rewriting pushed history
(DL-23), and skipping hooks (DL-24), and asks the owner before merges and API writes (DL-25).

Most tests use a fake repository state. `GitRepo`, and the effect of every allowed write form,
are tested against real git at the end.
"""

import io
import json
import re
import runpy
import shlex
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
    # name -> the ref it names; anything else is a commit expression (empty, as git reports it)
    refs: dict[str, str | None] = field(default_factory=dict[str, str | None])
    asked: list[Path] = field(default_factory=list[Path])

    def current_branch(self, cwd: Path) -> str | None:
        self.asked.append(cwd)
        return self.branch

    def push_destination(self, cwd: Path) -> str | None:
        return self.push_to

    def head_on_remote(self, cwd: Path) -> bool:
        return self.head_pushed

    def drops_pushed_commits(self, cwd: Path, target: str) -> bool | None:
        return self.drops.get(target)

    def full_ref(self, cwd: Path, name: str) -> str | None:
        return self.refs.get(name, "")

    def remotes(self, cwd: Path) -> list[str]:
        return ["origin"]


ON_MAIN = FakeRepo(branch="main", push_to="origin/main")
MAIN_TRACKING_MAIN = FakeRepo(
    branch="main", push_to="origin/main", refs={"@{upstream}": "refs/remotes/origin/main"}
)


def verdict(
    command: str, repo: FakeRepo | None = None, cwd: Path | None = CWD
) -> guard_git.Verdict:
    return guard_git.decide(command, cwd, repo or FakeRepo())


def block_message(command: str, repo: FakeRepo | None = None, cwd: Path | None = CWD) -> str:
    result = verdict(command, repo, cwd)
    assert result.block is not None, f"{command!r} was not blocked"
    return result.block


# --- The shape of a call (DL-26) --------------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "uv run wl check",
        "ls -la",
        "grep -rn 'git push' docs",  # git as data
        "cat .git/config",
        "ls .git && wc -l .git/config",
        "grep -c gh notes.txt | head -1",
        "echo use git switch",
    ],
)
def test_commands_where_git_is_only_data_are_allowed(command: str) -> None:
    repo = FakeRepo()

    assert verdict(command, repo) == guard_git.ALLOW
    assert repo.asked == []


@pytest.mark.parametrize(
    "command",
    [
        "git status && git log",
        "git status; ls",
        "git status | head -5",
        "cd backend && git status",
        "(git status)",
        "FOO=1 git status",
        "env git status",
        "bash -c 'git status'",
        "sh -c 'git push'",
        "eval git status",
        "ls | xargs git add",
        "uv run git status",
        "sudo git status",
        "echo $(git rev-parse HEAD)",
        "echo `git rev-parse HEAD`",
        "git log $REV",
        "git push origin {s1,main}",
        "git push origin ma$'in'",
        "python3 - <<'EOF'\nprint('git')\nEOF",
        "cat <<EOF\ngit push\nEOF",
        "x=$(gh pr list)",
    ],
)
def test_a_git_call_must_be_one_literal_command(command: str) -> None:
    assert "must be that one command and nothing else" in block_message(command)


@pytest.mark.parametrize("command", ["git commit -m 'unclosed", 'echo "git', "echo $(git status"])
def test_a_git_call_it_cannot_parse_is_blocked(command: str) -> None:
    assert "it can't parse this command" in block_message(command)


@pytest.mark.parametrize("command", ["echo 'unclosed", "ls $(", "cat <<EOF", "echo $(echo ${x)"])
def test_an_unparseable_command_that_is_not_about_git_is_left_to_bash(command: str) -> None:
    assert verdict(command) == guard_git.ALLOW


def test_redirecting_output_is_still_one_command() -> None:
    assert verdict("git log --oneline > /tmp/log.txt 2>&1") == guard_git.ALLOW


# --- The git allow-list (DL-26) ---------------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "git",
        "git status",
        "git log --oneline -5",
        "git diff HEAD~1 -- docs",
        "git show --stat HEAD",
        "git rev-parse --abbrev-ref HEAD",
        "git ls-files docs",
        "git ls-tree HEAD",
        "git blame README.md",
        "git grep -n TODO",
        "git merge-base HEAD origin/main",
        "git rev-list --count HEAD",
        "git cat-file -t HEAD",
        "git hash-object tests/a.py",
        "git describe --tags",
        "git shortlog -sn",
        "git --no-pager log -1",
        "git -C /work/other status",
        "git add -A",
        "git add docs/a.md backend/x.py",
        "git add -u",
        "git add -- -weird-name.md",
        "git rm --cached old.txt",
        "git rm -r build",
        "git mv a.md b.md",
        "git restore --staged a.md",
        "git restore a.md",
        "git branch",
        "git branch --show-current",
        "git branch -a -vv",
        "git branch --list 's1*'",
        "git remote",
        "git remote -v",
        "git config --get user.name",
        "git config get core.bare",
        "git config --list",
        "git config -l",
        "git config list",
        "git fetch",
        "git fetch origin",
        "git fetch origin s1",
        "git fetch --prune origin",
        "git stash",
        "git stash push -u -m wip",
        "git stash pop",
        "git stash drop",
        "git stash list",
        "git stash show",
        "git stash apply",
        "git switch s1",
        "git switch main",
        "git switch -c s2",
        "git checkout -- docs/a.md",
        "git merge --abort",
        "git rebase --abort",
        "git cherry-pick --abort",
        "git revert --abort",
        "git am --abort",
    ],
)
def test_allowed_git_forms_pass(command: str) -> None:
    assert verdict(command) == guard_git.ALLOW


@pytest.mark.parametrize(
    ("command", "subcommand"),
    [
        ("git add -f secret.env", "add"),
        ("git add -p", "add"),
        ("git rm -f a.md", "rm"),
        ("git mv -f a b", "mv"),
        ("git restore --source=HEAD~2 a.md", "restore"),
        ("git branch -f main s1", "branch"),
        ("git branch -D s1-old", "branch"),
        ("git branch -m s1 main", "branch"),
        ("git branch new-branch", "branch"),
        ("git remote add evil url", "remote"),
        ("git config core.hooksPath /dev/null", "config"),
        ("git config core.hooksPath --get", "config"),
        ("git config --get core.hooksPath pattern", "config"),
        ("git config --get --global", "config"),
        ("git config --unset core.hooksPath", "config"),
        ("git config set user.name x", "config"),
        ("git fetch origin s1:main", "fetch"),
        ("git fetch origin +s1", "fetch"),
        ("git fetch --all", "fetch"),
        ("git fetch origin s1 s2", "fetch"),
        ("git stash clear", "stash"),
        ("git stash pop stash@{1}", "stash"),
        ("git stash push --keep-index", "stash"),
        ("git stash push -m", "stash"),
        ("git switch -C main", "switch"),
        ("git switch --force-create main", "switch"),
        ("git switch -", "switch"),
        ("git switch --detach HEAD~1", "switch"),
        ("git checkout main", "checkout"),
        ("git checkout --", "checkout"),
        ("git checkout -b s2", "checkout"),
        ("git checkout -B main", "checkout"),
        ("git merge s1", "merge"),
        ("git merge --ff-only origin/s1", "merge"),
        ("git rebase main", "rebase"),
        ("git rebase --continue", "rebase"),
        ("git cherry-pick abc123", "cherry-pick"),
        ("git revert HEAD", "revert"),
        ("git am fix.patch", "am"),
        ("git update-ref refs/heads/main HEAD", "update-ref"),
        ("git symbolic-ref HEAD refs/heads/main", "symbolic-ref"),
        ("git worktree add ../w main", "worktree"),
        ("git tag v1", "tag"),
        ("git reflog expire --all", "reflog"),
        ("git filter-branch", "filter-branch"),
        ("git st", "st"),  # aliases aren't followed: only listed subcommands run
        ("git -c core.hooksPath=/dev/null commit -m x", "-c"),
        ("git --git-dir=/x/.git status", "--git-dir=/x/.git"),
        ("git -C", "-C"),
    ],
)
def test_git_forms_outside_the_allow_list_are_blocked(command: str, subcommand: str) -> None:
    message = block_message(command)

    assert f"this `git {subcommand}` isn't in the git guard's allow-list" in message
    assert "ask the owner to run (`! <command>`)" in message


# --- DL-21: no commits or merges on main ------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "git commit -m x",
        "git commit -am x",
        "git commit -q --allow-empty -m x",
        "git commit -F - <<'EOF'\nIt's a message\nEOF",
        "git commit --file notes.txt",
        "git commit --amend --no-edit",
    ],
)
def test_commit_forms_are_allowed_off_main(command: str) -> None:
    assert verdict(command, FakeRepo(branch="s1")) == guard_git.ALLOW


@pytest.mark.parametrize("command", ["git commit -m x", "git commit -F - <<'EOF'\nx\nEOF"])
def test_a_commit_on_main_is_blocked(command: str) -> None:
    assert "`git commit` on `main`" in block_message(command, ON_MAIN)


@pytest.mark.parametrize(
    ("target", "full_ref"),
    [
        ("origin/s1", "refs/remotes/origin/s1"),
        ("abc123", ""),  # a commit, not a ref
        ("fix/main", "refs/heads/fix/main"),  # a branch whose name ends in main
        ("v1", "refs/tags/v1"),
    ],
)
def test_a_reset_on_main_to_another_commit_is_blocked(target: str, full_ref: str) -> None:
    repo = FakeRepo(branch="main", drops={target: False}, refs={target: full_ref})

    message = block_message(f"git reset --hard {target}", repo)

    assert "on `main` would move it to another commit" in message


@pytest.mark.parametrize(
    ("target", "full_ref"),
    [
        ("origin/main", "refs/remotes/origin/main"),
        ("upstream/main", "refs/remotes/upstream/main"),
        ("main", "refs/heads/main"),
        ("HEAD", "refs/heads/main"),  # HEAD names main while main is checked out
    ],
)
def test_a_reset_on_main_to_main_itself_is_allowed(target: str, full_ref: str) -> None:
    repo = FakeRepo(branch="main", drops={target: False}, refs={target: full_ref})

    assert verdict(f"git reset --hard {target}", repo) == guard_git.ALLOW


@pytest.mark.parametrize(
    ("command", "repo"),
    [
        ("git pull --ff-only", MAIN_TRACKING_MAIN),
        ("git pull --ff-only origin main", ON_MAIN),
        ("git pull --ff-only origin s1", FakeRepo(branch="s1")),
    ],
)
def test_fast_forward_pulls_are_allowed(command: str, repo: FakeRepo) -> None:
    assert verdict(command, repo) == guard_git.ALLOW


@pytest.mark.parametrize(
    "command",
    [
        "git pull --ff-only origin s1",
        # a path to another repository isn't a configured remote (pass 3, finding 3; verified)
        "git pull --ff-only copy main",
    ],
)
def test_a_pull_on_main_from_another_branch_is_blocked(command: str) -> None:
    assert "only from `main`" in block_message(command, ON_MAIN)


@pytest.mark.parametrize("option", ["--show-token", "-t", "--hostname"])
def test_gh_auth_status_is_allowed_only_bare(option: str) -> None:
    message = block_message(f"gh auth status {option}")

    assert "`gh auth status` is allowed only with no options" in message


@pytest.mark.parametrize("command", ["git hash-object -w f", "git hash-object --stdin"])
def test_hash_object_that_writes_or_reads_stdin_is_blocked(command: str) -> None:
    assert "this `git hash-object` isn't in the git guard's allow-list" in block_message(command)


@pytest.mark.parametrize(
    "command",
    [
        "git pull",
        "git pull origin s1",
        "git pull --rebase",
        "git pull --ff-only --no-ff",
        "git pull --ff-only origin",
    ],
)
def test_other_pulls_are_blocked(command: str) -> None:
    assert "this `git pull` isn't in the git guard's allow-list" in block_message(command)


def test_creating_main_with_switch_is_blocked() -> None:
    assert "would create or reset `main`" in block_message("git switch -c main")


# --- DL-22: no pushes to main -------------------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    ["git push origin s1", "git push -u origin s1", "git push --set-upstream origin feature/x"],
)
def test_a_push_of_a_literal_slice_branch_is_allowed(command: str) -> None:
    assert verdict(command) == guard_git.ALLOW


def test_a_bare_push_off_main_with_a_slice_upstream_is_allowed() -> None:
    assert verdict("git push", FakeRepo(branch="s1", push_to="origin/s1")) == guard_git.ALLOW


@pytest.mark.parametrize(
    "command",
    [
        "git push origin main",
        "git push origin feature/main",
        "git push origin HEAD",
        "git push origin refs/heads/s1",
    ],
)
def test_a_push_to_main_or_a_name_that_could_be_it_is_blocked(command: str) -> None:
    assert "would update `main`" in block_message(command)


@pytest.mark.parametrize(
    ("repo", "message"),
    [
        (FakeRepo(branch="main", push_to="origin/main"), "this push would update `main`"),
        (
            FakeRepo(branch="s1", push_to="origin/main"),
            "needs a push destination that isn't `main`",
        ),
        (FakeRepo(branch="s1", push_to=None), "(it has none)"),
    ],
)
def test_a_bare_push_to_main_or_without_an_upstream_is_blocked(
    repo: FakeRepo, message: str
) -> None:
    assert message in block_message("git push", repo)


@pytest.mark.parametrize(
    "command",
    [
        "git push origin",
        "git push origin s1 s2",
        "git push origin s1:main",
        "git push origin +s1",
        "git push origin :s1",
        "git push -u",
    ],
)
def test_push_shapes_outside_the_allow_list_are_blocked(command: str) -> None:
    assert "this `git push` isn't in the git guard's allow-list" in block_message(command)


# --- DL-23: pushed history is never rewritten ----------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "git push -f origin s1",
        "git push --force origin s1",
        "git push --force-with-lease origin s1",
        "git push --mirror origin",
        "git push --delete origin s1",
        "git push -d origin s1",
        "git push --prune origin",
        "git push --all origin",
    ],
)
def test_force_and_destructive_pushes_are_blocked(command: str) -> None:
    assert "this `git push` isn't in the git guard's allow-list" in block_message(command)


def test_amending_a_pushed_head_is_blocked() -> None:
    message = block_message("git commit --amend --no-edit", FakeRepo(head_pushed=True))

    assert "HEAD is already on the remote" in message


@pytest.mark.parametrize("command", ["git reset --hard HEAD~2", "git reset HEAD~2"])
def test_a_reset_that_drops_pushed_commits_is_blocked(command: str) -> None:
    message = block_message(command, FakeRepo(drops={"HEAD~2": True}))

    assert "would drop commits that are already on the remote" in message


@pytest.mark.parametrize(
    "command",
    [
        "git reset",
        "git reset -q",
        "git reset --hard",
        "git reset -- a.md",
        "git reset HEAD -- a.md",
        "git reset a.md",  # not a commit: a path
        "git reset a.md b.md",
        "git reset --soft HEAD~1",  # drops only unpushed commits
    ],
)
def test_resets_that_keep_pushed_history_are_allowed(command: str) -> None:
    repo = FakeRepo(drops={"HEAD~1": False, "a.md": None})

    assert verdict(command, repo) == guard_git.ALLOW


@pytest.mark.parametrize(
    "command",
    [
        "git reset --soft --hard HEAD~1",
        "git reset --hard a.md b.md",
        "git reset --hard a.md",
        "git reset --merge HEAD~1",
        "git reset HEAD~1 -- a.md",
        "git reset --",
    ],
)
def test_reset_shapes_outside_the_allow_list_are_blocked(command: str) -> None:
    repo = FakeRepo(drops={"HEAD~1": False, "a.md": None})

    assert "this `git reset` isn't in the git guard's allow-list" in block_message(command, repo)


# --- DL-24: hooks are never skipped ---------------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "git commit --no-verify -m x",
        "git commit -n -m x",
        "git commit -nm x",
        "git commit -m x a.md",  # paths aren't allowed either
        "git commit -m",
        "git push --no-verify origin s1",
        "git config core.hooksPath x",
    ],
)
def test_options_that_skip_hooks_are_blocked(command: str) -> None:
    assert "isn't in the git guard's allow-list" in block_message(command)


@pytest.mark.parametrize(
    "command",
    ["SKIP=ruff git commit -m x", "GIT_CONFIG_PARAMETERS=x git commit -m x", "env SKIP=x git push"],
)
def test_environment_that_skips_hooks_is_blocked(command: str) -> None:
    assert "must be that one command and nothing else" in block_message(command)


def test_a_heredoc_is_allowed_only_for_a_commit_message() -> None:
    message = block_message("git log -F - <<'EOF'\nx\nEOF")

    assert "a heredoc is allowed only for `git commit -F -`" in message


@pytest.mark.parametrize(
    "command",
    [
        # bash runs these in an unquoted heredoc body (review DC-2026-10-08b, finding 1)
        "git commit --allow-empty -F - <<EOF\nfix: document `git push origin HEAD:main`\nEOF",
        "git commit -F - <<EOF\n$(touch /tmp/x)\nEOF",
        "git commit -F - <<-EOF\n\tplain text\n\tEOF",
    ],
)
def test_an_unquoted_commit_message_heredoc_is_blocked(command: str) -> None:
    assert "an unquoted heredoc runs the `$(...)` and backticks" in block_message(command)


@pytest.mark.parametrize(
    "command",
    [
        "git commit -F - <<'EOF'\nfix: document `git push` and $(this)\nEOF",
        'git commit -F - <<"EOF"\ntext\nEOF',
        "git commit -F - <<\\EOF\ntext\nEOF",
    ],
)
def test_a_quoted_commit_message_heredoc_is_allowed(command: str) -> None:
    assert verdict(command) == guard_git.ALLOW


@pytest.mark.parametrize(
    "command",
    [
        "printf '[core]\\n\\thooksPath = /x\\n' >> .git/config",
        "echo -n > .git/hooks/pre-commit",
        "git show HEAD:f > .git/hooks/pre-commit",
        "cat notes > .g''it/config",  # quoting doesn't hide the directory
        "grep -rn git docs > $OUT",  # a target named only at run time
        "git status > $(git push --force origin main)",  # a substitution in a redirect runs
    ],
)
def test_a_redirect_into_the_git_directory_is_blocked(command: str) -> None:
    assert "a redirect into `.git/`" in block_message(command)


@pytest.mark.parametrize(
    "command",
    [
        # the global config can set core.hooksPath too (review DC-2026-10-08b, pass 2, finding 3)
        "echo '[core]' >> ~/.gitconfig",
        "echo x >> ~/.config/git/config",
        "git show HEAD:f > ~/.gitconfig",
        "cat hooks.cfg > /home/someone/.gitconfig",
    ],
)
def test_a_redirect_into_a_git_config_file_is_blocked(command: str) -> None:
    assert "a git config file" in block_message(command)


def test_copying_over_the_global_config_is_blocked() -> None:
    assert "must be that one command and nothing else" in block_message("cp hooks.cfg ~/.gitconfig")


@pytest.mark.parametrize(
    "command",
    [
        # bash runs a substitution nested in an expansion (pass 2, finding 1; verified)
        "echo ${x:-$(git push origin HEAD:main)}",
        'echo "${x:-$(git push origin HEAD:main)}"',
        "echo ${x:-`git push origin HEAD:main`}",
        'echo $"$(git push origin HEAD:main)"',
        "ls ${x:-$(git status)}",
        "echo $(g''it push origin HEAD:main)",  # quoting can't hide git inside a substitution
        "echo $(echo ${x git)",  # a substitution it can't parse that mentions git
        # any expansion, when the call mentions git
        "grep -rn git $DIR",
        "echo git ${HOME}",
        # these evaluate an array subscript, and its $(...), even single-quoted (finding 2)
        "[[ 1 -eq 'a[$(git push origin HEAD:main)]' ]]",
        "test -v 'a[$(git push origin HEAD:main)]'",
        "[ -v 'a[$(git push)]' ]",
        "printf -v 'a[$(git push origin HEAD:main)]' x",
    ],
)
def test_an_expansion_or_evaluating_command_with_git_in_it_is_blocked(command: str) -> None:
    assert "must be that one command and nothing else" in block_message(command)


@pytest.mark.parametrize(
    "command", ["grep -rn git docs > /tmp/out.txt", "git log --oneline > notes/git-log.txt"]
)
def test_a_redirect_elsewhere_is_allowed(command: str) -> None:
    assert verdict(command) == guard_git.ALLOW


@pytest.mark.parametrize(
    "command",
    [
        # bash expands a glob in a redirect target to an existing file (pass 3, finding 5;
        # verified), so these write .git/config without naming it, git or not
        "echo '[core]' >> .gi?/config",
        "echo x > .g*/hooks/pre-commit",
        "echo x > .[g]it/config",
    ],
)
def test_a_glob_in_a_redirect_target_is_blocked(command: str) -> None:
    assert "a glob (`*`, `?`, `[`) in a redirect target" in block_message(command)


@pytest.mark.parametrize(
    "command",
    [
        "echo x > '.gi?/config'",  # quoted: a literal name (verified)
        "ls *.py > files.txt",  # a glob outside the redirect target
    ],
)
def test_a_quoted_glob_or_one_outside_a_redirect_target_is_allowed(command: str) -> None:
    assert verdict(command) == guard_git.ALLOW


@pytest.mark.parametrize(
    "command",
    [
        "sort -o .git/config /dev/null",
        "uniq notes .git/config",
        "rg --pre 'sh -c x' git docs",
        "file -C -m .git/x",
        "less .git/config",
        "man git",
    ],
)
def test_commands_that_can_write_or_run_are_not_data(command: str) -> None:
    assert "must be that one command and nothing else" in block_message(command)


@pytest.mark.parametrize(
    ("command", "option"),
    [
        # run a program (review DC-2026-10-08b, finding 2)
        (
            "git grep \"-Osh -c 'git push origin HEAD:main' sh\" base",
            "-Osh -c 'git push origin HEAD:main' sh",
        ),
        ("git grep --open-files-in-pager=sh base", "--open-files-in-pager=sh"),
        ("git diff --ext-diff", "--ext-diff"),
        ("git log -p --textconv", "--textconv"),
        # write a file (finding 3)
        ("git log -1 --output=.git/config", "--output=.git/config"),
        ("git show --output=x HEAD", "--output=x"),
        ("git diff --output x", "--output"),
        ("git blame --contents x f", "--contents"),
        ("git grep --no-index x", "--no-index"),
    ],
)
def test_read_options_that_run_or_write_are_blocked(command: str, option: str) -> None:
    assert f"not `{option}`, which isn't one" in block_message(command)


@pytest.mark.parametrize(
    "command",
    [
        "git log --format=%h -n5 --since=2.weeks --author=T --",
        "git log --pretty=oneline --decorate=short -3",
        "git diff -U5 --stat --diff-filter=M HEAD~1 -- docs",
        "git status --porcelain=v2 -b",
        "git grep -n -A3 -C 2 -e pattern -- '*.py'",
        "git rev-list --max-count=5 --count HEAD",
        "git blame -L10,20 f",
        "git describe --abbrev=7 --dirty",
        "git shortlog -sne --since=2026-01-01",
    ],
)
def test_listed_read_options_with_values_are_allowed(command: str) -> None:
    assert verdict(command) == guard_git.ALLOW


@pytest.mark.parametrize("upstream", ["refs/remotes/origin/s1", "", None])
def test_a_bare_pull_on_main_whose_upstream_is_not_main_is_blocked(upstream: str | None) -> None:
    # verified with real git: branch.main.merge=refs/heads/s1 makes @{upstream} origin/s1
    repo = FakeRepo(branch="main", refs={"@{upstream}": upstream})

    assert "only from `main`" in block_message("git pull --ff-only", repo)


# --- Which repository and branch ----------------------------------------------------------


def test_git_dash_c_points_the_checks_at_that_repository() -> None:
    repo = FakeRepo()

    verdict("git -C ../other commit -m x", repo, cwd=Path("/work/waterline"))

    assert repo.asked == [Path("/work/other")]


@pytest.mark.parametrize(
    ("command", "cwd", "asked"),
    [
        ("git -C /abs/repo commit -m x", None, Path("/abs/repo")),
        ("git -C ~/repo commit -m x", CWD, Path.home() / "repo"),
    ],
)
def test_an_absolute_or_home_dash_c_needs_no_working_directory(
    command: str, cwd: Path | None, asked: Path
) -> None:
    repo = FakeRepo()

    assert verdict(command, repo, cwd) == guard_git.ALLOW
    assert repo.asked == [asked]


@pytest.mark.parametrize(
    ("command", "cwd"), [("git commit -m x", None), ("git -C relative commit -m x", None)]
)
def test_a_branch_rule_in_an_unknown_repository_is_blocked(command: str, cwd: Path | None) -> None:
    assert "can't tell which repository" in block_message(command, cwd=cwd)


@pytest.mark.parametrize("command", ["git commit -m x", "git push"])
def test_a_branch_rule_where_no_branch_is_checked_out_is_blocked(command: str) -> None:
    message = block_message(command, FakeRepo(branch=None))

    assert "no branch is checked out at /work/waterline" in message


def test_a_read_needs_no_repository() -> None:
    assert verdict("git status", cwd=None) == guard_git.ALLOW


# --- gh (DL-25) ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "gh",
        "gh --version",
        "gh pr create --draft --base main --title x --body y",
        "gh pr view 7 --json state",
        "gh pr list",
        "gh pr checks 7 --watch --interval 30",
        "gh pr diff 7",
        "gh pr status",
        "gh pr ready 7",
        "gh pr edit 7 --title x",
        "gh run list",
        "gh run view 123 --log",
        "gh run watch 123",
        "gh auth status",
        "gh repo view",
        "gh issue list",
        "gh issue view 3",
        "gh -R owner/repo pr view 7",
        "gh --repo=owner/repo pr list",
        "gh api repos/o/r/pulls/7",
        "gh api repos/o/r/commits --paginate --jq '.[].sha'",
    ],
)
def test_allowed_gh_forms_pass(command: str) -> None:
    assert verdict(command) == guard_git.ALLOW


@pytest.mark.parametrize(
    "command",
    [
        "gh pr merge 7 --merge --delete-branch",
        "gh -R o/r pr merge 7",
        "gh api -X PUT repos/o/r/pulls/7/merge",
        "gh api --method PATCH repos/o/r/git/refs/heads/main -f sha=abc",
        "gh api repos/o/r/contents/a.md -f message=x",
        "gh api graphql -f query='query { viewer { login } }'",
        "gh api graphql",
        "gh api --input body.json repos/o/r/merges",
        # single-word forms, each with one endpoint (review DC-2026-10-08b, pass 3, finding 1)
        "gh api -XPUT repos/o/r/pulls/7/merge",
        "gh api --method=PUT repos/o/r/pulls/7/merge",
        "gh api -fmerge_method=merge repos/o/r/pulls/7/merge",
        "gh api --input=b.json repos/o/r/pulls/7/merge",
        "gh api repos/o/r/a repos/o/r/b",
        "gh api",
    ],
)
def test_merges_and_api_calls_other_than_plain_reads_ask_the_owner(command: str) -> None:
    result = verdict(command)

    assert result.block is None
    assert result.ask is not None
    assert "the owner's call (DL-25)" in result.ask


@pytest.mark.parametrize(
    "command", ["gh pr checkout 3", "gh pr close 7", "gh repo delete o/r", "gh pm 7", "gh co 3"]
)
def test_gh_commands_outside_the_allow_list_are_blocked(command: str) -> None:
    assert "isn't in the git guard's allow-list" in block_message(command)


def test_gh_with_a_heredoc_is_blocked() -> None:
    assert "no heredoc with gh" in block_message("gh pr create --body-file - <<'EOF'\nx\nEOF")


# --- The hook's input and output ------------------------------------------------------------------


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
    code, out, err = run_main(monkeypatch, capsys, hook_input("git push --force origin s1"))

    assert (code, out) == (2, "")
    assert err.startswith("Blocked by the git guard: this `git push` isn't in the git guard's")


def test_an_allowed_command_exits_0_silently(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run_main(monkeypatch, capsys, hook_input("git status")) == (0, "", "")


def test_a_merge_prints_an_ask_decision(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out, err = run_main(monkeypatch, capsys, hook_input("gh pr merge 7 --merge"))

    assert (code, err) == (0, "")
    output = json.loads(out)["hookSpecificOutput"]
    assert output["hookEventName"] == "PreToolUse"
    assert output["permissionDecision"] == "ask"
    assert "the owner's call (DL-25)" in output["permissionDecisionReason"]


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


def test_the_script_runs_main_with_the_real_repository(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(hook_input("git push --force origin s1")))

    with pytest.raises(SystemExit) as exit_info:
        runpy.run_path(guard_git.__file__, run_name="__main__")

    assert exit_info.value.code == 2
    assert "isn't in the git guard's allow-list" in capsys.readouterr().err


# --- Real git: GitRepo, and what every allowed form does (DL-26) -------------------------------


def git(cwd: Path, *args: str, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=cwd, input=stdin, capture_output=True, text=True, check=False
    )


def must(cwd: Path, *args: str) -> str:
    result = git(cwd, *args)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


@pytest.fixture
def clone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A clone of a bare remote: `main` (pushed), then `s1` tracking `origin/s1` with one pushed
    and one unpushed commit, and a tracked file `f`. Global and system git config are ignored."""
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    remote, work = tmp_path / "remote.git", tmp_path / "work"
    must(tmp_path, "init", "--quiet", "--bare", "--initial-branch=main", str(remote))
    must(tmp_path, "clone", "--quiet", str(remote), str(work))
    must(work, "config", "user.name", "T")
    must(work, "config", "user.email", "t@example.com")
    (work / "f").write_text("base\n")
    must(work, "add", "f")
    must(work, "commit", "--quiet", "-m", "base")
    must(work, "push", "--quiet", "origin", "main")
    must(work, "switch", "--quiet", "-c", "s1")
    must(work, "commit", "--quiet", "--allow-empty", "-m", "pushed")
    must(work, "push", "--quiet", "-u", "origin", "s1")
    must(work, "commit", "--quiet", "--allow-empty", "-m", "unpushed")
    return work


def snapshot(work: Path) -> set[str]:
    """Every ref in the clone and the remote, and every line of the clone's config; the stash
    ref is left out (a stash isn't history)."""
    local = must(work, "for-each-ref", "--format=local %(refname) %(objectname)").splitlines()
    remote = must(
        work.parent / "remote.git", "for-each-ref", "--format=remote %(refname) %(objectname)"
    ).splitlines()
    config = {f"config {line.strip()}" for line in (work / ".git/config").read_text().splitlines()}
    return {line for line in local + remote if "refs/stash" not in line} | config


def changed(before: set[str], after: set[str]) -> set[str]:
    """The refs (and config lines) that were added, removed, or moved."""
    return {" ".join(line.split()[:2]) for line in before ^ after}


@pytest.mark.parametrize(
    ("setup", "command", "expected"),
    [
        ("true", "git config --get user.name", set[str]()),
        ("true", "git config get user.name", set[str]()),
        ("true", "git config --list", set[str]()),
        ("true", "git config -l", set[str]()),
        ("true", "git config list", set[str]()),
        ("true", "git fetch origin s1", set[str]()),
        # Fetching a remote also records its default branch (a remote-tracking ref).
        ("true", "git fetch --prune origin", {"local refs/remotes/origin/HEAD"}),
        ("true", "git switch main", set[str]()),
        ("true", "git switch -c s2", {"local refs/heads/s2"}),
        ("echo x > f", "git add -A", set[str]()),
        ("echo x > g", "git add g", set[str]()),
        ("true", "git rm -q --cached f", set[str]()),
        ("true", "git mv f f2", set[str]()),
        ("echo x > f; git add f", "git restore --staged f", set[str]()),
        ("echo x > f", "git restore f", set[str]()),
        ("echo x > f", "git checkout -- f", set[str]()),
        ("echo x > f; git add f", "git reset -q", set[str]()),
        ("echo x > f; git add f", "git reset -q -- f", set[str]()),
        ("echo x > f; git add f", "git reset -q HEAD -- f", set[str]()),
        ("echo x > f", "git reset -q --hard", set[str]()),
        ("true", "git reset -q --soft HEAD~1", {"local refs/heads/s1"}),
        ("echo x > g", "git stash push -u -m wip", set[str]()),
        ("echo x > g; git stash push -q -u", "git stash pop", set[str]()),
        ("echo x > g; git stash push -q -u", "git stash drop", set[str]()),
        ("true", "git stash list", set[str]()),
        ("echo x > f; git add f", "git commit -q -m x", {"local refs/heads/s1"}),
        ("echo x > f", "git commit -q -am x", {"local refs/heads/s1"}),
        ("echo x > f; git add f", "git commit -q --amend --no-edit", {"local refs/heads/s1"}),
        ("true", "git push origin s1", {"local refs/remotes/origin/s1", "remote refs/heads/s1"}),
        ("true", "git push", {"local refs/remotes/origin/s1", "remote refs/heads/s1"}),
        # Up to date, so no branch moves; its fetch records the remote's default branch.
        ("true", "git pull --ff-only", {"local refs/remotes/origin/HEAD"}),
        ("true", "git merge --abort", set[str]()),
        ("true", "git rebase --abort", set[str]()),
        ("true", "git cherry-pick --abort", set[str]()),
        ("true", "git revert --abort", set[str]()),
        ("true", "git am --abort", set[str]()),
        # Reads, with listed options (review DC-2026-10-08b, finding 5)
        ("true", "git status --short -b", set[str]()),
        ("true", "git log --oneline -5 --format=%h", set[str]()),
        ("true", "git diff --stat HEAD~1", set[str]()),
        ("true", "git show --stat HEAD", set[str]()),
        ("true", "git grep -n base", set[str]()),
        ("true", "git blame f", set[str]()),
        ("true", "git ls-files --others --exclude-standard", set[str]()),
        ("true", "git ls-tree -r HEAD", set[str]()),
        ("true", "git rev-parse --abbrev-ref HEAD", set[str]()),
        ("true", "git merge-base HEAD origin/main", set[str]()),
        ("true", "git rev-list --count HEAD", set[str]()),
        ("true", "git cat-file -t HEAD", set[str]()),
        ("echo x > g", "git hash-object g", set[str]()),
        ("true", "git describe --always", set[str]()),
        ("true", "git shortlog -sn HEAD", set[str]()),
        ("true", "git branch -a -vv", set[str]()),
        ("true", "git branch --show-current", set[str]()),
        ("true", "git remote -v", set[str]()),
        # The rest of the write forms
        ("true", "git fetch", {"local refs/remotes/origin/HEAD"}),
        ("true", "git fetch origin", {"local refs/remotes/origin/HEAD"}),
        ("echo x > f", "git add -u", set[str]()),
        (
            "echo x > f; git add f; echo msg > ../msg.txt",
            "git commit -q --file ../msg.txt",
            {"local refs/heads/s1"},
        ),
        ("true", "git push -u origin s1", {"local refs/remotes/origin/s1", "remote refs/heads/s1"}),
        ("true", "git pull --ff-only origin s1", set[str]()),
        ("git switch -q main", "git switch s1", set[str]()),
        ("echo x > g; git stash push -q -u", "git stash apply", set[str]()),
        ("echo x > g; git stash push -q -u", "git stash show", set[str]()),
        ("echo x > f", "git restore --worktree f", set[str]()),
        ("mkdir d; echo x > d/a; git add d", "git rm -q -r --cached d", set[str]()),
        ("git switch -q main", "git reset -q --hard origin/main", set[str]()),
        ("git switch -q main", "git pull --ff-only origin main", set[str]()),
        # The rest of the forms (review DC-2026-10-08b, pass 2, finding 7)
        ("true", "git reset -q --mixed HEAD~1", {"local refs/heads/s1"}),
        ("true", "git reset -q --hard HEAD~1", {"local refs/heads/s1"}),
        ("echo x > f; git add f", "git reset -q f", set[str]()),
        ("echo x > f; echo y > g; git add f g", "git reset -q f g", set[str]()),
        ("echo x > f", "git stash", set[str]()),
        ("echo x > f", "git stash push -m wip", set[str]()),
        ("echo x > g", "git add -N g", set[str]()),
        ("true", "git branch --list 's*'", set[str]()),
        ("true", "git remote", set[str]()),
        ("true", "git fetch -p", {"local refs/remotes/origin/HEAD"}),
        ("true", "git fetch -q origin", {"local refs/remotes/origin/HEAD"}),
        ("true", "git -C . status", set[str]()),
        ("true", "git --no-pager log -1", set[str]()),
        (
            "true",
            "git push --set-upstream origin s1",
            {"local refs/remotes/origin/s1", "remote refs/heads/s1"},
        ),
        (
            "git switch -q main; git branch -q --set-upstream-to=origin/main",
            "git pull --ff-only",
            {"local refs/remotes/origin/HEAD"},
        ),
        # An alias can't override a builtin, so a listed subcommand is always the builtin.
        ("git config alias.status 'push --force origin +s1:main'", "git status", set[str]()),
    ],
)
def test_an_allowed_form_changes_only_what_it_should_in_real_git(
    clone: Path, setup: str, command: str, expected: set[str]
) -> None:
    subprocess.run(["sh", "-c", setup], cwd=clone, check=True, capture_output=True)
    before = snapshot(clone)

    assert guard_git.decide(command, clone, guard_git.GitRepo()) == guard_git.ALLOW
    git(clone, *shlex.split(command)[1:])

    assert changed(before, snapshot(clone)) == expected


@pytest.mark.parametrize(
    ("setup", "command", "message"),
    [
        (
            "git switch -q main; git config branch.main.remote origin; "
            "git config branch.main.merge refs/heads/s1",
            "git pull --ff-only",
            "only from `main`",
        ),
        ("git switch -q main; git branch fix/main s1", "git reset --hard fix/main", "on `main`"),
    ],
)
def test_branch_rules_on_main_use_the_real_repository_state(
    clone: Path, setup: str, command: str, message: str
) -> None:
    subprocess.run(["sh", "-c", setup], cwd=clone, check=True, capture_output=True)

    result = guard_git.decide(command, clone, guard_git.GitRepo())

    assert result.block is not None
    assert message in result.block


def test_a_commit_message_from_a_heredoc_is_read_from_stdin(clone: Path) -> None:
    command = "git commit -q --allow-empty -F - <<'EOF'\nfrom stdin\nEOF"

    assert guard_git.decide(command, clone, guard_git.GitRepo()) == guard_git.ALLOW
    git(clone, "commit", "-q", "--allow-empty", "-F", "-", stdin="from stdin\n")

    assert must(clone, "log", "-1", "--format=%s") == "from stdin"


def test_a_diverged_fast_forward_pull_refuses_and_moves_no_branch(clone: Path) -> None:
    remote, other = clone.parent / "remote.git", clone.parent / "other"
    must(clone.parent, "clone", "--quiet", "--branch", "s1", str(remote), str(other))
    must(
        other,
        "-c",
        "user.name=T",
        "-c",
        "user.email=t@e",
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        "o",
    )
    must(other, "push", "--quiet", "origin", "s1")
    head = must(clone, "rev-parse", "HEAD")

    result = git(clone, "pull", "-q", "--ff-only")

    assert result.returncode != 0
    assert must(clone, "rev-parse", "HEAD") == head


def test_git_repo_reads_the_branch_and_push_destination(clone: Path, tmp_path: Path) -> None:
    repo = guard_git.GitRepo()

    assert repo.current_branch(clone) == "s1"
    assert repo.push_destination(clone) == "origin/s1"
    assert repo.current_branch(tmp_path) is None
    assert repo.push_destination(tmp_path) is None


def test_git_repo_reports_no_branch_when_detached(clone: Path) -> None:
    must(clone, "switch", "--quiet", "--detach")

    assert guard_git.GitRepo().current_branch(clone) is None


def test_git_repo_knows_whether_head_is_pushed(clone: Path) -> None:
    repo = guard_git.GitRepo()

    assert repo.head_on_remote(clone) is False
    must(clone, "reset", "--quiet", "--hard", "HEAD~1")
    assert repo.head_on_remote(clone) is True


@pytest.mark.parametrize(
    ("target", "drops"),
    [("HEAD", False), ("HEAD~1", False), ("HEAD~2", True), ("origin/s1", False), ("f", None)],
)
def test_git_repo_knows_whether_a_reset_drops_pushed_commits(
    clone: Path, target: str, drops: bool | None
) -> None:
    assert guard_git.GitRepo().drops_pushed_commits(clone, target) is drops


def test_hash_object_without_w_writes_no_object(clone: Path) -> None:
    (clone / "g").write_text("content only this test writes\n")

    assert guard_git.decide("git hash-object g", clone, guard_git.GitRepo()) == guard_git.ALLOW
    sha = must(clone, "hash-object", "g")

    assert git(clone, "cat-file", "-e", sha).returncode != 0


@pytest.mark.parametrize(
    "error", [subprocess.TimeoutExpired("git", 2), OSError("no git")], ids=["timeout", "oserror"]
)
def test_a_git_call_that_times_out_or_cannot_run_blocks_the_command(
    clone: Path, monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    # pass 4, finding 3: an escaping exception would exit 1, which Claude Code doesn't block on
    calls: list[dict[str, object]] = []

    def failing_run(*args: object, **kwargs: object) -> object:
        calls.append(kwargs)
        raise error

    monkeypatch.setattr(guard_git.subprocess, "run", failing_run)

    result = guard_git.decide("git push", clone, guard_git.GitRepo())

    assert result.block is not None
    assert "couldn't ask git about the repository" in result.block
    assert calls[0]["timeout"] == 2


def test_git_repo_lists_the_configured_remotes(clone: Path) -> None:
    must(clone, "remote", "add", "backup", "../elsewhere.git")

    assert guard_git.GitRepo().remotes(clone) == ["backup", "origin"]


def test_a_pull_on_main_from_a_path_to_another_repository_is_blocked_in_real_git(
    clone: Path,
) -> None:
    must(clone, "switch", "--quiet", "main")
    (clone / "copy").symlink_to(clone.parent / "remote.git")  # a literal-looking name, no remote

    result = guard_git.decide("git pull --ff-only copy main", clone, guard_git.GitRepo())

    assert result.block is not None
    assert "only from `main`" in result.block


@pytest.mark.parametrize(
    ("name", "full"),
    [
        ("HEAD", "refs/heads/s1"),
        ("main", "refs/heads/main"),
        ("origin/main", "refs/remotes/origin/main"),
        ("fix/main", "refs/heads/fix/main"),
        ("v1", "refs/tags/v1"),
        ("HEAD~1", ""),  # a commit expression names no ref
        ("nothing", None),
    ],
)
def test_git_repo_resolves_what_a_name_refers_to(clone: Path, name: str, full: str | None) -> None:
    must(clone, "branch", "fix/main")
    must(clone, "tag", "v1")

    assert guard_git.GitRepo().full_ref(clone, name) == full


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
    must(clone, "switch", "--quiet", "main")
    assert guard_git.decide("git commit -m x", clone, repo).block is not None


# --- The tokenizer ------------------------------------------------------------------------------

X = "\x00"  # guard_git.UNKNOWN: a value only known at run time


def script(
    *segments: list[str],
    substitutions: tuple[str, ...] = (),
    operators: tuple[str, ...] = (),
    heredocs: tuple[str, ...] = (),
    targets: tuple[str, ...] = (),
    quoted: tuple[bool, ...] = (),
) -> guard_git.Script:
    parts = [guard_git.Segment(words=words) for words in segments]
    parts[0].heredocs.extend(heredocs)
    return guard_git.Script(
        parts, list(substitutions), list(operators), list(targets), list(quoted)
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "a && b | c; (d)",
            script(["a"], ["b"], ["c"], ["d"], operators=("&&", "|", ";", "(", ")")),
        ),
        ("echo a # a comment", script(["echo", "a"])),
        ("echo a\\ b \\\nc", script(["echo", "a b", "c"])),
        ('echo "a \\"q\\" $x"', script(["echo", f'a "q" {X}'])),
        ("echo ${HOME}/x", script(["echo", f"{X}/x"])),
        ("echo $'a\\'b'", script(["echo", X])),
        ('echo $"x"', script(["echo", f"{X}x"])),  # read like "x", so its $(...) is recorded
        ('echo $"$(cmd)"', script(["echo", f"{X}{X}"], substitutions=("cmd",))),
        ("echo ${x:-$(cmd)}", script(["echo", X], substitutions=("cmd",))),
        ("echo ${x:-`cmd`}", script(["echo", X], substitutions=("cmd",))),
        ("echo ${x:-'a}b'}", script(["echo", X])),  # a quoted brace doesn't close it
        ("echo ${x:-\\}}", script(["echo", X])),
        ("echo ${a:-${b}}/z", script(["echo", f"{X}/z"])),
        ("echo {'a b',c}", script(["echo", X])),
        ("echo {a\\,b}", script(["echo", "{a,b}"])),  # an escaped comma isn't an expansion
        ("echo {a b}", script(["echo", "{a", "b}"])),
        ("echo {a,b", script(["echo", "{a,b"])),
        ("echo $((1 + 2))", script(["echo", X], substitutions=("(1 + 2)",))),
        ('echo $(echo "a\\")b")', script(["echo", X], substitutions=('echo "a\\")b"',))),
        (
            "echo $(printf '%s' \")\" \\))",
            script(["echo", X], substitutions=("printf '%s' \")\" \\)",)),
        ),
        (
            "echo \"$(cat <<'EOF'\nit's\nEOF\n)\"",
            script(["echo", X], substitutions=("cat <<'EOF'\nit's\nEOF\n",)),
        ),
        (
            'echo "$(cat <<-EOF\n\tx\n\tEOF\n)"',
            script(["echo", X], substitutions=("cat <<-EOF\n\tx\n\tEOF\n",)),
        ),
        ("cat <<-EOF\n\tbody\n\tEOF", script(["cat"], heredocs=("\tbody",), quoted=(False,))),
        ("cat <<'E'\nx\nE", script(["cat"], heredocs=("x",), quoted=(True,))),
        ('cat <<E""\nx\nE', script(["cat"], heredocs=("x",), quoted=(True,))),
        ("git log > out.txt 2>&1 < in", script(["git", "log"], targets=("out.txt", "1", "in"))),
    ],
)
def test_the_tokenizer_splits_words_the_way_bash_does(
    text: str, expected: guard_git.Script
) -> None:
    assert guard_git.tokenize(text) == expected


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("echo `x", "an unclosed backtick"),
        ("echo $'abc", "an unclosed $'"),
        ("echo ${HOME", "an unclosed ${"),
        ("echo {'a", "an unclosed '"),
        ("echo $(cat <<EOF\nx)", "a heredoc without its closing 'EOF' line"),
        ("cat <<EOF\nno end", "a heredoc without its closing 'EOF' line"),
        ("cat <<EOF", "a heredoc without its closing 'EOF' line"),
    ],
)
def test_the_tokenizer_refuses_what_it_cannot_parse(text: str, reason: str) -> None:
    with pytest.raises(guard_git.Unparseable, match=re.escape(reason)):
        guard_git.tokenize(text)
