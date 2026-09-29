"""Password hashing and session tokens (design-doc §4, "Slice 1 security checklist")."""

import threading
from typing import Any

import pytest

from app.core import security

pytestmark = [pytest.mark.anyio, pytest.mark.security]


async def test_password_hash_is_argon2id_and_verifies_only_the_same_password() -> None:
    hashed = await security.hash_password("correct horse battery staple")

    assert hashed.startswith("$argon2id$")
    assert await security.verify_password(hashed, "correct horse battery staple") is True
    assert await security.verify_password(hashed, "correct horse battery stapler") is False


async def test_the_same_password_hashes_differently_each_time() -> None:
    first = await security.hash_password("secret")
    second = await security.hash_password("secret")

    assert first != second  # salted


async def test_a_malformed_hash_is_a_non_match_not_an_error() -> None:
    assert await security.verify_password("not-a-hash", "secret") is False


class _ThreadRecordingHasher:
    """Stands in for argon2's PasswordHasher and records which thread each call ran on."""

    def __init__(self) -> None:
        self.threads: list[int] = []

    def hash(self, password: str) -> str:
        self.threads.append(threading.get_ident())
        return f"hashed:{password}"

    def verify(self, password_hash: str, password: str) -> bool:
        self.threads.append(threading.get_ident())
        return password_hash == f"hashed:{password}"


async def test_hashing_and_verifying_run_off_the_event_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = _ThreadRecordingHasher()
    fake: Any = recorder
    monkeypatch.setattr(security, "_hasher", fake)
    event_loop_thread = threading.get_ident()

    hashed = await security.hash_password("secret")
    verified = await security.verify_password(hashed, "secret")

    assert verified is True
    assert len(recorder.threads) == 2
    assert event_loop_thread not in recorder.threads


def test_token_is_32_random_bytes_as_43_url_safe_characters() -> None:
    token = security.generate_token()

    assert len(token) == 43
    assert set(token) <= set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")


def test_each_token_is_new() -> None:
    assert security.generate_token() != security.generate_token()


def test_token_hash_is_the_sha256_hex_digest() -> None:
    # SHA-256 of "abc" (FIPS 180-2 test vector)
    assert security.hash_token("abc") == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )


async def test_unknown_user_check_hashes_off_the_event_loop_and_never_matches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = _ThreadRecordingHasher()
    fake: Any = recorder
    monkeypatch.setattr(security, "_hasher", fake)

    matched = await security.verify_password_for_unknown_user("secret")

    assert matched is False
    assert len(recorder.threads) == 1  # it did the hashing work, off the event loop
    assert threading.get_ident() not in recorder.threads


async def test_unknown_user_check_never_matches_with_the_real_hasher() -> None:
    assert await security.verify_password_for_unknown_user("any password") is False


def test_dummy_hash_uses_the_hashers_current_parameters() -> None:
    """Otherwise the unknown-user path would take a different time from a real check."""
    assert security.password_needs_rehash(security._DUMMY_HASH) is False  # pyright: ignore[reportPrivateUsage]


def test_hash_made_with_weaker_parameters_needs_rehash() -> None:
    weaker = "$argon2id$v=19$m=8,t=1,p=1$c29tZXNhbHQ$ZGFsbHlkYWxseWRhbGx5ZGFsbHk"

    assert security.password_needs_rehash(weaker) is True
