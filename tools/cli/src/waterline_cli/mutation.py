"""Whether `wl check` can skip mutation testing (DL-99): it runs again only when something it
depends on changed since its last green run. `wl check --full` (CI) always runs it.

The inputs are everything a mutant's test run imports or is configured by: the app, all of
`tests/` (the unit tests import factories and support helpers from across it), and the backend's
configuration and lockfile. Their hash is stored next
to mutmut's results after a green run.
"""

import hashlib
from pathlib import Path

INPUTS = ("app", "tests", "pyproject.toml", "uv.lock")
STAMP = Path("mutants") / "inputs.sha256"


def inputs_hash(backend: Path) -> str:
    digest = hashlib.sha256()
    for name in INPUTS:
        path = backend / name
        # Every file, not only .py: a test can read data files too.
        files = (
            sorted(p for p in path.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
            if path.is_dir()
            else [path]
        )
        for file in files:
            digest.update(file.relative_to(backend).as_posix().encode())
            digest.update(b"\0")
            digest.update(file.read_bytes())
            digest.update(b"\0")
    return digest.hexdigest()


def is_current(backend: Path, digest: str) -> bool:
    """True when the last green mutation run tested exactly the inputs hashed as `digest`."""
    stamp = backend / STAMP
    return stamp.is_file() and stamp.read_text().strip() == digest


def record(backend: Path, digest: str) -> None:
    """Mark `digest` (taken before the run) as green."""
    (backend / STAMP).write_text(digest + "\n")
