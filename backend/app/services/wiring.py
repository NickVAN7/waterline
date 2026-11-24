"""Imports every service module, so each area's module-level `register_on_*` call has run
before any request, command, or job (the handoff's Package 4 item 2). Imported by the app,
the CLI, and the worker; no service imports it (its own top layer in the import contract)."""

# pyright: reportUnusedImport=false
# ruff: noqa: F401 -- imported for their registrations, never used here

from app.services import (
    activity,
    approval,
    auth,
    health,
    my_work,
    numbering,
    org,
    project,
    project_members,
    requirement,
    requirement_approvals,
    roster,
    task,
    user,
    workspace,
)
