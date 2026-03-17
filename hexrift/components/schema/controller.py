from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import yaml
from pydantic import ValidationError

from hexrift.components.schema.models import ConglomerateConfig, Region
from hexrift.components.schema.models.regions import Node
from hexrift.constants import RegionType
from hexrift.core.controller import BaseController
from hexrift.errors import Error, SchemaValidationError


if TYPE_CHECKING:
    from hexrift.app import HexRiftApp  # noqa: F401


class SchemaController(BaseController["HexRiftApp"]):
    _config: ConglomerateConfig

    def load(self, path: Path) -> ConglomerateConfig:
        try:
            data = yaml.safe_load(path.read_text())
            self._config = ConglomerateConfig.model_validate(data)
        except (OSError, yaml.YAMLError) as e:
            raise Error(f"Failed to read schema {path}: {e}") from e
        except ValidationError as e:
            raise SchemaValidationError(path, e) from e
        return self._config

    @property
    def config(self) -> ConglomerateConfig:
        if getattr(self, "_config", None) is None:
            self.load(self.app.yaml_path)
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
        raise KeyError(f"Region not found: {region_id!r}")

    def get_node(self, node_id: str) -> tuple[Region, Node]:
        for region in self.config.regions:
            for node in region.nodes:
                if node.id == node_id:
                    return region, node
        raise KeyError(f"Node not found: {node_id!r}")
