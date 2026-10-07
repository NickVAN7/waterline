"""The password policy (design-doc §4, "Password policy"). Pure: whether the new password equals
the current one needs a hash check, so the caller does it and passes the answer in.

The same policy applies to changing a password, an admin reset, and a new account.
"""

from enum import StrEnum

# TD-12: the minimum rises to 12 before the first non-local deployment.
MIN_LENGTH = 8
MAX_LENGTH = 256


class PasswordProblem(StrEnum):
    TOO_SHORT = "too_short"
    TOO_LONG = "too_long"
    SAME_AS_EMAIL = "same_as_email"
    SAME_AS_USERNAME = "same_as_username"
    SAME_AS_CURRENT = "same_as_current"


def password_problems(
    password: str, *, email: str, username: str, same_as_current: bool
) -> list[PasswordProblem]:
    """Every problem with `password` for this account, in a fixed order; empty if it's
    acceptable. Length counts characters, not bytes; there are no composition rules.
    `same_as_current` is required, so no caller can skip the check by leaving it out: True when
    the caller has verified the password matches the account's current one, False for a new
    account (no current password)."""
    found: list[PasswordProblem] = []
    if len(password) < MIN_LENGTH:
        found.append(PasswordProblem.TOO_SHORT)
    if len(password) > MAX_LENGTH:
        found.append(PasswordProblem.TOO_LONG)
    folded = password.casefold()
    if folded == email.casefold():
        found.append(PasswordProblem.SAME_AS_EMAIL)
    if folded == username.casefold():
        found.append(PasswordProblem.SAME_AS_USERNAME)
    if same_as_current:
        found.append(PasswordProblem.SAME_AS_CURRENT)
    return found
