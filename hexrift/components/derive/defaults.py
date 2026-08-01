"""Merge per-node overrides on top of region defaults."""

from __future__ import annotations

from hexrift.components.schema.models.defaults import DefaultsConfig, ExitConnectionsConfig
from hexrift.components.schema.models.global_ import GlobalConfig
from hexrift.components.schema.models.observability import (
    LoggingConfig,
    LoggingOverride,
    ObservabilityConfig,
    ObservabilityOverride,
)
from hexrift.components.schema.models.regions import Node, Region
from hexrift.components.schema.models.resolve import resolve_node_metrics
from hexrift.components.schema.models.shared import RealityConfig
from hexrift.constants import RegionType
from hexrift.errors import DeriveError


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
            fallback_limits=dr.fallback_limits,
        )
    raise DeriveError(f"Exit node {node.id!r} must have a reality config")


def resolve_node_ipv6(node: Node, region: Region, defaults: DefaultsConfig) -> bool:
    if node.ipv6 is not None:
        return node.ipv6
    return defaults.exit.ipv6 if region.type == RegionType.EXIT else defaults.hub.ipv6


def resolve_node_haproxy(node: Node, region: Region, defaults: DefaultsConfig) -> bool:
    if node.haproxy is not None:
        return node.haproxy
    return defaults.exit.haproxy if region.type == RegionType.EXIT else defaults.hub.haproxy


def _overlay_logging(
    base: LoggingConfig,
    override: LoggingOverride | None,
) -> LoggingConfig:
    if override is None:
        return base
    return LoggingConfig(
        loglevel=override.loglevel if override.loglevel is not None else base.loglevel,
        access=override.access if override.access is not None else base.access,
        error=override.error if override.error is not None else base.error,
        dns_log=override.dns_log if override.dns_log is not None else base.dns_log,
    )


def resolve_node_observability(
    node: Node,
    region: Region,
    defaults: DefaultsConfig,
    global_: GlobalConfig,
) -> ObservabilityConfig:
    """Resolve observability config: node > defaults.<role> > global > built-in defaults."""

    role_defaults = defaults.exit if region.type == RegionType.EXIT else defaults.hub
    role_override: ObservabilityOverride | None = role_defaults.observability
    node_override: ObservabilityOverride | None = node.observability

    metrics = resolve_node_metrics(node, region, defaults, global_)

    logging = _overlay_logging(
        global_.observability.logging,
        role_override.logging if role_override else None,
    )
    logging = _overlay_logging(
        logging,
        node_override.logging if node_override else None,
    )

    return ObservabilityConfig(metrics=metrics, logging=logging)


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
            raise DeriveError(f"Malformed IPv6 address in dest (missing ']'): {dest!r}")
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
