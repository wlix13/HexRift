from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

import yaml
from pydantic import ValidationError

from hexrift.components.schema.models.regions import Node, Region
from hexrift.components.schema.models.root import ConglomerateConfig
from hexrift.constants import RegionType
from hexrift.core.controller import BaseController
from hexrift.errors import Error, NodeError, RegionError, SchemaValidationError


if TYPE_CHECKING:
    from hexrift.app import HexRiftApp


class SchemaController(BaseController["HexRiftApp"]):
    def __init__(self, app: HexRiftApp) -> None:
        super().__init__(app)
        self._config: ConglomerateConfig | None = None
        self._validators: list[Callable[[ConglomerateConfig], None]] = []

    def add_validator(self, validator: Callable[[ConglomerateConfig], None]) -> None:
        """Register a cross-component invariant checked on every load."""

        self._validators.append(validator)

    def load(self, path: Path) -> ConglomerateConfig:
        self._config = None
        try:
            data = yaml.safe_load(path.read_text())
            config = ConglomerateConfig.model_validate(data)
        except (OSError, yaml.YAMLError) as e:
            raise Error(f"Failed to read schema {path}: {e}") from e
        except ValidationError as e:
            raise SchemaValidationError(path, e) from e
        for validator in self._validators:
            validator(config)
        self._config = config
        return config

    @property
    def config(self) -> ConglomerateConfig:
        if self._config is None:
            return self.load(self.app.yaml_path)
        return self._config

    def get_exit_regions(self) -> list[Region]:
        return [r for r in self.config.regions if r.type == RegionType.EXIT]

    def get_hub_regions(self) -> list[Region]:
        return [r for r in self.config.regions if r.type == RegionType.HUB]

    def get_all_nodes(self) -> list[tuple[Region, Node]]:
        return [(region, node) for region in self.config.regions for node in region.nodes]

    def get_region(self, region_id: str) -> Region:
        for region in self.config.regions:
            if region.id == region_id:
                return region
        raise RegionError(f"Region not found: {region_id!r}")

    def get_node(self, node_id: str) -> tuple[Region, Node]:
        for region in self.config.regions:
            for node in region.nodes:
                if node.id == node_id:
                    return region, node
        raise NodeError(f"Node not found: {node_id!r}")
