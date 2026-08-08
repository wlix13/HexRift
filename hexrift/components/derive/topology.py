"""Topology resolution — build client lists, outbounds, balancers, routing rules."""

from __future__ import annotations

from dataclasses import dataclass

from hexrift.components.derive.identity import Namespace
from hexrift.components.schema.models.regions import LeastLoadSettings, Node, Region
from hexrift.components.schema.models.root import ConglomerateConfig
from hexrift.components.schema.models.routing import HubRoute
from hexrift.constants import (
    SPECIAL_DESTINATIONS,
    LbRole,
    LbStrategy,
    PublishNetwork,
    RegionType,
    SpecialDestination,
    TagPrefix,
    TagSuffix,
)
from hexrift.errors import DeriveError
from hexrift.shared.xray_defaults import make_dns_direct_rule


def portal_tag(portal_id: str) -> str:
    """Get outbound tag for portal."""

    return f"{portal_id}{TagSuffix.PORTAL}"


def publish_tag(portal_id: str, port: int) -> str:
    return f"{portal_id}{TagSuffix.PUBLISH}-{port}"


@dataclass(frozen=True)
class PublishedPort:
    """One portal published port resolved by single hub node."""

    tag: str
    reverse_tag: str
    port: int
    target_host: str
    target_port: int
    network: PublishNetwork
    allow: list[str]


def resolve_node_publishes(config: ConglomerateConfig, node: Node) -> list[PublishedPort]:
    """Published ports resolved by single hub node, in portal then declaration order."""

    resolved: list[PublishedPort] = []
    for portal in config.portals:
        reverse_tag = portal_tag(portal.id)
        for entry in portal.publish:
            if entry.nodes is not None and node.id not in entry.nodes:
                continue
            target_host, target_port = entry.target_host_port
            resolved.append(
                PublishedPort(
                    tag=publish_tag(portal.id, entry.port),
                    reverse_tag=reverse_tag,
                    port=entry.port,
                    target_host=target_host,
                    target_port=target_port,
                    network=entry.network,
                    allow=list(entry.allow) if entry.allow else [],
                )
            )
    return resolved


def build_publish_rules(published: list[PublishedPort]) -> list[dict]:
    """Build inboundTag-keyed rules steering published ports into portal tunnel."""

    rules: list[dict] = []
    for pub in published:
        rule: dict = {"inboundTag": [pub.tag]}
        if pub.allow:
            rule["source"] = pub.allow
        rule["outboundTag"] = pub.reverse_tag
        rules.append(rule)
        if pub.allow:
            # Deny anything the allowlist did not match; without it the port is open
            rules.append(
                {
                    "inboundTag": [pub.tag],
                    "outboundTag": SpecialDestination.BLOCKED,
                }
            )
    return rules


def _resolve_fallback_tag(region: Region) -> str:
    if not region.nodes:
        raise DeriveError(f"Region {region.id!r} has no nodes")
    if region.lb_fallback is None:
        # first primary node as fallback
        primary = [n for n in region.nodes if n.lb_role != LbRole.BACKUP]
        return primary[0].id if primary else region.nodes[0].id
    fb_node = next((n for n in region.nodes if n.id == region.lb_fallback), None)
    # if fallback node has backup role
    if fb_node and fb_node.lb_role == LbRole.BACKUP:
        return f"{TagPrefix.BACKUP}{region.lb_fallback}"
    return region.lb_fallback


def _build_strategy(region: Region) -> dict:
    """Build strategy for balancer with leastLoad settings when applicable."""

    strategy: dict = {"type": region.lb_strategy}
    if region.lb_strategy == LbStrategy.LEAST_LOAD:
        s = region.lb_least_load or LeastLoadSettings()
        strategy["settings"] = s.xray_settings
    return strategy


def build_balancers(exit_regions: list[Region]) -> list[dict]:
    """Build lb-{region} balancers (and lb-warp-{region} for warp-enabled regions) with lb_strategy."""

    balancers = []
    for region in exit_regions:
        if region.lb_strategy is None:
            continue
        fb_tag = _resolve_fallback_tag(region)
        strategy = _build_strategy(region)
        balancers.append(
            {
                "tag": f"{TagPrefix.LB}{region.id}",
                "selector": [region.id],
                "fallbackTag": fb_tag,
                "strategy": strategy,
            }
        )
        if region.warp is not None:
            warp_fb = f"{TagPrefix.WARP}{fb_tag}"
            balancers.append(
                {
                    "tag": f"{TagPrefix.LB_WARP}{region.id}",
                    "selector": [f"{TagPrefix.WARP}{region.id}"],
                    "fallbackTag": warp_fb,
                    "strategy": strategy,
                }
            )
    return balancers


def region_outbound_tag(region: Region) -> str:
    """Tag for routing to region: balancer tag or single node id."""

    if region.lb_strategy is not None:
        return f"{TagPrefix.LB}{region.id}"
    if not region.nodes:
        raise DeriveError(f"Region {region.id!r} has no nodes")
    primary = [n for n in region.nodes if n.lb_role != LbRole.BACKUP]
    return primary[0].id if primary else region.nodes[0].id


def region_warp_outbound_tag(region: Region) -> str:
    if region.lb_strategy is not None:
        return f"{TagPrefix.LB_WARP}{region.id}"
    if not region.nodes:
        raise DeriveError(f"Region {region.id!r} has no nodes")
    primary = [n for n in region.nodes if n.lb_role != LbRole.BACKUP]
    node = primary[0] if primary else region.nodes[0]
    return f"{TagPrefix.WARP}{node.id}"


def _balancer_key(region: Region) -> str:
    return "balancerTag" if region.lb_strategy is not None else "outboundTag"


def _route_user_filter(route: HubRoute, ns: Namespace) -> dict:
    emails = []
    if route.users:
        emails.extend(ns.user_email(u) for u in route.users)
    if route.proxy_users:
        emails.extend(route.proxy_users)
    return {"user": emails} if emails else {}


def _append_route_rules(
    rules: list[dict],
    route: HubRoute,
    uf: dict,
    out_key: str,
    out_tag: str,
    *,
    include_ips: bool = True,
) -> None:
    """Append route's domain / ip / bare-user-filter rules pointing at one outbound."""

    if route.domains:
        rules.append(
            {
                "domain": route.domains,
                **uf,
                out_key: out_tag,
            }
        )
    if include_ips and route.ips:
        rules.append(
            {
                "ip": route.ips,
                **uf,
                out_key: out_tag,
            }
        )
    if not route.domains and not route.ips and uf:
        rules.append(
            {
                **uf,
                out_key: out_tag,
            }
        )


def build_hub_routing_rules(config: ConglomerateConfig, published: list[PublishedPort]) -> list[dict]:
    """Build ordered routing rule list for hub node."""

    ns = Namespace(config.global_.namespace)
    routing = config.routing
    exit_regions = [r for r in config.regions if r.type == RegionType.EXIT]
    region_map = {r.id: r for r in config.regions}
    node_map = {n.id: (r, n) for r in config.regions for n in r.nodes}

    # 0. Published ports: ahead of every other rule so none can re-steer published connections
    rules: list[dict] = build_publish_rules(published)

    # 1. DNS localhost
    rules.append(
        make_dns_direct_rule(
            config.global_.dns.address,
            config.global_.dns.port,
        )
    )
    # 2. vlessRoute per exit region
    for region in exit_regions:
        tag_key = _balancer_key(region)
        tag_val = region_outbound_tag(region)
        rules.append(
            {
                "vlessRoute": str(region.vless_route),
                tag_key: tag_val,
            }
        )

    # 3. vlessRoute per warp-enabled exit region
    for region in exit_regions:
        if region.warp is None:
            continue
        warp_key = _balancer_key(region)
        warp_tag = region_warp_outbound_tag(region)
        rules.append({"vlessRoute": str(region.warp.vless_route), warp_key: warp_tag})

    # 4. Blocked domain rules
    for route in routing.hub_routes:
        if route.destination != SpecialDestination.BLOCKED:
            continue
        uf = _route_user_filter(route, ns)
        _append_route_rules(
            rules,
            route,
            uf,
            "outboundTag",
            SpecialDestination.BLOCKED,
            include_ips=False,
        )

    # 5 & 6. Portal domain + IP routes (filtered to each portal's member users)
    for portal in config.portals:
        uf = {"user": [ns.user_email(u) for u in portal.users]}
        pt = portal_tag(portal.id)
        if portal.routes.domains:
            rules.append(
                {
                    "domain": portal.routes.domains,
                    **uf,
                    "outboundTag": pt,
                }
            )
        if portal.routes.ips:
            rules.append(
                {
                    "ip": portal.routes.ips,
                    **uf,
                    "outboundTag": pt,
                }
            )

    # 7. hub_routes (non-blocked, non-direct, non-warp-only)
    for route in routing.hub_routes:
        if route.destination in (SpecialDestination.BLOCKED, SpecialDestination.DIRECT):
            continue
        dest = route.destination
        if dest == SpecialDestination.WARP:
            out_tag = SpecialDestination.WARP
            out_key = "outboundTag"
        elif dest in region_map:
            r = region_map[dest]
            out_tag = region_outbound_tag(r)
            out_key = _balancer_key(r)
        elif dest in node_map:
            out_tag = dest
            out_key = "outboundTag"
        else:
            continue  # Validated earlier; shouldn't happen
        uf = _route_user_filter(route, ns)
        _append_route_rules(rules, route, uf, out_key, out_tag)

    # 8 & 9. Direct domain + IP routes
    for route in routing.hub_routes:
        if route.destination != SpecialDestination.DIRECT:
            continue
        uf = _route_user_filter(route, ns)
        _append_route_rules(rules, route, uf, "outboundTag", SpecialDestination.DIRECT)

    # 10. Blocked IP rules
    for route in routing.hub_routes:
        if route.destination != SpecialDestination.BLOCKED or not route.ips:
            continue
        uf = _route_user_filter(route, ns)
        rules.append(
            {
                "ip": route.ips,
                **uf,
                "outboundTag": SpecialDestination.BLOCKED,
            }
        )

    # 11. Default fallthrough: region or special destination
    if routing.hub_default in SPECIAL_DESTINATIONS:
        rules.append(
            {
                "network": "TCP,UDP",
                "outboundTag": routing.hub_default,
            }
        )
    else:
        default_region = region_map[routing.hub_default]
        def_tag = region_outbound_tag(default_region)
        def_key = _balancer_key(default_region)
        rules.append(
            {
                "network": "TCP,UDP",
                def_key: def_tag,
            }
        )

    return rules


def build_burst_observatory_selectors(exit_regions: list[Region]) -> list[str]:
    """Selectors for burstObservatory: all regions with LB + warp variants for warp-enabled."""

    selectors: list[str] = []
    for region in exit_regions:
        if region.lb_strategy is not None:
            selectors.append(region.id)
            if region.warp is not None:
                selectors.append(f"{TagPrefix.WARP}{region.id}")
    return selectors
