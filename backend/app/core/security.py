"""Password hashing and session-token helpers (design-doc §4, "Slice 1 security checklist").

Argon2id hashing is CPU-heavy, so it runs in a worker thread and never blocks the event loop
(build-plan, "Async rules"). Tokens are 32 random bytes; only their SHA-256 hash is stored.
"""

import hashlib
import secrets

from anyio import to_thread
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

# argon2-cffi's defaults are Argon2id with RFC 9106's low-memory profile.
_hasher = PasswordHasher()

TOKEN_BYTES = 32

# A hash of a random, discarded password, made with the hasher's current parameters. Sign-in
# verifies against it when the email has no account, so a missing account costs the same time
# as a wrong password and response timing doesn't reveal which emails exist (design-doc §4).
_DUMMY_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$Cmo00xRVh2AcNLdG591NYQ"
    "$hzhaMcbOzFbRWNjLl0GwpFYHLp40gzxS4GiiWUtmiCM"
)


async def hash_password(password: str) -> str:
    """An Argon2id hash (with its salt and parameters encoded) for storing."""
    return await to_thread.run_sync(_hasher.hash, password)


async def verify_password(password_hash: str, password: str) -> bool:
    """Whether `password` matches `password_hash`. A malformed hash is a non-match, never an
    error the caller could leak."""

    def verify() -> bool:
        try:
            return _hasher.verify(password_hash, password)
        except VerificationError, InvalidHashError:
            return False

    return await to_thread.run_sync(verify)


async def verify_password_for_unknown_user(password: str) -> bool:
    """Do the same hashing work as `verify_password` for an email with no account; always
    False. Sign-in calls it instead of returning early."""
    await verify_password(_DUMMY_HASH, password)
    return False


def password_needs_rehash(password_hash: str) -> bool:
    """Whether a stored hash uses older parameters than the hasher's current ones. Sign-in
    re-hashes the password on a successful check when it does. Call it only after
    `verify_password` returned True: a malformed hash raises here."""
    return _hasher.check_needs_rehash(password_hash)


def generate_token() -> str:
    """A new session token for the cookie: 32 random bytes, URL-safe base64 (43 characters)."""
    return secrets.token_urlsafe(TOKEN_BYTES)


def hash_token(token: str) -> str:
    """The SHA-256 hex digest stored in place of the token; lookups hash the cookie's token and
    compare digests."""
    return hashlib.sha256(token.encode()).hexdigest()
