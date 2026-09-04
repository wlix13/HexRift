from __future__ import annotations

from typing import Generic

import rich_click as click

from hexrift.core.types import ApplicationType, ControllerType


class BaseComponent(Generic[ApplicationType, ControllerType]):  # noqa: UP046
    """Base component — layer between CLI and Controller."""

    name: str
    controller_class: type[ControllerType]
    expose_controller: bool = True

    def __init__(self, app: ApplicationType) -> None:
        self.app = app
        self.controller: ControllerType = self.controller_class(app)

    @classmethod
    def expose_cli(cls, base: click.Group) -> None:
        """Register Click commands on base group."""

    @staticmethod
    def subgroup(base: click.Group, name: str) -> click.Group:
        """Group declared on `base` by the app, for commands several components contribute to."""

        group = base.commands[name]
        if not isinstance(group, click.Group):
            raise TypeError(f"{name!r} on {base.name!r} is not a group")
        return group

    def on_register(self) -> None:
        """Called after component is registered with application."""

    def on_deregister(self) -> None:
        """Called before component is deregistered from application."""
