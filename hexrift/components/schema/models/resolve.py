"""Node-level overlay resolution shared by schema validation and rendering."""

from __future__ import annotations

from typing import TYPE_CHECKING

from hexrift.components.schema.models.observability import MetricsConfig
from hexrift.components.schema.models.regions import WireguardConfig
from hexrift.constants import RegionType
from hexrift.errors import DeriveError


if TYPE_CHECKING:
    from hexrift.components.schema.models.defaults import DefaultsConfig
    from hexrift.components.schema.models.global_ import GlobalConfig
    from hexrift.components.schema.models.observability import MetricsOverride
    from hexrift.components.schema.models.regions import (
        Node,
        NodeWireguardOverride,
        Region,
        XdnsConfig,
    )


def resolve_node_proxy_inbound(node: Node, defaults: DefaultsConfig) -> bool:
    """Whether a hub node exposes the mixed proxy inbound."""

    if node.proxy_inbound is not None:
        return node.proxy_inbound
    return defaults.hub.proxy_inbound


def resolve_node_xdns(node: Node, defaults: DefaultsConfig) -> XdnsConfig | None:
    """Xdns config for a hub node, or None when it has none."""

    return node.xdns if node.xdns is not None else defaults.hub.xdns


def resolve_node_wireguard_port(node: Node, defaults: DefaultsConfig) -> int | None:
    """Wireguard port a hub node listens on, or None when wireguard is off for it."""

    override: NodeWireguardOverride | None = node.wireguard
    base: WireguardConfig | None = defaults.hub.wireguard
    if override is None:
        return base.port if base is not None else None
    if override.enabled is False:
        return None
    return override.port or (base.port if base is not None else 443)


def resolve_node_wireguard(node: Node, defaults: DefaultsConfig) -> WireguardConfig | None:
    """Wireguard config for a hub node after the node > defaults.hub overlay."""

    override: NodeWireguardOverride | None = node.wireguard
    base: WireguardConfig | None = defaults.hub.wireguard

    port = resolve_node_wireguard_port(node, defaults)
    if port is None:
        return None
    if override is None:
        return base

    subnet = override.subnet or (base.subnet if base else None)
    if subnet is None:
        raise DeriveError(f"Node {node.id!r}: wireguard.subnet must be set (no default configured)")

    return WireguardConfig(
        port=port,
        mtu=override.mtu or (base.mtu if base else 1420),
        subnet=subnet,
        keepalive=override.keepalive if override.keepalive is not None else (base.keepalive if base else 0),
        kernel_mode=override.kernel_mode if override.kernel_mode is not None else (base.kernel_mode if base else False),
    )


def overlay_metrics(base: MetricsConfig, override: MetricsOverride | None) -> MetricsConfig:
    """Apply one metrics override layer on top of a resolved metrics config."""

    if override is None:
        return base
    return MetricsConfig(
        enabled=override.enabled if override.enabled is not None else base.enabled,
        listen=override.listen if override.listen is not None else base.listen,
        port=override.port if override.port is not None else base.port,
        user_stats=override.user_stats if override.user_stats is not None else base.user_stats,
        online=override.online if override.online is not None else base.online,
    )


def resolve_node_metrics(
    node: Node,
    region: Region,
    defaults: DefaultsConfig,
    global_: GlobalConfig,
) -> MetricsConfig:
    """Resolve metrics config: node > defaults.<role> > global > built-in defaults."""

    role_defaults = defaults.exit if region.type == RegionType.EXIT else defaults.hub
    role_override = role_defaults.observability
    node_override = node.observability

    metrics = overlay_metrics(global_.observability.metrics, role_override.metrics if role_override else None)
    return overlay_metrics(metrics, node_override.metrics if node_override else None)
