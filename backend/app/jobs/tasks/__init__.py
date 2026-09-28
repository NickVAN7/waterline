"""Job functions. Import every job module here so the worker registers it.

Only the worker imports this package (an import-linter contract enforces it).
"""

from app.jobs.tasks import ping

__all__ = ["ping"]
