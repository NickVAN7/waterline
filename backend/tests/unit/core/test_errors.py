"""Which stale rows are version conflicts (409) and which are rows that are gone (404)."""

import pytest
from sqlalchemy.orm.exc import StaleDataError
from starlette.types import Message, Receive, Scope, Send

from app.core.base_model import StaleVersionError
from app.core.db import stale_row_error
from app.core.errors import NotFoundError, StaleRowError, UnhandledErrorMiddleware
from tests.support import (
    models,  # noqa: F401  # pyright: ignore[reportUnusedImport] -- registers the support tables
)


@pytest.mark.parametrize(
    ("error", "gone", "answer"),
    [
        # SQLAlchemy's own wording, on a versioned and a non-versioned table
        (
            StaleDataError(
                "UPDATE statement on table 'support_document' expected to update 1 row(s); "
                "0 were matched."
            ),
            False,
            StaleRowError,
        ),
        (
            StaleDataError(
                "UPDATE statement on table 'support_widget' expected to update 1 row(s); "
                "0 were matched."
            ),
            False,
            NotFoundError,
        ),
        # a DELETE raises only on a versioned table (non-versioned ones just warn)
        (
            StaleDataError(
                "DELETE statement on table 'support_document' expected to delete 1 row(s); "
                "0 were matched.  Please set confirm_deleted_rows=False within the mapper "
                "configuration to prevent this warning."
            ),
            False,
            StaleRowError,
        ),
        # check_version's own error
        (StaleVersionError("Document is at version 2, not 1"), False, StaleRowError),
        # wording we can't read: keep the old, conservative answer
        (StaleDataError("something else went stale"), False, StaleRowError),
        # a versioned row deleted, or soft-deleted, since this request loaded it
        (
            StaleDataError(
                "UPDATE statement on table 'support_document' expected to update 1 row(s); "
                "0 were matched."
            ),
            True,
            NotFoundError,
        ),
    ],
)
def test_stale_row_is_a_version_conflict_only_on_a_versioned_row_still_there(
    error: StaleDataError, gone: bool, answer: type[Exception]
) -> None:
    assert type(stale_row_error(error, gone=gone)) is answer


@pytest.mark.anyio
async def test_catch_all_middleware_leaves_lifespan_errors_to_the_server() -> None:
    """A failure at startup or shutdown isn't an HTTP request: it must propagate as it is, not
    be answered with a 500 body on the lifespan channel."""
    sent: list[Message] = []

    async def failing_startup(_scope: Scope, _receive: Receive, _send: Send) -> None:
        raise RuntimeError("engine failed to start")

    async def receive() -> Message:
        return {"type": "lifespan.startup"}

    async def send(message: Message) -> None:
        sent.append(message)

    with pytest.raises(RuntimeError, match="engine failed to start"):
        await UnhandledErrorMiddleware(failing_startup)({"type": "lifespan"}, receive, send)

    assert sent == []
