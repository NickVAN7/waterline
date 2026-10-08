"""PreToolUse hook (Bash): stop git and gh commands that would land work on `main`, rewrite
pushed history, skip hooks, or merge a pull request without the owner.

A guard against mistakes, not a security boundary: branch protection (TD-15) is the real
control. Reads the hook input (JSON) on stdin. Exit code 2 blocks the command and shows stderr
to Claude; a PreToolUse `permissionDecision` of "ask" on stdout makes Claude Code ask the user;
exit code 0 with no output lets the normal permission flow continue. A command that mentions
git or gh and can't be parsed with confidence is blocked (fail closed).
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

MAIN = "main"
MAIN_REFS = {MAIN, f"heads/{MAIN}", f"refs/heads/{MAIN}"}
# Stands in for anything expanded at run time ($VAR, $(...), `...`): its value is unknown.
UNKNOWN = "\x00"
MAX_DEPTH = 5

SIMPLE = (
    "Run git and gh as simple commands (one per call, or joined with && or ;), with literal "
    "arguments, not through aliases, wrappers like xargs, or a shell reading stdin."
)
FIX_FORWARD = (
    "Make a follow-up commit instead (`fix(<ID>): <what>`); pushed history is never rewritten."
)


class Unparseable(Exception):  # noqa: N818 -- reads as a verdict: "Unparseable(reason)"
    """The command mentions git or gh but can't be analyzed with confidence."""


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
    def alias(self, cwd: Path, name: str) -> str | None: ...


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
                timeout=10,
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

    def alias(self, cwd: Path, name: str) -> str | None:
        return self._out(cwd, "config", "--get", f"alias.{name}")


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

    def expansion(self, *, quoted: bool = False) -> bool:
        """At `$`, `` ` ``, or (unquoted) `<(` or `>(`: records a command substitution or skips
        a variable, returning True; False when it's a plain character."""
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
                end = self.text.find("}", self.i)
                if end == -1:
                    raise Unparseable("an unclosed ${")
                self.i = end + 1
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

    def end_word() -> None:
        nonlocal word, in_word, drop_next_word, heredoc_next_word
        if in_word:
            value = "".join(word)
            if heredoc_next_word is not None:
                pending_heredocs.append(
                    (value.replace(UNKNOWN, ""), heredoc_next_word, segments[-1])
                )
                heredoc_next_word = None
            elif drop_next_word:
                drop_next_word = False
            else:
                segments[-1].words.append(value)
        word, in_word = [], False

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
            in_word = True
            scanner.i += 2
        elif char == "'":
            start = scanner.i
            scanner.skip_quoted("'")
            word.append(text[start + 1 : scanner.i - 1])
            in_word = True
        elif char == '"':
            in_word = True
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
            scanner.i += len(operator)
        else:
            word.append(char)
            in_word = True
            scanner.i += 1
    end_word()
    if pending_heredocs:
        read_heredoc_bodies()
    return Script([s for s in segments if s.words], scanner.substitutions)


# --- Analysis ---------------------------------------------------------------------------------

ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z_0-9]*=")
PREFIX_WORDS = {"if", "then", "else", "elif", "do", "while", "until", "!", "{", "time", "nohup"}
SHELLS = {"bash", "sh", "zsh", "dash", "ksh"}
# Commands whose arguments are only data, so `which git` or `grep gh docs` runs nothing.
DATA_COMMANDS = {
    "echo", "printf", "which", "type", "whereis", "man", "grep", "egrep", "fgrep", "rg", "ls",
    "cat", "head", "tail", "wc", "test", "[", "[[", "true", "false", "cut", "sort", "uniq", "tr",
    "diff", "jq", "basename", "dirname", "realpath", "readlink",
}  # fmt: skip
# Names that, as an argument to some other command, may be run by it (xargs git, find -exec git).
RUNNABLE = {"git", "gh", "eval", "xargs", "env", *SHELLS}
ENV_FLAGS = {"-i", "--ignore-environment", "-0", "--null", "-v", "--debug", "--"}


def mentions_git(text: str) -> bool:
    return re.search(r"\b(git|gh)\b", text) is not None


def analyze(command: str, cwd: Path | None, repo: Repo, depth: int = 0) -> Verdict:
    """The verdict for a whole command line: the first block, else the first ask, else allow."""
    if not mentions_git(command):
        return ALLOW
    if depth > MAX_DEPTH:
        raise Unparseable("commands nested too deeply")
    script = tokenize(command)
    verdicts = [analyze(inner, cwd, repo, depth + 1) for inner in script.substitutions]
    for segment in script.segments:
        verdict, cwd = analyze_segment(segment, cwd, repo, depth)
        verdicts.append(verdict)
    return next(
        (v for v in verdicts if v.block),
        next((v for v in verdicts if v.ask), ALLOW),
    )


def basename(word: str) -> str:
    return word.rsplit("/", 1)[-1]


def resolve_path(cwd: Path | None, path: str) -> Path | None:
    """A literal path relative to `cwd`; None when it can't be known before running."""
    if cwd is None or UNKNOWN in path or path == "-":
        return None
    return (cwd / os.path.expanduser(path)).resolve()


def analyze_segment(
    segment: Segment, cwd: Path | None, repo: Repo, depth: int
) -> tuple[Verdict, Path | None]:
    """The verdict for one simple command, and the working directory after it."""
    words = segment.words
    index = 0
    while index < len(words) and (ASSIGNMENT.match(words[index]) or words[index] in PREFIX_WORDS):
        index += 1
    if index < len(words) and words[index] in ("command", "builtin", "exec"):
        if words[index] == "command" and words[index + 1 : index + 2] in (["-v"], ["-V"]):
            return ALLOW, cwd  # a lookup, not a run
        index += 1
    if index < len(words) and words[index] == "env":
        index += 1
        while index < len(words) and (words[index] in ENV_FLAGS or ASSIGNMENT.match(words[index])):
            index += 1
        if index < len(words) and words[index].startswith("-"):
            raise Unparseable(f"`env {words[index]}`")
    if index >= len(words):
        return ALLOW, cwd
    name, args = basename(words[index]), words[index + 1 :]
    if name == "git":
        return analyze_git(args, cwd, repo, depth), cwd
    if name == "gh":
        return analyze_gh(args), cwd
    if name in SHELLS:
        return analyze_shell(name, args, segment.heredocs, cwd, repo, depth), cwd
    if name == "eval":
        return analyze(" ".join(args), cwd, repo, depth + 1), cwd
    if name in ("cd", "pushd"):
        return ALLOW, resolve_path(cwd, args[0] if args else "~")
    if name == "popd":
        return ALLOW, None
    if name not in DATA_COMMANDS:
        runnable = next((arg for arg in args if basename(arg) in RUNNABLE), None)
        if runnable is not None:
            raise Unparseable(f"`{name}` may run `{basename(runnable)}`")
    return ALLOW, cwd


def analyze_shell(
    name: str, args: list[str], heredocs: list[str], cwd: Path | None, repo: Repo, depth: int
) -> Verdict:
    """`bash -c '<script>'` is checked like any command line; a shell reading a heredoc checks
    its body; a shell reading stdin can't be checked."""
    index, has_c = 0, False
    while index < len(args) and args[index].startswith(("-", "+")) and args[index] != "--":
        option = args[index]
        index += 1
        if option[0] == "-" and not option.startswith("--") and "c" in option:
            has_c = True
        if option in ("-o", "+o"):
            index += 1
    if index < len(args) and args[index] == "--":
        index += 1
    if has_c:
        if index >= len(args):
            raise Unparseable(f"`{name} -c` without a command")
        return analyze(args[index], cwd, repo, depth + 1)
    if heredocs:
        verdicts = [analyze(body, cwd, repo, depth + 1) for body in heredocs]
        return next((v for v in verdicts if v.block or v.ask), ALLOW)
    if index < len(args):
        return ALLOW  # runs a script file
    raise Unparseable(f"`{name}` reading its commands from stdin")


# --- git --------------------------------------------------------------------------------------

GLOBAL_FLAGS = {
    "-p", "--paginate", "-P", "--no-pager", "--no-replace-objects", "--bare",
    "--literal-pathspecs", "--glob-pathspecs", "--noglob-pathspecs", "--icase-pathspecs",
    "--no-optional-locks", "--no-advice", "--html-path", "--man-path", "--info-path",
    "--version", "--help", "-v", "-h", "--exec-path",
}  # fmt: skip
GLOBAL_WITH_VALUE = {"--git-dir", "--work-tree", "--namespace", "--super-prefix", "--config-env"}
# Builtins and common commands, so a name outside this list is checked for being an alias.
KNOWN_COMMANDS = {
    "add", "am", "annotate", "apply", "archive", "bisect", "blame", "branch", "bundle",
    "cat-file", "check-ignore", "checkout", "cherry", "cherry-pick", "citool", "clean", "clone",
    "commit", "config", "count-objects", "describe", "diff", "diff-files", "diff-index",
    "diff-tree", "difftool", "fetch", "for-each-ref", "format-patch", "fsck", "gc", "grep",
    "hash-object", "help", "init", "log", "ls-files", "ls-remote", "ls-tree", "merge",
    "merge-base", "mergetool", "mv", "name-rev", "notes", "pull", "push", "range-diff",
    "rebase", "reflog", "remote", "repack", "replace", "reset", "restore", "rev-list",
    "rev-parse", "revert", "rm", "shortlog", "show", "show-branch", "show-ref", "sparse-checkout",
    "stash", "status", "submodule", "switch", "symbolic-ref", "tag", "update-index",
    "update-ref", "var", "verify-commit", "verify-tag", "version", "whatchanged", "worktree",
    "write-tree", "maintenance", "lfs",
}  # fmt: skip


@dataclass
class GitContext:
    cwd: Path | None
    unknown_repo: str | None = None  # why the repository can't be known, if it can't
    configs: list[str] = field(default_factory=list[str])

    def where(self) -> Path:
        if self.cwd is None or self.unknown_repo:
            reason = self.unknown_repo or "the working directory isn't a literal path"
            raise CantTell(reason)
        return self.cwd


class CantTell(Exception):  # noqa: N818 -- reads as a verdict
    """The repository a git command runs in can't be known before it runs."""


def analyze_git(args: list[str], cwd: Path | None, repo: Repo, depth: int = 0) -> Verdict:
    context = GitContext(cwd)
    index = 0
    while index < len(args) and args[index].startswith("-"):
        option = args[index]
        name, has_value, _ = option.partition("=")
        if option == "-C":
            path = args[index + 1] if index + 1 < len(args) else UNKNOWN
            context.cwd = resolve_path(context.cwd, path)
            index += 2
        elif option == "-c" or (option.startswith("-c") and not option.startswith("--")):
            value = option[2:] or (args[index + 1] if index + 1 < len(args) else "")
            context.configs.append(value)
            index += 1 if option[2:] else 2
        elif name in GLOBAL_WITH_VALUE:
            value = option.partition("=")[2] if has_value else ""
            if name == "--config-env":
                context.configs.append(value or (args[index + 1] if index + 1 < len(args) else ""))
            elif name in ("--git-dir", "--work-tree"):
                context.unknown_repo = f"`{name}` names another repository"
            index += 1 if has_value else 2
        elif option in GLOBAL_FLAGS or name in ("--exec-path", "--list-cmds"):
            index += 1
        else:
            raise Unparseable(f"the git option `{option}`")
    for config in context.configs:
        key = config.partition("=")[0].lower()
        if key.startswith("alias."):
            raise Unparseable("an alias defined with `git -c`")
        if key == "core.hookspath":
            return blocked(
                "`-c core.hooksPath` skips the repository's hooks. Fix what the hook reports "
                "and run the command again with the hooks."
            )
    if index >= len(args):
        return ALLOW
    command, rest = args[index], args[index + 1 :]
    try:
        if command not in KNOWN_COMMANDS:
            return analyze_alias(command, rest, context, repo, depth)
        return check_git_command(command, rest, context, repo)
    except CantTell as exc:
        return blocked(
            f"can't tell which repository `git {command}` runs in ({exc}). Run it from the "
            "repository, or with `git -C <path>` and a literal path."
        )


def analyze_alias(
    command: str, rest: list[str], context: GitContext, repo: Repo, depth: int
) -> Verdict:
    if UNKNOWN in command:
        raise Unparseable("a git subcommand that's only known at run time")
    alias = repo.alias(context.where(), command)
    if alias is None:
        return ALLOW  # not an alias: an external git-<command>, or a typo git rejects
    if depth >= MAX_DEPTH:
        raise Unparseable("git aliases nested too deeply")
    if alias.startswith("!"):
        return analyze(f"{alias[1:]} {shlex.join(rest)}", context.cwd, repo, depth + 1)
    return analyze_git([*shlex.split(alias), *rest], context.cwd, repo, depth + 1)


def check_git_command(command: str, rest: list[str], context: GitContext, repo: Repo) -> Verdict:
    match command:
        case "commit":
            return check_commit(rest, context, repo)
        case "merge":
            return check_merge(rest, context, repo)
        case "push":
            return check_push(rest, context, repo)
        case "rebase":
            return check_rebase(rest)
        case "reset":
            return check_reset(rest, context, repo)
        case _:
            return ALLOW


def on_main(context: GitContext, repo: Repo) -> bool:
    return repo.current_branch(context.where()) == MAIN


def long_option(option: str, full: str, shortest: str) -> bool:
    """Whether `option` (before any `=`) is `full` or an abbreviation git accepts for it."""
    name = option.partition("=")[0]
    return full.startswith(name) and len(name) >= len(shortest)


@dataclass
class Parsed:
    flags: list[str]
    positionals: list[str]
    after_dashdash: list[str]


def parse_options(
    rest: list[str], short_with_value: str, long_with_value: set[str], *, bundle_value: str = ""
) -> Parsed:
    """Options and positionals, git style: short flags bundle (`-am msg`), a short option in
    `short_with_value` takes the rest of its bundle or the next word, and `--` ends options."""
    flags: list[str] = []
    positionals: list[str] = []
    index = 0
    while index < len(rest):
        word = rest[index]
        index += 1
        if word == "--":
            return Parsed(flags, positionals, rest[index:])
        if word.startswith("--"):
            flags.append(word)
            if "=" not in word and word in long_with_value:
                index += 1
        elif word.startswith("-") and len(word) > 1:
            for position, char in enumerate(word[1:], start=1):
                flags.append(f"-{char}")
                if char in short_with_value or char in bundle_value:
                    if position == len(word) - 1 and char in short_with_value:
                        index += 1
                    break
        else:
            positionals.append(word)
    return Parsed(flags, positionals, [])


COMMIT_SHORT_VALUE = "mFCct"
COMMIT_LONG_VALUE = {
    "--message", "--file", "--author", "--date", "--template", "--reuse-message",
    "--reedit-message", "--fixup", "--squash", "--cleanup", "--trailer", "--pathspec-from-file",
}  # fmt: skip
SKIP_HOOKS = (
    "skipping the hooks (`--no-verify`, or `-n` on commit) isn't allowed. Fix what the hook "
    "reports and run the command again with the hooks."
)


def check_commit(rest: list[str], context: GitContext, repo: Repo) -> Verdict:
    parsed = parse_options(rest, COMMIT_SHORT_VALUE, COMMIT_LONG_VALUE, bundle_value="Su")
    if any(f == "-n" or long_option(f, "--no-verify", "--no-veri") for f in parsed.flags):
        return blocked(SKIP_HOOKS)
    if on_main(context, repo):
        return blocked(
            f"`git commit` on `{MAIN}`. Commit on the slice branch (`git switch s<n>`): "
            f"`{MAIN}` changes only when the owner merges the slice's pull request."
        )
    amend = any(long_option(f, "--amend", "--am") for f in parsed.flags)
    if amend and repo.head_on_remote(context.where()):
        return blocked(f"`git commit --amend`: HEAD is already on the remote. {FIX_FORWARD}")
    return ALLOW


def check_merge(rest: list[str], context: GitContext, repo: Repo) -> Verdict:
    if "--abort" in rest or "--quit" in rest:
        return ALLOW
    if any(long_option(f, "--no-verify", "--no-veri") for f in rest):
        return blocked(SKIP_HOOKS)
    if on_main(context, repo):
        return blocked(
            f"`git merge` on `{MAIN}`. Only the owner merges into `{MAIN}`, through the slice's "
            "pull request."
        )
    return ALLOW


PUSH_DANGEROUS = {
    "--force": "a force push rewrites pushed history. " + FIX_FORWARD,
    "--force-with-lease": "a force push rewrites pushed history. " + FIX_FORWARD,
    "--force-if-includes": "a force push rewrites pushed history. " + FIX_FORWARD,
    "--mirror": "`--mirror` overwrites and deletes remote refs. Push the slice branch by name.",
    "--delete": "deleting a remote branch is the owner's call. Ask them.",
    "--prune": "`--prune` deletes remote branches. Push the slice branch by name.",
    "--all": f"`--all` pushes every branch, `{MAIN}` included. Push the slice branch by name.",
    "--branches": f"`--branches` pushes every branch, `{MAIN}` included. Push the slice branch.",
    "--no-verify": SKIP_HOOKS,
}
PUSH_KNOWN = {
    "--follow-tags", "--no-follow-tags", "--dry-run", "--porcelain", "--tags", "--signed",
    "--no-signed", "--atomic", "--no-atomic", "--push-option", "--receive-pack", "--exec",
    "--repo", "--set-upstream", "--thin", "--no-thin", "--quiet", "--verbose", "--progress",
    "--no-progress", "--recurse-submodules", "--no-recurse-submodules", "--verify", "--ipv4",
    "--ipv6", "--no-force-with-lease", "--no-force-if-includes",
}  # fmt: skip
PUSH_LONG_VALUE = {"--push-option", "--receive-pack", "--exec", "--repo"}
TO_MAIN = (
    f"this push would update `{MAIN}`. Push the slice branch (`git push origin s<n>`): `{MAIN}` "
    "changes only when the owner merges the slice's pull request."
)


def check_push(rest: list[str], context: GitContext, repo: Repo) -> Verdict:
    parsed = parse_options(rest, "o", PUSH_LONG_VALUE)
    for flag in parsed.flags:
        if flag in ("-f", "-d"):
            return blocked(PUSH_DANGEROUS["--force" if flag == "-f" else "--delete"])
        name = flag.partition("=")[0]
        if name.startswith("--") and name not in PUSH_KNOWN:
            danger = [full for full in PUSH_DANGEROUS if full.startswith(name)]
            if danger:
                return blocked(PUSH_DANGEROUS[danger[0]])
    # The first positional is the repository, unless `--repo=<repo>` named it.
    named_repo = any(flag.startswith("--repo=") for flag in parsed.flags)
    refspecs = (parsed.positionals + parsed.after_dashdash)[0 if named_repo else 1 :]
    for refspec in refspecs:
        verdict = check_refspec(refspec, context, repo)
        if verdict.block:
            return verdict
    if not refspecs:
        if on_main(context, repo):
            return blocked(TO_MAIN)
        destination = repo.push_destination(context.where())
        if destination is not None and destination.split("/", 1)[-1] == MAIN:
            return blocked(TO_MAIN)
    return ALLOW


def check_refspec(refspec: str, context: GitContext, repo: Repo) -> Verdict:
    if refspec.startswith("+"):
        return blocked(PUSH_DANGEROUS["--force"])
    if refspec.startswith(":"):
        return blocked(PUSH_DANGEROUS["--delete"])
    if UNKNOWN in refspec or "*" in refspec:
        return blocked(
            f"can't tell where `{refspec.replace(UNKNOWN, '$…')}` pushes. Name the slice branch "
            "literally (`git push origin s<n>`)."
        )
    source, _, destination = refspec.partition(":")
    if not destination and source in ("HEAD", "@"):
        destination = repo.current_branch(context.where()) or ""
    if (destination or source) in MAIN_REFS:
        return blocked(TO_MAIN)
    return ALLOW


def check_rebase(rest: list[str]) -> Verdict:
    if "--abort" in rest or "--quit" in rest:
        return ALLOW
    return blocked(
        "`git rebase` rewrites history, and nothing on a slice branch needs one. "
        f"{FIX_FORWARD} (`git rebase --abort` and `--quit` are allowed.)"
    )


RESET_LONG_VALUE = {"--pathspec-from-file"}


def check_reset(rest: list[str], context: GitContext, repo: Repo) -> Verdict:
    parsed = parse_options(rest, "", RESET_LONG_VALUE)
    paths = parsed.after_dashdash or len(parsed.positionals) > 1
    patch = any(f in ("-p", "--patch") or f.startswith("--pathspec") for f in parsed.flags)
    if paths or patch or not parsed.positionals:
        return ALLOW  # resets paths in the index, or HEAD to itself: HEAD doesn't move
    target = parsed.positionals[0]
    if UNKNOWN in target:
        return blocked(
            "can't tell which commit `git reset` moves to. Name it literally, so the guard can "
            "check that no pushed commit is dropped."
        )
    if repo.drops_pushed_commits(context.where(), target):
        return blocked(
            f"`git reset {target}` would drop commits that are already on the remote. "
            f"{FIX_FORWARD} (Resetting unpushed commits is allowed.)"
        )
    return ALLOW


# --- gh ---------------------------------------------------------------------------------------

GH_COMMANDS = {
    "accessibility", "agent-task", "alias", "api", "attestation", "auth", "browse", "cache",
    "co", "codespace", "completion", "config", "copilot", "extension", "gist", "gpg-key", "help",
    "issue", "label", "org", "pr", "preview", "project", "release", "repo", "ruleset", "run",
    "search", "secret", "ssh-key", "status", "variable", "version", "workflow",
}  # fmt: skip
OWNER_MERGES = (
    'Merging a pull request is the owner\'s call (build plan, "Pull requests"). Allow this only '
    "if the owner said to merge."
)
MERGE_MUTATIONS = ("mergePullRequest", "enablePullRequestAutoMerge", "mergeBranch")


def gh_words(args: list[str]) -> Iterator[str]:
    """The words of a gh command without `-R`/`--repo <repo>`, which may appear anywhere."""
    index = 0
    while index < len(args):
        if args[index] in ("-R", "--repo"):
            index += 2
            continue
        yield args[index]
        index += 1


def analyze_gh(args: list[str]) -> Verdict:
    words = [w for w in gh_words(args) if not w.startswith("--repo=")]
    command = next((w for w in words if not w.startswith("-")), None)
    if command is None:
        return ALLOW
    if UNKNOWN in command or command not in GH_COMMANDS:
        raise Unparseable(f"`gh {command.replace(UNKNOWN, '$…')}` (an alias or extension?)")
    positionals = [w for w in words if not w.startswith("-")]
    if positionals[:2] == ["pr", "merge"]:
        return Verdict(ask=OWNER_MERGES)
    if command == "api":
        merges_endpoint = any(re.search(r"pulls/[^/]+/merge\b", w) for w in positionals[1:])
        mutation = any(m in w for w in words for m in MERGE_MUTATIONS)
        unseen = "graphql" in positionals and any(w.startswith("--input") for w in words)
        if merges_endpoint or mutation or unseen:
            return Verdict(ask=OWNER_MERGES)
    return ALLOW


# --- Hook entry point -------------------------------------------------------------------------


def decide(command: str, cwd: Path | None, repo: Repo) -> Verdict:
    try:
        return analyze(command, cwd, repo)
    except Unparseable as exc:
        return blocked(f"it can't check this command with confidence ({exc}). {SIMPLE}")


def main(repo: Repo | None = None) -> int:
    try:
        data: dict[str, Any] = json.load(sys.stdin)
    except json.JSONDecodeError:
        print("Blocked by the git guard: the hook input isn't JSON.", file=sys.stderr)  # noqa: T201
        return 2
    tool_input: dict[str, Any] = data.get("tool_input") or {}
    command = tool_input.get("command")
    if not isinstance(command, str):
        return 0
    cwd = data.get("cwd")
    verdict = decide(command, Path(cwd) if isinstance(cwd, str) else None, repo or GitRepo())
    if verdict.block:
        # stderr is how a blocking hook tells Claude why.
        print(verdict.block, file=sys.stderr)  # noqa: T201
        return 2
    if verdict.ask:
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": verdict.ask,
            }
        }
        print(json.dumps(output))  # noqa: T201
    return 0


if __name__ == "__main__":
    sys.exit(main())
