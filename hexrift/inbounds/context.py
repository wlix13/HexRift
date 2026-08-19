"""Per-node contexts: shared data, inbound slots, and hub data."""

from __future__ import annotations

from dataclasses import dataclass

from hexrift.components.derive.defaults import (
    resolve_exit_connections,
    resolve_node_haproxy,
    resolve_node_ipv6,
    resolve_node_observability,
)
from hexrift.components.derive.topology import (
    build_balancers,
    build_burst_observatory_selectors,
    build_hub_routing_rules,
    resolve_node_publishes,
)
from hexrift.components.keys.store import NodeKeys
from hexrift.components.schema.models.defaults import ObservatoryConfig
from hexrift.components.schema.models.regions import Node, Region
from hexrift.components.schema.models.root import ConglomerateConfig
from hexrift.constants import AccessType, LbRole, RegionType, TagPrefix
from hexrift.inbounds.base import InboundContext, InboundEnv, SharedContext
from hexrift.inbounds.forward import forward_fragment
from hexrift.inbounds.registry import build_slots
from hexrift.links.base import LinkContext, LinkEnv
from hexrift.links.registry import build_link


@dataclass(frozen=True)
class ExitContext:
    shared: SharedContext
    slots: dict[AccessType, InboundContext]

    # Routing
    warp_domains: list[str]  # region warp_extra + exit_warp_global (domain-based warp routing)
    extra_routes: list[dict]  # from region routes + global_exit_routes


@dataclass(frozen=True)
class HubContext:
    shared: SharedContext
    slots: dict[AccessType, InboundContext]
    forward_inbounds: list[dict]  # dokodemo-door fragments, one per published portal port

    # Outbounds
    outbounds: list[LinkContext]  # one per exit node (normal)
    warp_outbounds: list[LinkContext]  # one per exit node (warp variant)

    # Routing / balancers
    balancers: list[dict]
    routing_rules: list[dict]
    observatory_selectors: list[str]

    # Observatory config
    observatory: ObservatoryConfig


def _make_shared(config: ConglomerateConfig, region: Region, node: Node, node_keys: NodeKeys) -> SharedContext:
    return SharedContext(
        node_id=node.id,
        hostname=node.hostname,
        ipv6=resolve_node_ipv6(node, region, config.defaults),
        decryption=node_keys.decryption,
        dns_address=config.global_.dns.address,
        dns_port=config.global_.dns.port,
        trusted_forwarded_headers=config.global_.cdn.trusted_forwarded_headers if config.global_.cdn else [],
        haproxy=resolve_node_haproxy(node, region, config.defaults),
        route_only=region.type != RegionType.EXIT,
        observability=resolve_node_observability(node, region, config.defaults, config.global_),
    )


def build_exit_context(
    config: ConglomerateConfig,
    region: Region,
    node: Node,
    node_keys: NodeKeys,
) -> ExitContext:
    env = InboundEnv(config, region, node, node_keys)

    # warp_domains: domain-based warp routing on exit
    warp_domains: list[str] = []
    if region.routing and region.routing.warp_extra:
        warp_domains.extend(region.routing.warp_extra)
    warp_domains.extend(config.routing.exit_warp_global)

    # extra_routes: region-specific routes first, then global exit routes (both applied additively)
    extra_routes: list[dict] = []
    all_exit_routes = (region.routing.routes or [] if region.routing else []) + config.routing.exit_routes_global
    for route in all_exit_routes:
        if route.domains:
            extra_routes.append(
                {
                    "domain": route.domains,
                    "outboundTag": route.destination,
                }
            )
        if route.ips:
            extra_routes.append(
                {
                    "ip": route.ips,
                    "outboundTag": route.destination,
                }
            )

    return ExitContext(
        shared=_make_shared(config, region, node, node_keys),
        slots=build_slots(env),
        warp_domains=warp_domains,
        extra_routes=extra_routes,
    )


def build_hub_context(
    config: ConglomerateConfig,
    region: Region,
    node: Node,
    node_keys: NodeKeys,
    exit_node_keys: dict[str, NodeKeys],  # {exitNodeId: NodeKeys}
) -> HubContext:
    env = InboundEnv(config, region, node, node_keys)
    shared = _make_shared(config, region, node, node_keys)
    ns = env.ns

    # Build exit outbounds
    exit_regions = [r for r in config.regions if r.type == RegionType.EXIT]

    ec = resolve_exit_connections(node, config.defaults)
    outbounds: list[LinkContext] = []
    warp_outbounds: list[LinkContext] = []

    for exit_region in exit_regions:
        warp_vless_route = exit_region.warp.vless_route if exit_region.warp else None
        for exit_node in exit_region.nodes:
            link = LinkEnv(
                config=config,
                hub=node,
                exit_region=exit_region,
                exit_node=exit_node,
                exit_keys=exit_node_keys[exit_node.id],
                ns=ns,
                exit_connections=ec,
            )
            uid = ns.hub_exit_uuid(node.id, exit_node.id)
            tag_prefix = TagPrefix.BACKUP if exit_node.lb_role == LbRole.BACKUP else TagPrefix.NONE
            outbounds.append(build_link(link, str(uid), tag_prefix))
            if warp_vless_route is not None:
                warp_outbounds.append(build_link(link, str(ns.warp_uuid(uid)), TagPrefix.WARP + tag_prefix))

    published = resolve_node_publishes(config, node)

    return HubContext(
        shared=shared,
        slots=build_slots(env),
        forward_inbounds=[forward_fragment(pub, shared) for pub in published],
        outbounds=outbounds,
        warp_outbounds=warp_outbounds,
        balancers=build_balancers(exit_regions),
        routing_rules=build_hub_routing_rules(config, published),
        observatory_selectors=build_burst_observatory_selectors(exit_regions),
        observatory=config.defaults.hub.observatory,
    )
