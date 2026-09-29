"""Which stale rows are version conflicts (409) and which are rows that are gone (404)."""

import pytest
from sqlalchemy.orm.exc import StaleDataError

from app.core.base_model import StaleVersionError
from app.core.errors import is_version_conflict
from tests.support import (
    models,  # noqa: F401  # pyright: ignore[reportUnusedImport] -- registers the support tables
)


@pytest.mark.parametrize(
    ("error", "conflict"),
    [
        # SQLAlchemy's own wording, on a versioned and a non-versioned table
        (
            StaleDataError(
                "UPDATE statement on table 'support_document' expected to update 1 row(s); "
                "0 were matched."
            ),
            True,
        ),
        (
            StaleDataError(
                "UPDATE statement on table 'support_widget' expected to update 1 row(s); "
                "0 were matched."
            ),
            False,
        ),
        # a DELETE raises only on a versioned table (non-versioned ones just warn)
        (
            StaleDataError(
                "DELETE statement on table 'support_document' expected to delete 1 row(s); "
                "0 were matched.  Please set confirm_deleted_rows=False within the mapper "
                "configuration to prevent this warning."
            ),
            True,
        ),
        # check_version's own error
        (StaleVersionError("Document is at version 2, not 1"), True),
        # wording we can't read: keep the old, conservative answer
        (StaleDataError("something else went stale"), True),
    ],
)
def test_stale_row_is_a_version_conflict_only_on_a_versioned_table(
    error: StaleDataError, conflict: bool
) -> None:
    assert is_version_conflict(error) is conflict
