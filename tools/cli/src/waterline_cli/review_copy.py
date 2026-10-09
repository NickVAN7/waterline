"""`wl review-copy <dest>`: a throwaway copy of the repository as it is about to be committed.

The copy is the committed state plus the uncommitted changes (`git diff HEAD --binary`, applied)
and every untracked, non-ignored file; with `--with-env`, the `.env` file too. Reviewers make
their sabotage copies with it, and `fresh-clone-verifier` its fresh copy (without `.env`): the
git guard allows only one plain git command per call, so the clone-and-apply steps live here
(DL-29). It never changes the repository it copies.
"""

import os
import shutil
import subprocess
from pathlib import Path

# The patch's format, whatever the user's or repository's config says (verified: with
# `color.ui=always` an unpinned diff is ANSI text that `git apply` can't read).
DIFF = (
    "diff", "HEAD", "--binary", "--no-color", "--no-ext-diff", "--no-textconv",
    "--src-prefix=a/", "--dst-prefix=b/",
)  # fmt: skip


class CopyError(Exception):
    """The copy couldn't be made."""


def describe(root: Path, dest: Path, *, with_env: bool) -> list[str]:
    """What `make_copy` runs, for `--dry-run`."""
    lines = [
        f"git clone --quiet {root} {dest}",
        f"git -C {root} {' '.join(DIFF)} | git -C {dest} apply",
        f"copy each file listed by `git -C {root} ls-files --others --exclude-standard` "
        f"into {dest}",
    ]
    if with_env:
        lines.append(f"copy {root / '.env'} into {dest} (if it exists)")
    return lines


def _git(*args: str, data: bytes | None = None) -> bytes:
    try:
        result = subprocess.run(["git", *args], input=data, capture_output=True, check=False)
    except OSError as exc:
        raise CopyError(f"couldn't run git: {exc}") from exc
    if result.returncode != 0:
        raise CopyError(
            f"git {args[0] if args[0] != '-C' else args[2]} failed: "
            f"{result.stderr.decode(errors='replace').strip()}"
        )
    return result.stdout


def make_copy(root: Path, dest: Path, *, with_env: bool) -> list[str]:
    """Builds the copy at `dest` (absent or an empty directory, outside `root`); returns the
    untracked files it copied."""
    if dest.resolve().is_relative_to(root.resolve()):
        raise CopyError(f"{dest} is inside the repository; give a directory outside it")
    if dest.exists() and (not dest.is_dir() or any(dest.iterdir())):
        raise CopyError(f"{dest} isn't an empty directory; give a new or empty one")
    _git("clone", "--quiet", str(root), str(dest))
    try:
        return _fill(root, dest, with_env=with_env)
    except (CopyError, OSError) as exc:
        raise CopyError(f"{exc} ({dest} may hold a partial copy; delete it)") from exc


def _fill(root: Path, dest: Path, *, with_env: bool) -> list[str]:
    diff = _git("-C", str(root), *DIFF)
    if diff:
        _git("-C", str(dest), "apply", data=diff)
    listed = _git("-C", str(root), "ls-files", "--others", "--exclude-standard", "-z")
    untracked = [name for name in os.fsdecode(listed).split("\0") if name]
    for name in untracked:
        if name.endswith("/"):  # an untracked nested repository
            raise CopyError(f"{name} is a nested repository; it can't be copied")
        target = dest / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / name, target, follow_symlinks=False)
    if with_env and (root / ".env").is_file():
        shutil.copy2(root / ".env", dest / ".env")
    return untracked
