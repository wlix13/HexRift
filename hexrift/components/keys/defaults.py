"""Resolve node's effective key configuration from per-node overrides and region defaults."""

from __future__ import annotations

from hexrift.components.schema.models.defaults import DefaultsConfig, KeysConfig
from hexrift.components.schema.models.regions import Node, Region
from hexrift.constants import RegionType


def resolve_node_keys(node: Node, region: Region, defaults: DefaultsConfig) -> KeysConfig:
    base = defaults.exit.keys if region.type == RegionType.EXIT else defaults.hub.keys
    if node.keys is None:
        return base
    return KeysConfig(
        enabled=node.keys.enabled if node.keys.enabled is not None else base.enabled,
        mode=node.keys.mode or base.mode,
        session_time=node.keys.session_time or base.session_time,
        auth=node.keys.auth or base.auth,
        padding=node.keys.padding if node.keys.padding is not None else base.padding,
    )
