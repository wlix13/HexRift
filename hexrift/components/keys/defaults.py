"""Resolve node's effective key configuration from per-node overrides and region defaults."""

from __future__ import annotations

from hexrift.components.schema.models.defaults import DefaultsConfig, KeysConfig
from hexrift.components.schema.models.regions import Node, Region
from hexrift.components.schema.models.resolve import resolve_node_keys_enabled
from hexrift.constants import RegionType


def resolve_node_keys(node: Node, region: Region, defaults: DefaultsConfig) -> KeysConfig:
    base = defaults.exit.keys if region.type == RegionType.EXIT else defaults.hub.keys
    if node.keys is None:
        return base
    return KeysConfig(
        enabled=resolve_node_keys_enabled(node, region, defaults),
        mode=node.keys.mode or base.mode,
        session_time=node.keys.session_time or base.session_time,
        auth=node.keys.auth or base.auth,
        padding=node.keys.padding if node.keys.padding is not None else base.padding,
    )
