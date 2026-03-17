from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar


if TYPE_CHECKING:
    from hexrift.core.application import BaseApplication
    from hexrift.core.controller import BaseController
    from hexrift.core.model import BaseModel

ApplicationType = TypeVar("ApplicationType", bound="BaseApplication")
ControllerType = TypeVar("ControllerType", bound="BaseController")
ModelType = TypeVar("ModelType", bound="BaseModel")
