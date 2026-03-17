from __future__ import annotations

from typing import ClassVar, Generic

import rich_click as click
from rich.console import Console

from hexrift.core.component import BaseComponent
from hexrift.core.types import ApplicationType


class BaseApplication(Generic[ApplicationType]):  # noqa: UP046
    """Application singleton — central registry and dependency injector."""

    default_components: ClassVar[list[type[BaseComponent]]] = []
    _instance: ClassVar[BaseApplication | None] = None

    def __init__(self) -> None:
        self.components: dict[str, BaseComponent] = {}
        self.console: Console = Console()
        type(self)._instance = self
        for component in self.default_components:
            self.register(component)

    @classmethod
    def current(cls) -> ApplicationType:
        if cls._instance is None:
            raise RuntimeError("No application instance exists yet.")
        return cls._instance  # ty:ignore[invalid-return-type]

    def register(self, component_cls: type[BaseComponent]) -> None:
        component = component_cls(self)
        self.components[component.name] = component
        if component.expose_controller:
            setattr(self, component.name, component.controller)
        component.on_register()

    @classmethod
    def register_cli(cls, group: click.Group) -> None:
        for component in cls.default_components:
            component.expose_cli(group)
