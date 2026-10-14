"""Project keys, slugs, and usernames (design-doc §3, "Project key rules", "Reserved slugs";
§4, "Users"). Pure: no database. Each check returns the first problem found, or None, so the API
can report a specific field error.
"""

import string
import unicodedata
from enum import StrEnum

PROJECT_KEY_MIN = 3
PROJECT_KEY_MAX = 6
SLUG_MIN = 2
SLUG_MAX = 40

_UPPERCASE = frozenset(string.ascii_uppercase)
_LOWERCASE = frozenset(string.ascii_lowercase)
_KEY_CHARACTERS = _UPPERCASE | frozenset(string.digits)
_SLUG_CHARACTERS = _LOWERCASE | frozenset(string.digits) | {"-"}

# Top-level browser routes. Org slugs sit at the root of browser URLs (`/{org_slug}/...`), so
# none may equal one of these; workspace slugs follow the same list (design-doc §3). Every
# top-level route in the frontend's router must be listed here (a frontend test checks it,
# from S1-C14). `api` is the backend's path behind the Vite proxy; `assets`, the built files.
RESERVED_SLUGS: frozenset[str] = frozenset(
    {"account", "api", "assets", "sign-in", "status", "workspace"}
)


class IdentifierProblem(StrEnum):
    TOO_SHORT = "too_short"
    TOO_LONG = "too_long"
    MUST_START_WITH_LETTER = "must_start_with_letter"
    INVALID_CHARACTERS = "invalid_characters"
    RESERVED = "reserved"


def _format_problem(
    value: str,
    *,
    minimum: int,
    maximum: int,
    first: frozenset[str],
    allowed: frozenset[str],
) -> IdentifierProblem | None:
    if len(value) < minimum:
        return IdentifierProblem.TOO_SHORT
    if len(value) > maximum:
        return IdentifierProblem.TOO_LONG
    # Characters first, so `Acme` reads "invalid characters", not "must start with a letter".
    if not set(value) <= allowed:
        return IdentifierProblem.INVALID_CHARACTERS
    if value[0] not in first:
        return IdentifierProblem.MUST_START_WITH_LETTER
    return None


_ASCII_UPPERCASE = str.maketrans(string.ascii_lowercase, string.ascii_uppercase)


def normalize_project_key(raw: str) -> str:
    """Keys are uppercased as typed: `pmt` is `PMT`. ASCII letters only: `str.upper()` would
    turn a dotless i (U+0131) into `I` and `ß` into `SS`, making a valid key the user never
    typed; those stay as they are and fail as invalid characters."""
    return raw.translate(_ASCII_UPPERCASE)


def project_key_problem(key: str) -> IdentifierProblem | None:
    """3-6 uppercase ASCII letters or digits, starting with a letter (`^[A-Z][A-Z0-9]{2,5}$`).
    Normalize first: lowercase input is a problem here."""
    return _format_problem(
        key,
        minimum=PROJECT_KEY_MIN,
        maximum=PROJECT_KEY_MAX,
        first=_UPPERCASE,
        allowed=_KEY_CHARACTERS,
    )


def username_problem(username: str) -> IdentifierProblem | None:
    """The slug format (lowercase ASCII letters, digits, and hyphens, 2-40 characters, starting
    with a letter); the reserved list doesn't apply."""
    return _format_problem(
        username, minimum=SLUG_MIN, maximum=SLUG_MAX, first=_LOWERCASE, allowed=_SLUG_CHARACTERS
    )


def slug_problem(slug: str) -> IdentifierProblem | None:
    """A workspace or org slug: the username format, and not a reserved top-level route."""
    problem = username_problem(slug)
    if problem is None and slug in RESERVED_SLUGS:
        return IdentifierProblem.RESERVED
    return problem


def suggest_username(name: str, suffix: int | None = None) -> str | None:
    """A username suggested from a person's name (DL-66; build plan, "The user check"): the name
    lowercased, accents removed, and every other character the username rule doesn't allow
    dropped; the first and last remaining word joined by a hyphen (one word alone); cut to
    `SLUG_MAX`, or with `suffix` n, the base shortened so base plus `-n` fits; trailing hyphens
    stripped after any cut. None when no valid username results."""
    # NFKD splits an accented letter into the letter and its accent, which is then dropped.
    decomposed = unicodedata.normalize("NFKD", name.lower())
    words = [
        w
        for w in ("".join(c for c in word if c in _SLUG_CHARACTERS) for word in decomposed.split())
        if w
    ]
    if not words:
        return None
    base = words[0] if len(words) == 1 else f"{words[0]}-{words[-1]}"
    tail = "" if suffix is None else f"-{suffix}"
    # Equivalent mutant: `rstrip("XX-XX")` also strips uppercase X, which a lowercased base
    # never holds, so no input tells the two apart.
    candidate = base[: SLUG_MAX - len(tail)].rstrip("-") + tail  # pragma: no mutate
    return None if username_problem(candidate) else candidate
