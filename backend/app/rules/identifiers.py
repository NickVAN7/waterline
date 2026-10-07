"""Project keys, slugs, and usernames (design-doc §3, "Project key rules", "Reserved slugs";
§4, "Users"). Pure: no database. Each check returns the first problem found, or None, so the API
can report a specific field error.
"""

import string
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
