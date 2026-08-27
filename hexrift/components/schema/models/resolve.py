"""Node-level overlay resolution shared by schema validation and rendering."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel

from hexrift.components.schema.models.observability import MetricsConfig
from hexrift.components.schema.models.regions import HysteriaConfig, WireguardConfig
from hexrift.constants import ExitProtocol, RegionType
from hexrift.errors import DeriveError


if TYPE_CHECKING:
    from hexrift.components.schema.models.defaults import DefaultsConfig
    from hexrift.components.schema.models.global_ import GlobalConfig
    from hexrift.components.schema.models.observability import MetricsOverride
    from hexrift.components.schema.models.regions import (
        HysteriaOverride,
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


def resolve_link_protocol(region: Region) -> ExitProtocol:
    """Protocol hubs use to dial an exit region."""

    return region.protocol if region.protocol is not None else ExitProtocol.VLESS


def overlay[T: BaseModel](base: T, override: BaseModel | None) -> T:
    if override is None:
        return base
    values = {}
    for name in type(base).model_fields:
        value = getattr(override, name, None)
        values[name] = value if value is not None else getattr(base, name)
    return type(base)(**values)


def overlay_hysteria(base: HysteriaConfig, override: HysteriaOverride | None) -> HysteriaConfig:
    """Apply one hysteria override layer on top of a resolved hysteria config."""

    return overlay(base, override)


def resolve_hysteria_overlay(node: Node, region: Region, defaults: DefaultsConfig) -> HysteriaConfig:
    """Fully overlaid hysteria config for a node, whether or not it renders a listener."""

    if region.type == RegionType.EXIT:
        base = defaults.exit.hysteria or HysteriaConfig()
        return overlay_hysteria(overlay_hysteria(base, region.hysteria), node.hysteria)
    return overlay_hysteria(defaults.hub.hysteria or HysteriaConfig(), node.hysteria)


def resolve_node_hysteria(node: Node, region: Region, defaults: DefaultsConfig) -> HysteriaConfig | None:
    """Hysteria listener config for a node, or None when it renders none."""

    if region.type == RegionType.EXIT:
        listens = (
            region.hysteria is not None
            or node.hysteria is not None
            or resolve_link_protocol(region) == ExitProtocol.HYSTERIA
        )
        if not listens:
            return None
        return resolve_hysteria_overlay(node, region, defaults)

    if node.hysteria is None:
        return defaults.hub.hysteria
    if node.hysteria.enabled is False:
        return None
    return resolve_hysteria_overlay(node, region, defaults)


def overlay_metrics(base: MetricsConfig, override: MetricsOverride | None) -> MetricsConfig:
    """Apply one metrics override layer on top of a resolved metrics config."""

    return overlay(base, override)


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
