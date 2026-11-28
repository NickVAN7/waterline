"""A task's branch name to copy (design-doc §6, Task, "Copy branch name"; DL-408), which branch
auto-detection (§12) matches."""

import re
import unicodedata

SLUG_MAX = 50

# Anything but a lowercase ASCII letter or a digit, as a username keeps (DL-408).
_OTHER = re.compile(r"[^a-z0-9]+")


def branch_name(display_id: str, title: str) -> str:
    """The lowercase `display_id` (e.g. `WTL-TA-45`) plus a slug of `title`, or the ID alone
    when the title leaves no slug: the title lowercased, accents removed, every run of other
    characters one hyphen, cut to `SLUG_MAX` with no hyphen at either end."""
    # NFKD splits an accented letter into the letter and its accent; dropping what isn't ASCII
    # then drops the accent (and any letter with none to split off, as a username does).
    # Equivalent mutants: the codec's name in either case is the same codec, and
    # `strip("XX-XX")` also strips uppercase X, which a lowercased title never holds.
    decomposed = unicodedata.normalize("NFKD", title.lower())
    ascii_title = decomposed.encode("ascii", "ignore").decode()  # pragma: no mutate
    slug = _OTHER.sub("-", ascii_title).strip("-")[:SLUG_MAX].rstrip("-")  # pragma: no mutate
    return f"{display_id.lower()}-{slug}" if slug else display_id.lower()
