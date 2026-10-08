"""PreToolUse hook (Bash): the git guard, an allow-list (DL-26).

A call that involves git or gh must be one command in an allowed form, so that Claude never
commits or merges on `main` (DL-21), pushes to `main` (DL-22), rewrites pushed history (DL-23),
or skips hooks (DL-24); merging a pull request or writing through the GitHub API asks the owner
(DL-25). Anything else that mentions git or gh is blocked: the owner runs it (`! <command>`).
Every allowed git form's effect is verified against real git by the tests (the gh forms are
tested against this guard only).

A guard against mistakes, not a security boundary: GitHub's rulesets (DL-27) are the real
control. Reads the hook input (JSON) on stdin. Exit code 2 blocks the command and shows stderr
to Claude; a PreToolUse `permissionDecision` of "ask" on stdout makes Claude Code ask the user;
exit code 0 with no output lets the normal permission flow continue.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from itertools import pairwise
from pathlib import Path
from typing import Any, Protocol

MAIN = "main"
# Stands in for anything expanded at run time ($VAR, $(...), `...`, braces): its value is unknown.
UNKNOWN = "\x00"
# An unquoted `*`, `?`, or `[` in a redirect target: bash expands it to an existing file
# (verified, bash 5.3), so `>> .gi?/config` writes `.git/config` without naming it.
GLOB = "\x01"


class Unparseable(Exception):  # noqa: N818 -- reads as a verdict: "Unparseable(reason)"
    """The command can't be analyzed with confidence."""


@dataclass(frozen=True)
class Verdict:
    """`block` and `ask` carry the message shown; neither set means allow."""

    block: str | None = None
    ask: str | None = None


ALLOW = Verdict()


def blocked(message: str) -> Verdict:
    return Verdict(block=f"Blocked by the git guard: {message}")


# --- Repository state -------------------------------------------------------------------------


class Repo(Protocol):
    def current_branch(self, cwd: Path) -> str | None: ...
    def push_destination(self, cwd: Path) -> str | None: ...
    def head_on_remote(self, cwd: Path) -> bool: ...
    def drops_pushed_commits(self, cwd: Path, target: str) -> bool | None: ...
    def full_ref(self, cwd: Path, name: str) -> str | None: ...
    def remotes(self, cwd: Path) -> list[str]: ...


class GitRepo:
    """Asks git about the repository at `cwd`. Read-only commands only."""

    def _git(self, cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
        # Fixed executable and arguments, no shell.
        try:
            return subprocess.run(  # noqa: S603
                ["git", "-C", str(cwd), *args],  # noqa: S607
                capture_output=True,
                text=True,
                check=False,
                timeout=2,  # 5 calls at most per command: under the hook's 15 s
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise Unparseable(f"couldn't ask git about the repository: {exc}") from exc

    def _out(self, cwd: Path, *args: str) -> str | None:
        result = self._git(cwd, *args)
        return result.stdout.strip() if result.returncode == 0 else None

    def current_branch(self, cwd: Path) -> str | None:
        return self._out(cwd, "symbolic-ref", "--quiet", "--short", "HEAD")

    def push_destination(self, cwd: Path) -> str | None:
        """Where a bare `git push` sends the current branch, e.g. `origin/s1`."""
        return self._out(cwd, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{push}")

    def head_on_remote(self, cwd: Path) -> bool:
        """Whether HEAD is reachable from any remote-tracking branch."""
        return self._out(cwd, "rev-list", "--count", "HEAD", "--not", "--remotes") == "0"

    def drops_pushed_commits(self, cwd: Path, target: str) -> bool | None:
        """Whether moving HEAD to `target` drops a commit that is on a remote; None when
        `target` isn't a commit (so `git reset <target>` resets paths, not HEAD)."""
        if self._out(cwd, "rev-parse", "--verify", "--quiet", f"{target}^{{commit}}") is None:
            return None
        dropped = self._out(cwd, "rev-list", "--count", f"{target}..HEAD")
        unpushed = self._out(cwd, "rev-list", "--count", f"{target}..HEAD", "--not", "--remotes")
        return dropped != unpushed

    def remotes(self, cwd: Path) -> list[str]:
        """The configured remotes' names (verified: `git remote` prints one per line)."""
        names = self._out(cwd, "remote")
        return names.splitlines() if names else []

    def full_ref(self, cwd: Path, name: str) -> str | None:
        """The ref `name` names (`main` → `refs/heads/main`, `origin/main` →
        `refs/remotes/origin/main`); empty for a commit expression such as `HEAD~1`; None when
        it names nothing. Verified with real git: a branch called `fix/main` is
        `refs/heads/fix/main`, a tag `refs/tags/…`."""
        return self._out(cwd, "rev-parse", "--symbolic-full-name", name)


# --- Tokenizing -------------------------------------------------------------------------------

# Longest first, so `&&` wins over `&` and `<<-` over `<<`.
OPERATORS = sorted(
    [
        "&&", "||", ";;", ";&", "|&", "&>>", "&>", ">>", "<<<", "<<-", "<<", ">&", "<&", ">|",
        "<>", ">", "<", ";", "&", "|", "(", ")",
    ],
    key=len,
    reverse=True,
)  # fmt: skip
HEREDOC = {"<<", "<<-"}
HEREDOC_START = re.compile(r"<<-?[ \t]*(['\"]?)([A-Za-z_0-9]+)\1")
VARIABLE_START = re.compile(r"[A-Za-z_0-9{@*#?$!-]")


@dataclass
class Segment:
    """One simple command: its words, and the bodies of any heredocs it reads."""

    words: list[str] = field(default_factory=list[str])
    heredocs: list[str] = field(default_factory=list[str])


@dataclass
class Script:
    segments: list[Segment]
    substitutions: list[str]  # the commands inside $(...), `...`, <(...), >(...)
    operators: list[str]
    redirect_targets: list[str] = field(default_factory=list[str])  # files read or written
    # One per heredoc: whether its delimiter was quoted (`<<'EOF'`), so bash leaves the body as
    # text; an unquoted body runs its `$(...)` and backticks.
    heredocs_quoted: list[bool] = field(default_factory=list[bool])


class _Scanner:
    def __init__(self, text: str) -> None:
        self.text = text
        self.i = 0
        self.substitutions: list[str] = []

    def peek(self, n: int = 1) -> str:
        return self.text[self.i : self.i + n]

    def read_until_close(self) -> str:
        """After an opening `(`: the text up to its matching `)`, respecting quotes and
        heredocs (whose bodies may hold unbalanced quotes, as in a commit message)."""
        start, depth = self.i, 1
        while self.i < len(self.text):
            char = self.text[self.i]
            if char == "\\":
                self.i += 2
                continue
            if char in "'\"":
                self.skip_quoted(char)
                continue
            heredoc = HEREDOC_START.match(self.text, self.i)
            if heredoc:
                self.skip_heredoc(heredoc.group(2), strip_tabs=heredoc.group(0)[2] == "-")
                continue
            self.i += 1
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    return self.text[start : self.i - 1]
        raise Unparseable("an unclosed `(`")

    def skip_heredoc(self, delimiter: str, *, strip_tabs: bool) -> None:
        """From a heredoc operator: past the rest of its line and the body's closing line."""
        lines = self.text[self.i :].split("\n")
        for number, line in enumerate(lines[1:], start=1):
            if (line.lstrip("\t") if strip_tabs else line) == delimiter:
                self.i += sum(len(skipped) + 1 for skipped in lines[:number]) + len(line)
                return
        raise Unparseable(f"a heredoc without its closing {delimiter!r} line")

    def skip_quoted(self, quote: str) -> None:
        end = self.text.find(quote, self.i + 1)
        while quote == '"' and end != -1 and self.text[end - 1] == "\\":
            end = self.text.find(quote, end + 1)
        if end == -1:
            raise Unparseable(f"an unclosed {quote}")
        self.i = end + 1

    def read_backticks(self) -> str:
        end = self.text.find("`", self.i + 1)
        if end == -1:
            raise Unparseable("an unclosed backtick")
        inner = self.text[self.i + 1 : end]
        self.i = end + 1
        return inner

    def brace_expansion_end(self) -> int | None:
        """At an unquoted `{`: where its brace expansion (`{a,b}`, `{1..3}`, quotes allowed
        inside) ends; None when it isn't one (`{ cmd; }`, `{x}`, unclosed). A nested pair
        needs no tracking: any comma makes the word unknown, wherever it is."""
        index, expands = self.i + 1, False
        while index < len(self.text):
            char = self.text[index]
            if char == "\\":
                index += 2
                continue
            if char in "'\"":
                end = self.text.find(char, index + 1)
                if end == -1:
                    return None
                index = end + 1
                continue
            if char in " \t\n;&|<>()":
                return None
            if char == "}":
                return index + 1 if expands else None
            if char == "," or self.text.startswith("..", index):
                expands = True
            index += 1
        return None

    def read_parameter(self) -> None:
        """At the `{` of `${…}`: past its matching `}`, recording the `$(...)` and backticks
        inside (bash runs them: `${x:-$(cmd)}`, verified), and stepping over quotes."""
        self.i += 1
        depth = 1
        while self.i < len(self.text):
            char = self.text[self.i]
            if char == "\\":
                self.i += 2
            elif char == "'":
                self.skip_quoted("'")
            elif self.peek(2) == "$(":
                self.i += 2
                self.substitutions.append(self.read_until_close())
            elif char == "`":
                self.substitutions.append(self.read_backticks())
            else:
                self.i += 1
                depth += {"{": 1, "}": -1}.get(char, 0)
                if depth == 0:
                    return
        raise Unparseable("an unclosed ${")

    def expansion(self, *, quoted: bool = False) -> bool:
        """At `$`, `` ` ``, or (unquoted) `<(`, `>(`, `$'`, `$"` or a brace expansion: records
        a command substitution or skips what's only known at run time, returning True; False
        when it's a plain character."""
        if not quoted and self.peek(2) == "$'":
            end = self.i + 2
            while end < len(self.text) and self.text[end] != "'":
                end += 2 if self.text[end] == "\\" else 1
            if end >= len(self.text):
                raise Unparseable("an unclosed $'")
            self.i = end + 1
            return True
        if not quoted and self.peek(2) == '$"':
            # A translated string is a double-quoted one (bash runs its `$(...)`), so only the
            # `$` is consumed: the string is then read like any double-quoted text.
            self.i += 1
            return True
        brace_end = None if quoted or self.peek() != "{" else self.brace_expansion_end()
        if brace_end is not None:
            self.i = brace_end
            return True
        if self.peek(2) == "$(" or (not quoted and self.peek(2) in ("<(", ">(")):
            self.i += 2
            self.substitutions.append(self.read_until_close())
            return True
        if self.peek() == "`":
            self.substitutions.append(self.read_backticks())
            return True
        if self.peek() == "$" and VARIABLE_START.match(self.peek(2)[1:] or " "):
            self.i += 1
            if self.peek() == "{":
                self.read_parameter()
            else:
                match = re.match(r"[A-Za-z_][A-Za-z_0-9]*|.", self.text[self.i :])
                self.i += len(match.group(0)) if match else 0
            return True
        return False


def tokenize(text: str) -> Script:
    """Split shell text into simple commands, the way bash would for the words that matter
    here. Expansions become `UNKNOWN`; the commands inside substitutions are returned to be
    checked on their own."""
    scanner = _Scanner(text)
    segments: list[Segment] = [Segment()]
    word: list[str] = []
    in_word = False
    pending_heredocs: list[tuple[str, bool, Segment]] = []  # delimiter, strip tabs, reader
    drop_next_word = False
    heredoc_next_word: bool | None = None  # strip-tabs flag while awaiting a delimiter
    operators: list[str] = []  # control operators (`&&`, `;`, `|`, `(`, …), not redirections
    redirect_targets: list[str] = []
    heredocs_quoted: list[bool] = []
    quoted = False  # whether the current word has any quoting (so a heredoc delimiter is quoted)

    def end_word() -> None:
        nonlocal word, in_word, drop_next_word, heredoc_next_word, quoted
        if in_word:
            value = "".join(word)
            if heredoc_next_word is not None:
                pending_heredocs.append(
                    (value.replace(UNKNOWN, ""), heredoc_next_word, segments[-1])
                )
                heredocs_quoted.append(quoted)
                heredoc_next_word = None
            elif drop_next_word:
                redirect_targets.append(value)
                drop_next_word = False
            else:
                segments[-1].words.append(value)
        word, in_word, quoted = [], False, False

    def new_segment() -> None:
        if segments[-1].words or segments[-1].heredocs:
            segments.append(Segment())

    def read_heredoc_bodies() -> None:
        for delimiter, strip_tabs, reader in pending_heredocs:
            lines: list[str] = []
            while True:
                end = text.find("\n", scanner.i)
                line = text[scanner.i : len(text) if end == -1 else end]
                scanner.i = len(text) if end == -1 else end + 1
                if (line.lstrip("\t") if strip_tabs else line) == delimiter:
                    break
                if end == -1:
                    raise Unparseable(f"a heredoc without its closing {delimiter!r} line")
                lines.append(line)
            reader.heredocs.append("\n".join(lines))
        pending_heredocs.clear()

    while scanner.i < len(text):
        char = text[scanner.i]
        if char == "\\":
            if scanner.peek(2) == "\\\n":
                scanner.i += 2
                continue
            word.append(text[scanner.i + 1 : scanner.i + 2])
            in_word = quoted = True
            scanner.i += 2
        elif char == "'":
            start = scanner.i
            scanner.skip_quoted("'")
            word.append(text[start + 1 : scanner.i - 1])
            in_word = quoted = True
        elif char == '"':
            in_word = quoted = True
            scanner.i += 1
            while True:
                if scanner.i >= len(text):
                    raise Unparseable('an unclosed "')
                inner = text[scanner.i]
                if inner == '"':
                    scanner.i += 1
                    break
                if inner == "\\" and scanner.peek(2)[1:] in ('"', "\\", "$", "`", "\n"):
                    word.append(scanner.peek(2)[1:])
                    scanner.i += 2
                elif scanner.expansion(quoted=True):
                    word.append(UNKNOWN)
                else:
                    word.append(inner)
                    scanner.i += 1
        elif char in " \t":
            end_word()
            scanner.i += 1
        elif char == "\n":
            end_word()
            scanner.i += 1
            read_heredoc_bodies()
            new_segment()
        elif char == "#" and not in_word:
            end = text.find("\n", scanner.i)
            scanner.i = len(text) if end == -1 else end
        elif scanner.expansion():
            word.append(UNKNOWN)
            in_word = True
        elif char in ";&|()<>":
            operator = next(op for op in OPERATORS if text.startswith(op, scanner.i))
            if "<" in operator or ">" in operator:
                if in_word and "".join(word).isdigit():
                    word, in_word = [], False  # a file descriptor, as in 2>&1
                end_word()
                if operator in HEREDOC:
                    heredoc_next_word = operator == "<<-"
                else:
                    drop_next_word = True  # the redirection's target
            else:
                end_word()
                new_segment()
                operators.append(operator)
            scanner.i += len(operator)
        else:
            word.append(GLOB if drop_next_word and char in "*?[" else char)
            in_word = True
            scanner.i += 1
    end_word()
    if pending_heredocs:
        read_heredoc_bodies()
    return Script(
        [s for s in segments if s.words],
        scanner.substitutions,
        operators,
        redirect_targets,
        heredocs_quoted,
    )


# --- What a call may do -----------------------------------------------------------------------

# Commands that only read and print, with no option that runs a program or writes a file, so
# `grep -rn "git push" docs` or `cat .git/config` changes nothing. (Not `sort -o`, `uniq <out>`,
# `rg --pre`, `file -C`, pagers, or `test`/`[`/`[[`/`printf -v`, which evaluate an array
# subscript, and so a `$(...)` in it, even in a single-quoted operand: verified.) Where their
# output goes is checked separately.
DATA_COMMANDS = {
    "echo", "which", "type", "whereis", "grep", "egrep", "fgrep", "ls", "cat", "head", "tail",
    "wc", "true", "false", "cut", "tr", "diff", "jq", "basename", "dirname", "realpath",
    "readlink", "stat",
}  # fmt: skip
ONE_COMMAND = (
    "a call that involves git or gh must be that one command and nothing else: no `&&`, `;`, "
    "`|`, `cd`, variables, `$(...)`, `bash -c`, or environment prefixes. Use `git -C <path>` "
    "for another directory, and `git commit -F - <<'EOF'` for a message. Anything the "
    "allow-list doesn't cover, ask the owner to run (`! <command>`)."
)


def mentions_git(text: str) -> bool:
    """git, gh, or a git config file (`.gitconfig`, `~/.config/git/config`)."""
    return re.search(r"\b(git|gh)\b|gitconfig", text) is not None


def basename(word: str) -> str:
    return word.rsplit("/", 1)[-1]


def script_mentions_git(script: Script) -> bool:
    """Git or gh in any word, redirect target, or heredoc body, after quoting is removed (so
    `.g''it/config` counts as `.git/config`), or in any substitution, read the same way."""
    texts = [
        *(word for segment in script.segments for word in segment.words),
        *(body for segment in script.segments for body in segment.heredocs),
        *script.redirect_targets,
    ]
    return any(mentions_git(text) for text in texts) or any(
        substitution_mentions_git(inner) for inner in script.substitutions
    )


def substitution_mentions_git(inner: str) -> bool:
    try:
        return script_mentions_git(tokenize(inner))
    except Unparseable:
        return mentions_git(inner)


def is_git_config_or_hooks(target: str) -> bool:
    """A path inside a `.git` directory (its config or hooks), or a git config file outside it:
    `~/.gitconfig`, or one under a `.config/git` directory."""
    parts = Path(target).parts
    under_config_git = any(a == ".config" and b == "git" for a, b in pairwise(parts))
    return ".git" in parts or ".gitconfig" in parts or under_config_git


def writes_into_git_dir(script: Script) -> bool:
    """A redirect to a git config or hooks file, or to a file whose name is only known at run
    time."""
    return any(
        UNKNOWN in target or is_git_config_or_hooks(target) for target in script.redirect_targets
    )


def decide(command: str, cwd: Path | None, repo: Repo) -> Verdict:
    """The verdict for one Bash call (DL-26): one git or gh command in an allowed form, or a
    call where git and gh appear only as data; anything else that mentions them is blocked."""
    try:
        script = tokenize(command)
    except Unparseable as exc:
        if not mentions_git(command):
            return ALLOW  # not about git; bash will report its own syntax error
        return blocked(f"it can't parse this command ({exc}). {ONE_COMMAND}")
    if any(GLOB in target for target in script.redirect_targets):
        return blocked(
            "a glob (`*`, `?`, `[`) in a redirect target can name `.git/` without saying so "
            "(DL-24). Name the file."
        )
    if not mentions_git(command) and not script_mentions_git(script):
        return ALLOW
    if writes_into_git_dir(script):
        return blocked(
            "a redirect into `.git/` (its config or hooks) or a git config file, or to a file "
            "named only at run time, can turn the repository's hooks off (DL-24). Write "
            "somewhere else."
        )
    words = script.segments[0].words if len(script.segments) == 1 else []
    if words and basename(words[0]) in ("git", "gh"):
        # A substitution always leaves an unknown word or redirect target (both blocked), so
        # operators and unknown words are all that's left to check.
        if script.operators or any(UNKNOWN in word for word in words):
            return blocked(ONE_COMMAND)
        if not all(script.heredocs_quoted):
            return blocked(
                "an unquoted heredoc runs the `$(...)` and backticks in its body. Quote the "
                "delimiter: `git commit -F - <<'EOF'`."
            )
        try:
            if basename(words[0]) == "gh":
                return check_gh(words[1:], script.segments[0].heredocs)
            return check_git(words[1:], script.segments[0].heredocs, cwd, repo)
        except Unparseable as exc:
            return blocked(f"{exc}. {ONE_COMMAND}")
    # Git appears only as data: every command only reads and prints, and nothing is expanded
    # (an expansion can hide a command: `${x:-$(cmd)}`).
    only_data = all(segment.words[0] in DATA_COMMANDS for segment in script.segments)
    has_heredoc = any(segment.heredocs for segment in script.segments)
    expands = any(UNKNOWN in word for segment in script.segments for word in segment.words) or bool(
        script.substitutions
    )
    if only_data and not expands and not has_heredoc:
        return ALLOW
    return blocked(ONE_COMMAND)


# --- git --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ReadFlags:
    """A read command's allowed options: exact flags; long options that take a value
    (`--format=…` or `--format …`); short options that take one attached (`-n5`, `-U3`); and
    whether a bare count (`-5`) is allowed. Positionals (revisions, paths) are free. Anything
    else is blocked: some options of read commands run a program (`grep -O<cmd>`) or write a
    file (`log --output=<file>`)."""

    flags: frozenset[str]
    valued: frozenset[str] = frozenset()
    short_valued: frozenset[str] = frozenset()
    count: bool = False


FORMAT = frozenset({
    "--oneline", "--stat", "--shortstat", "--numstat", "--name-only", "--name-status", "--graph",
    "--decorate", "--no-decorate", "--abbrev-commit", "--patch", "-p", "--no-patch", "-s",
    "--color", "--no-color", "--relative-date", "-z", "--raw", "--summary", "--reverse",
})  # fmt: skip
FORMAT_VALUED = frozenset({"--format", "--pretty", "--color", "--date", "--abbrev", "--decorate"})
HISTORY = frozenset({
    "--all", "--branches", "--remotes", "--tags", "--first-parent", "--merges", "--no-merges",
    "--follow", "--left-right", "--topo-order", "--date-order", "--ancestry-path", "-i",
    "--regexp-ignore-case", "-E", "-F",
})  # fmt: skip
HISTORY_VALUED = frozenset({
    "--max-count", "--since", "--after", "--until", "--before", "--author", "--committer",
    "--grep", "--skip", "--branches", "--remotes", "--tags",
})  # fmt: skip
READ_ONLY = {
    "status": ReadFlags(
        frozenset(
            {
                "--short",
                "-s",
                "--branch",
                "-b",
                "--porcelain",
                "--long",
                "-z",
                "--ignored",
                "--untracked-files",
                "-u",
                "-uno",
                "-unormal",
                "-uall",
            }
        ),
        frozenset({"--porcelain", "--untracked-files", "--ignored"}),
    ),
    "log": ReadFlags(FORMAT | HISTORY, FORMAT_VALUED | HISTORY_VALUED, frozenset({"-n"}), True),
    "show": ReadFlags(FORMAT | {"--quiet", "-q"}, FORMAT_VALUED),
    "diff": ReadFlags(
        FORMAT
        | {
            "--cached",
            "--staged",
            "--exit-code",
            "--quiet",
            "-w",
            "--ignore-all-space",
            "-b",
            "--ignore-space-change",
            "--check",
            "-M",
            "--find-renames",
            "--no-renames",
            "-R",
            "--word-diff",
            "--relative",
            "--minimal",
            "--histogram",
        },
        FORMAT_VALUED | {"--unified", "--word-diff", "--diff-filter", "--relative", "--stat"},
        frozenset({"-U"}),
    ),
    "rev-parse": ReadFlags(
        frozenset(
            {
                "--abbrev-ref",
                "--symbolic-full-name",
                "--symbolic",
                "--verify",
                "--quiet",
                "-q",
                "--short",
                "--show-toplevel",
                "--git-dir",
                "--git-common-dir",
                "--absolute-git-dir",
                "--is-inside-work-tree",
                "--is-inside-git-dir",
                "--is-bare-repository",
                "--is-shallow-repository",
                "--show-prefix",
                "--show-cdup",
                "--all",
                "--branches",
                "--tags",
                "--remotes",
            }
        ),
        frozenset({"--short", "--abbrev-ref"}),
    ),
    "ls-files": ReadFlags(
        frozenset(
            {
                "--others",
                "-o",
                "--cached",
                "-c",
                "--deleted",
                "-d",
                "--modified",
                "-m",
                "--exclude-standard",
                "--ignored",
                "-i",
                "-z",
                "--stage",
                "-s",
                "--error-unmatch",
                "--full-name",
                "--directory",
                "--unmerged",
                "-u",
            }
        )
    ),
    "ls-tree": ReadFlags(
        frozenset(
            {
                "-r",
                "-t",
                "-d",
                "--name-only",
                "--name-status",
                "-z",
                "-l",
                "--long",
                "--full-name",
                "--full-tree",
                "--abbrev",
            }
        )
    ),
    "blame": ReadFlags(
        frozenset(
            {
                "-w",
                "-M",
                "-C",
                "-s",
                "-e",
                "--line-porcelain",
                "--porcelain",
                "-l",
                "-t",
                "--show-email",
                "-c",
                "-L",
            }
        ),
        frozenset({"--date"}),
        frozenset({"-L"}),
    ),
    "grep": ReadFlags(
        frozenset(
            {
                "-n",
                "--line-number",
                "-i",
                "--ignore-case",
                "-w",
                "--word-regexp",
                "-l",
                "--files-with-matches",
                "-L",
                "--files-without-match",
                "-c",
                "--count",
                "-e",
                "-E",
                "--extended-regexp",
                "-F",
                "--fixed-strings",
                "-P",
                "--perl-regexp",
                "-v",
                "--invert-match",
                "-h",
                "-H",
                "--cached",
                "-I",
                "--untracked",
                "-q",
                "--quiet",
                "--heading",
                "--break",
                "-o",
                "--only-matching",
                "--full-name",
                "--all-match",
                "--and",
                "--or",
                "--not",
                "-r",
                "--recursive",
                "-A",
                "-B",
                "-C",
            }
        ),
        frozenset({"--max-depth", "--context", "--after-context", "--before-context"}),
        frozenset({"-A", "-B", "-C"}),
    ),
    "merge-base": ReadFlags(
        frozenset({"--is-ancestor", "--all", "--fork-point", "--octopus", "--independent"})
    ),
    "rev-list": ReadFlags(
        frozenset(
            {
                "--count",
                "--all",
                "--reverse",
                "--first-parent",
                "--merges",
                "--no-merges",
                "--left-right",
                "--not",
                "--remotes",
                "--branches",
                "--tags",
                "--oneline",
            }
        ),
        frozenset({"--max-count", "--since", "--until", "--remotes", "--branches", "--tags"}),
        frozenset({"-n"}),
        True,
    ),
    "cat-file": ReadFlags(frozenset({"-t", "-s", "-p", "-e"})),
    # Without -w it only prints the hash (verified: no object written).
    "hash-object": ReadFlags(frozenset()),
    "describe": ReadFlags(
        frozenset(
            {
                "--tags",
                "--always",
                "--long",
                "--exact-match",
                "--all",
                "--contains",
                "--first-parent",
                "--dirty",
            }
        ),
        frozenset({"--abbrev", "--match", "--exclude", "--dirty"}),
    ),
    "shortlog": ReadFlags(
        frozenset(
            {
                "-s",
                "-n",
                "-e",
                "-sn",
                "-ns",
                "-sne",
                "--summary",
                "--numbered",
                "--email",
                "--all",
                "--no-merges",
                "--merges",
            }
        ),
        frozenset({"--since", "--until", "--format", "--group"}),
    ),
}


def read_flag_allowed(word: str, allowed: ReadFlags) -> bool:
    name, has_value, _ = word.partition("=")
    if has_value:
        return name in allowed.valued
    if word in allowed.flags or word in allowed.valued:
        return True
    if allowed.count and re.fullmatch(r"-\d+", word):
        return True
    return any(
        word.startswith(prefix) and len(word) > len(prefix) for prefix in allowed.short_valued
    )


def check_read(command: str, rest: list[str]) -> Verdict:
    """A read command with only its listed options; positionals and anything after `--` are
    free (revisions and paths)."""
    allowed = READ_ONLY[command]
    options = rest[: rest.index("--")] if "--" in rest else rest
    bad = [
        word for word in options if word.startswith("-") and not read_flag_allowed(word, allowed)
    ]
    if not bad:
        return ALLOW
    return not_allowed(
        command,
        f"its listed read options (developer guide, section 11); not `{bad[0]}`, which isn't one",
    )


PATHS_ONLY = {
    "add": {"-A", "--all", "-u", "--update", "-N", "--intent-to-add"},
    "rm": {"-r", "--cached", "-q", "--quiet"},
    "mv": set[str](),
    "restore": {"--staged", "-S", "--worktree", "-W"},
}
BRANCH_READ_FLAGS = {"-a", "--all", "-r", "--remotes", "-v", "-vv", "--verbose", "--list", "-l"}
FIX_FORWARD = (
    "Make a follow-up commit instead (`fix(<ID>): <what>`); pushed history is never rewritten."
)
TO_THE_OWNER = "`main` changes only when the owner merges the slice's pull request."
# A branch or remote name written out literally: no refspec syntax (`:`, `+`, `*`, `^`, `~`).
LITERAL_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]*")


def not_allowed(command: str, forms: str) -> Verdict:
    return blocked(
        f"this `git {command}` isn't in the git guard's allow-list. Allowed: {forms}. Anything "
        "else, ask the owner to run (`! <command>`)."
    )


class GitCall:
    """The repository a git command runs in: the hook's working directory, or `git -C <path>`."""

    def __init__(self, cwd: Path | None, repo: Repo) -> None:
        self.cwd = cwd
        self.repo = repo

    def where(self) -> Path:
        if self.cwd is None:
            raise Unparseable("it can't tell which repository the command runs in")
        return self.cwd

    def branch(self) -> str:
        """The checked-out branch; there must be one, so a branch rule can be checked."""
        branch = self.repo.current_branch(self.where())
        if branch is None:
            raise Unparseable(
                f"no branch is checked out at {self.where()}, so its branch rules can't be checked"
            )
        return branch


def check_git(args: list[str], heredocs: list[str], cwd: Path | None, repo: Repo) -> Verdict:
    """`git [-C <path>] [--no-pager] <subcommand> <arguments>`, in an allowed form."""
    index = 0
    while index < len(args) and args[index] in ("-C", "--no-pager"):
        if args[index] == "-C":
            if index + 1 >= len(args):
                return not_allowed("-C", "`git -C <path> <subcommand> …`")
            cwd = resolve_path(cwd, args[index + 1])
            index += 2
        else:
            index += 1
    if index >= len(args):
        return ALLOW  # plain `git` prints its usage
    command, rest = args[index], args[index + 1 :]
    if heredocs and not (command == "commit" and rest_reads_stdin(rest)):
        return blocked(f"a heredoc is allowed only for `git commit -F -`. {ONE_COMMAND}")
    call = GitCall(cwd, repo)
    match command:
        case _ if command in READ_ONLY:
            return check_read(command, rest)
        case "add" | "rm" | "mv" | "restore":
            return check_paths(command, rest)
        case "branch":
            return check_branch(rest)
        case "remote":
            return (
                ALLOW
                if rest in ([], ["-v"], ["--verbose"])
                else not_allowed("remote", "`git remote [-v]`")
            )
        case "config":
            return check_config(rest)
        case "fetch":
            return check_fetch(rest)
        case "stash":
            return check_stash(rest)
        case "commit":
            return check_commit(rest, call)
        case "push":
            return check_push(rest, call)
        case "switch":
            return check_switch(rest)
        case "checkout":
            return check_checkout(rest)
        case "reset":
            return check_reset(rest, call)
        case "pull":
            return check_pull(rest, call)
        case "merge" | "rebase" | "cherry-pick" | "revert" | "am":
            if rest == ["--abort"]:
                return ALLOW
            return not_allowed(command, f"`git {command} --abort` ({TO_THE_OWNER})")
        case _:
            return not_allowed(command, "see the developer guide, section 11")


def resolve_path(cwd: Path | None, path: str) -> Path | None:
    """A `-C` path: absolute or `~`, or relative to the working directory when it's known."""
    expanded = Path(path).expanduser()
    if expanded.is_absolute():
        return expanded.resolve()
    return (cwd / expanded).resolve() if cwd is not None else None


def rest_reads_stdin(rest: list[str]) -> bool:
    return any(word in ("-F", "--file") and value == "-" for word, value in pairwise(rest))


def check_paths(command: str, rest: list[str]) -> Verdict:
    """Paths, after the command's few allowed flags (and `--`)."""
    flags = [word for word in rest if word.startswith("-") and word != "--"]
    if "--" in rest:
        flags = [word for word in rest[: rest.index("--")] if word.startswith("-")]
    if all(flag in PATHS_ONLY[command] for flag in flags):
        return ALLOW
    allowed = ", ".join(f"`{flag}`" for flag in sorted(PATHS_ONLY[command])) or "no flags"
    return not_allowed(command, f"paths, with {allowed}")


def check_branch(rest: list[str]) -> Verdict:
    """Listing branches: `--show-current`, or read flags (with a pattern after `--list`)."""
    if rest == ["--show-current"]:
        return ALLOW
    flags = [word for word in rest if word.startswith("-")]
    patterns = [word for word in rest if not word.startswith("-")]
    if all(flag in BRANCH_READ_FLAGS for flag in flags) and (
        not patterns or {"--list", "-l"} & set(flags)
    ):
        return ALLOW
    return not_allowed(
        "branch", "`git branch --show-current`, `git branch [-a|-r|-v|-vv] [--list <pattern>]`"
    )


def check_config(rest: list[str]) -> Verdict:
    """Reads only, verified with real git to leave the config unchanged: `--get <key>`,
    `get <key>`, `--list`, `-l`, `list`."""
    if rest in (["--list"], ["-l"], ["list"]) or (
        len(rest) == 2 and rest[0] in ("--get", "get") and not rest[1].startswith("-")
    ):
        return ALLOW
    return not_allowed(
        "config", "`git config --get <key>`, `git config get <key>`, `git config --list`"
    )


def check_fetch(rest: list[str]) -> Verdict:
    """`git fetch [--prune] [<remote> [<branch>]]`: with the default fetch refspec, it writes
    remote-tracking refs only (verified). A refspec that writes `refs/heads/` isn't checked
    (DL-28)."""
    flags = [word for word in rest if word.startswith("-")]
    names = [word for word in rest if not word.startswith("-")]
    if (
        set(flags) <= {"--prune", "-p", "-q", "--quiet"}
        and len(names) <= 2
        and all(LITERAL_NAME.fullmatch(name) for name in names)
    ):
        return ALLOW
    return not_allowed(
        "fetch", "`git fetch [--prune] [<remote> [<branch>]]` (no `src:dst` refspecs)"
    )


def check_stash(rest: list[str]) -> Verdict:
    """`git stash [push [-u] [-m <msg>]] | pop | drop | list | show`: the stash only (verified)."""
    head, tail = (rest[0], rest[1:]) if rest else ("push", [])
    if head in ("list", "show", "pop", "drop", "apply") and not tail:
        return ALLOW
    if head == "push" and stash_push_options(tail):
        return ALLOW
    return not_allowed(
        "stash", "`git stash [push [-u] [-m <message>]]`, `pop`, `drop`, `list`, `show`"
    )


def stash_push_options(tail: list[str]) -> bool:
    index = 0
    while index < len(tail):
        if tail[index] in ("-u", "--include-untracked", "-q", "--quiet"):
            index += 1
        elif tail[index] in ("-m", "--message") and index + 1 < len(tail):
            index += 2
        else:
            return False
    return True


COMMIT_FLAGS = {"-a", "--all", "-q", "--quiet", "--allow-empty", "--no-edit", "--amend"}
COMMIT_WITH_VALUE = {"-m", "--message", "-F", "--file", "-am"}


def check_commit(rest: list[str], call: GitCall) -> Verdict:
    """Off `main` (DL-21), with only these options (no hook-skipping, DL-24); `--amend` only
    while HEAD is unpushed (DL-23)."""
    index = 0
    while index < len(rest):
        word = rest[index]
        if word in COMMIT_WITH_VALUE and index + 1 < len(rest):
            index += 2
        elif word in COMMIT_FLAGS:
            index += 1
        else:
            return not_allowed(
                "commit",
                "`git commit [-a] [-q] [--allow-empty] [--no-edit] [--amend] (-m <message> | -F "
                "<file> | -F - <<'EOF')` (no `--no-verify`, `-n`, or paths)",
            )
    if call.branch() == MAIN:
        return blocked(f"`git commit` on `{MAIN}`. Commit on the slice branch. {TO_THE_OWNER}")
    if "--amend" in rest and call.repo.head_on_remote(call.where()):
        return blocked(f"`git commit --amend`: HEAD is already on the remote. {FIX_FORWARD}")
    return ALLOW


def is_main_ref(full: str | None) -> bool:
    """`refs/heads/main`, or a remote's `main` (`refs/remotes/<remote>/main`)."""
    return (
        full is not None
        and re.fullmatch(rf"refs/heads/{MAIN}|refs/remotes/[^/]+/{MAIN}", full) is not None
    )


def check_push(rest: list[str], call: GitCall) -> Verdict:
    """`git push [-u] <remote> <branch>` with a literal non-main branch, or a bare `git push`
    off main whose upstream isn't main (DL-22). No other option: nothing forces, deletes, or
    skips hooks (DL-23, DL-24). Configuration that redirects a push (`push.default`,
    `remote.<name>.push`, a mirror remote) isn't checked: GitHub's rulesets refuse any push to
    main, force-push, or deletion it could cause (DL-27)."""
    names = rest[1:] if rest[:1] in (["-u"], ["--set-upstream"]) else rest
    forms = "`git push`, `git push [-u] <remote> <branch>` (a literal branch, not `main`)"
    if not names and len(rest) == 0:
        if call.branch() == MAIN:
            return blocked(f"this push would update `{MAIN}`. {TO_THE_OWNER}")
        destination = call.repo.push_destination(call.where())
        if destination is None or destination.split("/", 1)[-1] == MAIN:
            return blocked(
                f"a bare `git push` needs a push destination that isn't `{MAIN}` (it has "
                f"{destination or 'none'}). Push with `git push -u origin <branch>`."
            )
        return ALLOW
    if len(names) != 2 or not all(LITERAL_NAME.fullmatch(name) for name in names):
        return not_allowed("push", forms)
    branch = names[1]
    if branch in (MAIN, "HEAD") or branch.endswith(f"/{MAIN}") or branch.startswith("refs/"):
        return blocked(
            f"this push would update `{MAIN}` (or can't be told apart from it). {TO_THE_OWNER}"
        )
    return ALLOW


def check_switch(rest: list[str]) -> Verdict:
    """`git switch <branch>`, or `git switch -c <new branch>` other than main."""
    if len(rest) == 1 and LITERAL_NAME.fullmatch(rest[0]):
        return ALLOW
    if len(rest) == 2 and rest[0] in ("-c", "--create") and LITERAL_NAME.fullmatch(rest[1]):
        if rest[1] == MAIN:
            return blocked(f"`git switch -c {MAIN}` would create or reset `{MAIN}`. {TO_THE_OWNER}")
        return ALLOW
    return not_allowed("switch", "`git switch <branch>`, `git switch -c <new branch>`")


def check_checkout(rest: list[str]) -> Verdict:
    if len(rest) >= 2 and rest[0] == "--":
        return ALLOW
    return not_allowed("checkout", "`git checkout -- <paths>` (use `git switch` for branches)")


RESET_MODES = {"--soft", "--mixed", "--hard"}


def check_reset(rest: list[str], call: GitCall) -> Verdict:
    """Paths (`git reset [HEAD] -- <paths>`, `git reset <paths>`), or `git reset [<mode>]
    [<commit>]` that drops no pushed commit (DL-23) and, on main, only to main itself (DL-21)."""
    forms = "`git reset [HEAD] -- <paths>`, `git reset [--soft|--mixed|--hard] [<commit>]`"
    words = [word for word in rest if word not in ("-q", "--quiet")]
    if "--" in words:
        before = words[: words.index("--")]
        return (
            ALLOW
            if before in ([], ["HEAD"]) and len(words) > len(before) + 1
            else not_allowed("reset", forms)
        )
    modes = [word for word in words if word in RESET_MODES]
    targets = [word for word in words if word not in RESET_MODES]
    if len(modes) > 1 or any(target.startswith("-") for target in targets):
        return not_allowed("reset", forms)
    if not targets:
        return ALLOW  # HEAD to itself: unstages, or with --hard discards changes; HEAD doesn't move
    if len(targets) > 1:
        return ALLOW if not modes else not_allowed("reset", forms)  # several paths
    target = targets[0]
    drops = call.repo.drops_pushed_commits(call.where(), target)
    if drops is None:
        return ALLOW if not modes else not_allowed("reset", forms)  # a path, not a commit
    if drops:
        return blocked(
            f"`git reset {target}` would drop commits that are already on the remote. {FIX_FORWARD}"
        )
    if call.branch() == MAIN and not is_main_ref(call.repo.full_ref(call.where(), target)):
        return blocked(
            f"`git reset {target}` on `{MAIN}` would move it to another commit. {TO_THE_OWNER}"
        )
    return ALLOW


def check_pull(rest: list[str], call: GitCall) -> Verdict:
    """`git pull --ff-only [<remote> <branch>]` (verified: refuses rather than merge); on main,
    only from main (DL-21)."""
    names = rest[1:] if rest[:1] == ["--ff-only"] else None
    if (
        names is None
        or len(names) not in (0, 2)
        or not all(LITERAL_NAME.fullmatch(n) for n in names)
    ):
        return not_allowed("pull", "`git pull --ff-only [<remote> <branch>]`")
    if call.branch() == MAIN:
        from_main = (
            names[1] == MAIN and names[0] in call.repo.remotes(call.where())
            if names
            else is_main_ref(call.repo.full_ref(call.where(), "@{upstream}"))
        )  # verified: `@{upstream}` resolves to the branch `branch.main.merge` names
        if not from_main:
            return blocked(f"on `{MAIN}`, `git pull --ff-only` only from `{MAIN}`. {TO_THE_OWNER}")
    return ALLOW


# --- gh ---------------------------------------------------------------------------------------

GH_ALLOWED = {
    ("pr", "create"), ("pr", "view"), ("pr", "list"), ("pr", "checks"), ("pr", "diff"),
    ("pr", "status"), ("pr", "ready"), ("pr", "edit"), ("run", "list"), ("run", "view"),
    ("run", "watch"), ("auth", "status"), ("repo", "view"), ("issue", "list"), ("issue", "view"),
}  # fmt: skip
OWNER_DECIDES = (
    "Merging a pull request, or writing to GitHub through the API, is the owner's call (DL-25). "
    "Allow it only if the owner said to."
)
GH_API_READ_FLAGS = {"--paginate", "--jq", "-q", "--silent", "-i", "--include", "--verbose"}


def gh_words(args: list[str]) -> list[str]:
    """The words of a gh command without `-R <repo>` / `--repo <repo>` / `--repo=<repo>`."""
    words: list[str] = []
    index = 0
    while index < len(args):
        if args[index] in ("-R", "--repo"):
            index += 2
            continue
        if not args[index].startswith("--repo="):
            words.append(args[index])
        index += 1
    return words


def check_gh(args: list[str], heredocs: list[str]) -> Verdict:
    """Listed read and pull-request commands; `gh pr merge` and every gh api call that isn't a
    plain read ask the owner (DL-25); anything else is blocked."""
    words = gh_words(args)
    if heredocs:
        return blocked(f"no heredoc with gh. {ONE_COMMAND}")
    if not words or words == ["--version"]:
        return ALLOW
    if words[:2] == ["auth", "status"] and len(words) > 2:
        return blocked(
            "`gh auth status` is allowed only with no options (`--show-token` prints the token)."
        )
    if tuple(words[:2]) in GH_ALLOWED:
        return ALLOW
    if words[:2] == ["pr", "merge"]:
        return Verdict(ask=OWNER_DECIDES)
    if words[0] == "api":
        return check_gh_api(words[1:])
    return blocked(
        f"this `gh {' '.join(words[:2])}` isn't in the git guard's allow-list. Allowed: "
        f"{', '.join(' '.join(pair) for pair in sorted(GH_ALLOWED))}, `gh api` reads. Anything "
        "else, ask the owner to run (`! <command>`)."
    )


def check_gh_api(rest: list[str]) -> Verdict:
    """A plain read: one endpoint (not graphql), only output flags (a `--jq <filter>` value
    allowed). Anything else (a method, a field, an input file, GraphQL) asks."""
    endpoints: list[str] = []
    index = 0
    while index < len(rest):
        word = rest[index]
        if word in ("--jq", "-q"):
            index += 2
            continue
        if word.startswith("-") and word not in GH_API_READ_FLAGS:
            return Verdict(ask=OWNER_DECIDES)
        if not word.startswith("-"):
            endpoints.append(word)
        index += 1
    if len(endpoints) != 1 or endpoints[0] == "graphql":
        return Verdict(ask=OWNER_DECIDES)
    return ALLOW


# --- Hook entry point -------------------------------------------------------------------------


def main(repo: Repo | None = None) -> int:
    try:
        data: dict[str, Any] = json.load(sys.stdin)
    except json.JSONDecodeError:
        print("Blocked by the git guard: the hook input isn't JSON.", file=sys.stderr)
        return 2
    tool_input: dict[str, Any] = data.get("tool_input") or {}
    command = tool_input.get("command")
    if not isinstance(command, str):
        return 0
    cwd = data.get("cwd")
    verdict = decide(command, Path(cwd) if isinstance(cwd, str) else None, repo or GitRepo())
    if verdict.block:
        # stderr is how a blocking hook tells Claude why.
        print(verdict.block, file=sys.stderr)
        return 2
    if verdict.ask:
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": verdict.ask,
            }
        }
        print(json.dumps(output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
