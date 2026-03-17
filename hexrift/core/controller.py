from __future__ import annotations

from typing import Generic

from hexrift.core.types import ApplicationType


class BaseController(Generic[ApplicationType]):  # noqa: UP046
    """Base controller for business logic."""

    def __init__(self, app: ApplicationType) -> None:
        self.app = app
