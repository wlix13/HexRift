from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

import yaml
from pydantic import ValidationError

from hexrift.components.schema.models.regions import ExitRegion, HubRegion, NodePair, Region
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

    def get_exit_regions(self) -> list[ExitRegion]:
        return self.config.exit_regions

    def get_hub_regions(self) -> list[HubRegion]:
        return self.config.hub_regions

    def get_all_nodes(self) -> list[NodePair]:
        pairs: list[NodePair] = []
        for region in self.config.regions:
            # same body twice, ty narrows node type per branch only
            if region.type == RegionType.EXIT:
                pairs.extend((region, node) for node in region.nodes)
            else:
                pairs.extend((region, node) for node in region.nodes)
        return pairs

    def get_region(self, region_id: str) -> Region:
        for region in self.config.regions:
            if region.id == region_id:
                return region
        raise RegionError(f"Region not found: {region_id!r}")

    def get_node(self, node_id: str) -> NodePair:
        for pair in self.get_all_nodes():
            if pair[1].id == node_id:
                return pair
        raise NodeError(f"Node not found: {node_id!r}")
