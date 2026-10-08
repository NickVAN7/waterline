"""`wl review-copy` (DL-29): a throwaway copy of the repository as it is about to be committed,
built against real git repositories."""

import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from waterline_cli import main, review_copy

runner = CliRunner()


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
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A repository with one commit, then: a modified tracked file, a staged new file, an
    untracked file in a subdirectory, an ignored build file, a `.env`, and a binary change."""
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "--quiet", "-b", "s1")
    (root / ".gitignore").write_text(".env\nbuild/\n")
    (root / "tracked.txt").write_text("committed\n")
    (root / "image.bin").write_bytes(b"\x00\x01committed")
    git(root, "add", ".")
    git(root, "commit", "--quiet", "-m", "first")
    (root / "tracked.txt").write_text("changed, not committed\n")
    (root / "image.bin").write_bytes(b"\x00\x02changed\xff")
    (root / "staged.txt").write_text("staged\n")
    git(root, "add", "staged.txt")
    (root / "docs").mkdir()
    (root / "docs" / "new.md").write_text("untracked\n")
    (root / "build").mkdir()
    (root / "build" / "out.o").write_text("ignored\n")
    (root / ".env").write_text("POSTGRES_PASSWORD=x\n")
    return root


def test_the_copy_is_the_repository_as_it_is_about_to_be_committed(
    repo: Path, tmp_path: Path
) -> None:
    dest = tmp_path / "copy"

    untracked = review_copy.make_copy(repo, dest, with_env=False)

    assert untracked == ["docs/new.md"]
    assert (dest / "tracked.txt").read_text() == "changed, not committed\n"
    assert (dest / "image.bin").read_bytes() == b"\x00\x02changed\xff"
    assert (dest / "staged.txt").read_text() == "staged\n"
    assert (dest / "docs" / "new.md").read_text() == "untracked\n"
    assert not (dest / "build").exists()
    assert not (dest / ".env").exists()
    assert git(dest, "rev-parse", "HEAD") == git(repo, "rev-parse", "HEAD")


@pytest.mark.parametrize(
    "setting",
    [
        # each changes `git diff`'s output (pass 4, finding 1; verified): color made the patch
        # unreadable and the copy silently lacked the changes
        ("color.ui", "always"),
        ("color.diff", "always"),
        ("diff.noprefix", "true"),
        ("diff.mnemonicPrefix", "true"),
    ],
)
def test_diff_settings_in_the_config_dont_change_the_copy(
    repo: Path, tmp_path: Path, setting: tuple[str, str]
) -> None:
    git(repo, "config", *setting)
    dest = tmp_path / "copy"

    review_copy.make_copy(repo, dest, with_env=False)

    assert (dest / "tracked.txt").read_text() == "changed, not committed\n"
    assert (dest / "image.bin").read_bytes() == b"\x00\x02changed\xff"


def test_a_diff_that_isnt_a_patch_fails_the_copy(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # `apply --allow-empty` would accept it and copy none of the changes (pass 4, finding 1)
    monkeypatch.setattr(review_copy, "DIFF", ("log", "-1"))

    with pytest.raises(review_copy.CopyError, match="git apply failed"):
        review_copy.make_copy(repo, tmp_path / "copy", with_env=False)


def test_untracked_symlinks_are_copied_as_links(repo: Path, tmp_path: Path) -> None:
    (repo / "link.txt").symlink_to("tracked.txt")
    (repo / "dangling").symlink_to("missing.txt")
    dest = tmp_path / "copy"

    review_copy.make_copy(repo, dest, with_env=False)

    assert (dest / "link.txt").readlink() == Path("tracked.txt")
    assert (dest / "dangling").readlink() == Path("missing.txt")


@pytest.mark.parametrize("inside", ["copy", "docs/copy"])
def test_a_destination_inside_the_repository_is_refused(repo: Path, inside: str) -> None:
    with pytest.raises(review_copy.CopyError, match="is inside the repository"):
        review_copy.make_copy(repo, repo / inside, with_env=False)
    assert not (repo / inside).exists()


def test_a_destination_that_is_a_file_is_refused(repo: Path, tmp_path: Path) -> None:
    (tmp_path / "copy").write_text("a file\n")

    with pytest.raises(review_copy.CopyError, match="isn't an empty directory"):
        review_copy.make_copy(repo, tmp_path / "copy", with_env=False)


def test_an_untracked_nested_repository_is_reported_with_the_partial_copy(
    repo: Path, tmp_path: Path
) -> None:
    git(repo / "docs", "init", "--quiet", "inner")

    with pytest.raises(
        review_copy.CopyError, match=r"docs/inner/ is a nested repository.*may hold a partial copy"
    ):
        review_copy.make_copy(repo, tmp_path / "copy", with_env=False)


def test_a_file_that_cannot_be_copied_is_reported_with_the_partial_copy(
    repo: Path, tmp_path: Path
) -> None:
    (repo / "docs" / "new.md").chmod(0)

    with pytest.raises(review_copy.CopyError, match=r"Permission denied.*may hold a partial copy"):
        review_copy.make_copy(repo, tmp_path / "copy", with_env=False)


def test_with_env_also_copies_the_env_file(repo: Path, tmp_path: Path) -> None:
    dest = tmp_path / "copy"

    review_copy.make_copy(repo, dest, with_env=True)

    assert (dest / ".env").read_text() == "POSTGRES_PASSWORD=x\n"


def test_with_env_and_no_env_file_copies_nothing_extra(repo: Path, tmp_path: Path) -> None:
    (repo / ".env").unlink()
    dest = tmp_path / "copy"

    review_copy.make_copy(repo, dest, with_env=True)

    assert not (dest / ".env").exists()


def test_making_a_copy_never_changes_the_repository(repo: Path, tmp_path: Path) -> None:
    before = git(repo, "status", "--porcelain=v2", "--branch", "--untracked-files=all")

    review_copy.make_copy(repo, tmp_path / "copy", with_env=True)

    assert git(repo, "status", "--porcelain=v2", "--branch", "--untracked-files=all") == before


def test_a_clean_repository_is_copied_as_committed(repo: Path, tmp_path: Path) -> None:
    git(repo, "add", "-A")
    git(repo, "commit", "--quiet", "-m", "everything")
    dest = tmp_path / "copy"

    assert review_copy.make_copy(repo, dest, with_env=False) == []
    assert (dest / "docs" / "new.md").read_text() == "untracked\n"


def test_a_non_empty_destination_is_refused(repo: Path, tmp_path: Path) -> None:
    dest = tmp_path / "copy"
    dest.mkdir()
    (dest / "keep.txt").write_text("mine\n")

    with pytest.raises(review_copy.CopyError, match="isn't an empty directory"):
        review_copy.make_copy(repo, dest, with_env=False)
    assert [path.name for path in dest.iterdir()] == ["keep.txt"]


def test_an_empty_destination_is_used(repo: Path, tmp_path: Path) -> None:
    dest = tmp_path / "copy"
    dest.mkdir()

    review_copy.make_copy(repo, dest, with_env=False)

    assert (dest / "tracked.txt").read_text() == "changed, not committed\n"


def test_a_failing_git_command_is_reported(tmp_path: Path) -> None:
    with pytest.raises(review_copy.CopyError, match="git clone failed"):
        review_copy.make_copy(tmp_path / "not-a-repo", tmp_path / "copy", with_env=False)


def test_a_failing_git_dash_c_command_names_its_subcommand(repo: Path) -> None:
    with pytest.raises(review_copy.CopyError, match="git apply failed"):
        review_copy._git("-C", str(repo), "apply", data=b"not a patch\n")  # pyright: ignore[reportPrivateUsage] -- the helper under test


def test_git_that_cannot_run_is_reported(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PATH", "")

    with pytest.raises(review_copy.CopyError, match="couldn't run git"):
        review_copy.make_copy(repo, tmp_path / "copy", with_env=False)


def test_the_command_reports_the_copy(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(main, "find_repo_root", lambda: repo)

    result = runner.invoke(main.app, ["review-copy", str(tmp_path / "copy"), "--with-env"])

    assert result.exit_code == 0, result.output
    assert result.output == f"Copy ready at {tmp_path / 'copy'} (1 untracked files copied).\n"
    assert (tmp_path / "copy" / ".env").is_file()


def test_the_command_exits_1_when_the_copy_fails(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "copy").mkdir()
    (tmp_path / "copy" / "x").write_text("x")
    monkeypatch.setattr(main, "find_repo_root", lambda: repo)

    result = runner.invoke(main.app, ["review-copy", str(tmp_path / "copy")])

    assert result.exit_code == 1
    assert "isn't an empty directory" in result.output


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (
            ["review-copy", "/work/c"],
            [
                "git clone --quiet /r /work/c",
                "git -C /r diff HEAD --binary --no-color --no-ext-diff --no-textconv "
                "--src-prefix=a/ --dst-prefix=b/ | git -C /work/c apply",
                "copy each file listed by `git -C /r ls-files --others --exclude-standard` "
                "into /work/c",
            ],
        ),
        (
            ["review-copy", "/work/c", "--with-env"],
            [
                "git clone --quiet /r /work/c",
                "git -C /r diff HEAD --binary --no-color --no-ext-diff --no-textconv "
                "--src-prefix=a/ --dst-prefix=b/ | git -C /work/c apply",
                "copy each file listed by `git -C /r ls-files --others --exclude-standard` "
                "into /work/c",
                "copy /r/.env into /work/c (if it exists)",
            ],
        ),
    ],
)
def test_dry_run_prints_what_it_would_run(
    monkeypatch: pytest.MonkeyPatch, args: list[str], expected: list[str]
) -> None:
    monkeypatch.setattr(main, "find_repo_root", lambda: Path("/r"))

    result = runner.invoke(main.app, [*args, "--dry-run"])

    assert result.exit_code == 0, result.output
    assert result.output.splitlines() == expected
