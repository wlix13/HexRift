"""Merge per-node overrides on top of region defaults."""

from hexrift.components.schema.models.defaults import DefaultsConfig, ExitConnectionsConfig, KeysConfig
from hexrift.components.schema.models.regions import Node, Region
from hexrift.components.schema.models.shared import RealityConfig
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


def resolve_node_reality(node: Node, region: Region, defaults: DefaultsConfig) -> RealityConfig:
    if node.reality is not None:
        return node.reality
    if region.type == RegionType.HUB:
        dr = defaults.hub.reality
        return RealityConfig(
            dest=dr.dest,
            server_names=dr.server_names,
            xhttp_host=dr.xhttp_host,
            xhttp_path=dr.xhttp_path,
        )
    raise ValueError(f"Exit node {node.id!r} must have a reality config")


def resolve_node_ipv6(node: Node, region: Region, defaults: DefaultsConfig) -> bool:
    if node.ipv6 is not None:
        return node.ipv6
    return defaults.exit.ipv6 if region.type == RegionType.EXIT else defaults.hub.ipv6


def resolve_node_proxy_inbound(node: Node, defaults: DefaultsConfig) -> bool:
    if node.proxy_inbound is not None:
        return node.proxy_inbound
    return defaults.hub.proxy_inbound


def resolve_exit_connections(node: Node, defaults: DefaultsConfig) -> ExitConnectionsConfig:
    base = defaults.hub.exit_connections
    if node.exit_connections is None:
        return base
    return ExitConnectionsConfig(
        method=node.exit_connections.method or base.method,
        fingerprint=node.exit_connections.fingerprint or base.fingerprint,
    )


def _extract_host(dest: str) -> str:
    """Extract host from dest, handling IPv6 bracketed literals and port suffixes."""

    if dest.startswith("["):
        close = dest.find("]")
        if close == -1:
            raise ValueError(f"Malformed IPv6 address in dest (missing ']'): {dest!r}")
        return dest[1:close]
    return dest.rsplit(":", 1)[0]


def derive_server_names(reality: RealityConfig) -> list[str]:
    if reality.server_names is not None:
        return reality.server_names
    return [_extract_host(reality.dest)]


def derive_xhttp_host(reality: RealityConfig) -> str:
    if reality.xhttp_host is not None:
        return reality.xhttp_host
    return _extract_host(reality.dest)
