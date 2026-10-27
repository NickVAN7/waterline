"""`scope_clause` refuses a content scope without the export-controlled expression: built without
it, the `WHERE` would reach export-controlled projects through inherited admin (design-doc §3.1)."""

import pytest

from app.authz.scoping import Scope
from app.models.project import Project
from app.repositories.base import scope_clause

pytestmark = pytest.mark.security


def test_a_content_scope_without_the_export_controlled_expression_is_refused() -> None:
    """Bug: the content flag silently ignored, so an org admin lists export-controlled content."""
    with pytest.raises(ValueError, match="needs the export_controlled expression"):
        scope_clause(Scope(everything=True, content=True), Project.id, Project.workspace_id)
