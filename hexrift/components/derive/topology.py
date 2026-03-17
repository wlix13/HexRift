"""Topology resolution — build client lists, outbounds, balancers, routing rules."""

from hexrift.components.derive.identity import Namespace
from hexrift.components.schema.models.regions import Node, Region
from hexrift.components.schema.models.root import ConglomerateConfig
from hexrift.components.schema.models.users import User
from hexrift.constants import VLESS_FLOW, AccessType, LbRole, RegionType, SpecialDestination, TagPrefix, TagSuffix


def _build_exit_clients(
    hub_nodes: list[Node],
    exit_node: Node,
    ns: Namespace,
    flow: str,
) -> list[dict]:
    return [
        {
            "email": ns.hub_exit_email(hub.id, exit_node.id),
            "id": str(ns.hub_exit_uuid(hub.id, exit_node.id)),
            "flow": flow,
        }
        for hub in hub_nodes
    ]


def get_exit_direct_clients(
    hub_nodes: list[Node],
    exit_node: Node,
    ns: Namespace,
    flow: str = VLESS_FLOW,
) -> list[dict]:
    """Clients for exit direct-xhttp inbound."""

    return _build_exit_clients(hub_nodes, exit_node, ns, flow)


def get_exit_cdn_clients(
    hub_nodes: list[Node],
    exit_node: Node,
    ns: Namespace,
    flow: str = VLESS_FLOW,
) -> list[dict]:
    """Clients for exit cdn-xhttp inbound."""

    return _build_exit_clients(hub_nodes, exit_node, ns, flow)


def get_hub_vless_clients(
    users: list[User],
    ns: Namespace,
    flow: str = VLESS_FLOW,
) -> list[dict]:
    """Clients for hub vless-xhttp inbound: xhttp users + servers + portal clients."""

    clients = []
    for user in users:
        user_base = ns.user_uuid(user.username, override=user.uuid)
        if AccessType.XHTTP in user.access:
            clients.append(
                {
                    "email": ns.user_email(user.username),
                    "id": str(user_base),
                    "flow": flow,
                }
            )
        if AccessType.SERVER in user.access:
            clients.append(
                {
                    "email": ns.server_email(user.username),
                    "id": str(ns.server_uuid(user.username, user_base=user_base)),
                    "flow": flow,
                }
            )
        if user.guests and AccessType.XHTTP in user.access:
            for label in user.guests:
                clients.append(
                    {
                        "email": ns.guest_email(label, user.username),
                        "id": str(ns.guest_uuid(label, user.username, user_base=user_base)),
                        "flow": flow,
                    }
                )
    for user in users:
        if user.portals:
            user_base = ns.user_uuid(user.username, override=user.uuid)
            for portal in user.portals:
                clients.append(
                    {
                        "email": ns.portal_email(portal.label, user.username),
                        "id": str(ns.portal_uuid(portal.label, user.username, user_base=user_base)),
                        "flow": flow,
                    }
                )
    return clients


def get_hub_cdn_clients(
    users: list[User],
    ns: Namespace,
    flow: str = VLESS_FLOW,
) -> list[dict]:
    """Clients for hub cdn-xhttp inbound."""

    clients = []
    for u in users:
        if AccessType.CDN not in u.access:
            continue
        user_base = ns.user_uuid(u.username, override=u.uuid)
        clients.append({"id": str(user_base), "email": ns.user_email(u.username), "flow": flow})
        for label in u.guests:
            clients.append(
                {
                    "id": str(ns.guest_uuid(label, u.username, user_base=user_base)),
                    "email": ns.guest_email(label, u.username),
                    "flow": flow,
                }
            )
    return clients


def get_hub_short_ids(groups: list, ns: Namespace) -> list[str]:
    """Hub node shortIds = group shortIds only (identical across all hub nodes in the region)."""

    return [ns.group_short_id(group) for group in groups]


def get_exit_short_id(node: Node, ns: Namespace) -> str:
    """Exit node gets a single shortId."""

    return ns.exit_short_id(node.id)


def _resolve_fallback_tag(region: Region) -> str:
    if not region.nodes:
        raise ValueError(f"Region {region.id!r} has no nodes")
    if region.lb_fallback is None:
        # first primary node as fallback
        primary = [n for n in region.nodes if n.lb_role != LbRole.BACKUP]
        return primary[0].id if primary else region.nodes[0].id
    fb_node = next((n for n in region.nodes if n.id == region.lb_fallback), None)
    # if fallback node has backup role
    if fb_node and fb_node.lb_role == LbRole.BACKUP:
        return f"{TagPrefix.BACKUP}{region.lb_fallback}"
    return region.lb_fallback


def build_balancers(exit_regions: list[Region]) -> list[dict]:
    """Build lb-{region} balancers (and lb-warp-{region} for warp-enabled regions) with lb_strategy."""

    balancers = []
    for region in exit_regions:
        if region.lb_strategy is None:
            continue
        fb_tag = _resolve_fallback_tag(region)
        balancers.append(
            {
                "tag": f"{TagPrefix.LB}{region.id}",
                "selector": [region.id],
                "fallbackTag": fb_tag,
                "strategy": {"type": region.lb_strategy},
            }
        )
        if region.warp is not None:
            warp_fb = f"{TagPrefix.WARP}{fb_tag}"
            balancers.append(
                {
                    "tag": f"{TagPrefix.LB_WARP}{region.id}",
                    "selector": [f"{TagPrefix.WARP}{region.id}"],
                    "fallbackTag": warp_fb,
                    "strategy": {"type": region.lb_strategy},
                }
            )
    return balancers


def region_outbound_tag(region: Region) -> str:
    """Tag for routing to region: balancer tag or single node id."""

    if region.lb_strategy is not None:
        return f"{TagPrefix.LB}{region.id}"
    if not region.nodes:
        raise ValueError(f"Region {region.id!r} has no nodes")
    primary = [n for n in region.nodes if n.lb_role != LbRole.BACKUP]
    return primary[0].id if primary else region.nodes[0].id


def region_warp_outbound_tag(region: Region) -> str:
    if region.lb_strategy is not None:
        return f"{TagPrefix.LB_WARP}{region.id}"
    if not region.nodes:
        raise ValueError(f"Region {region.id!r} has no nodes")
    primary = [n for n in region.nodes if n.lb_role != LbRole.BACKUP]
    node = primary[0] if primary else region.nodes[0]
    return f"{TagPrefix.WARP}{node.id}"


def _balancer_key(region: Region) -> str:
    return "balancerTag" if region.lb_strategy is not None else "outboundTag"


def build_hub_routing_rules(config: ConglomerateConfig) -> list[dict]:
    """Build ordered routing rule list for hub node."""

    ns = Namespace(config.global_.namespace)
    routing = config.routing
    exit_regions = [r for r in config.regions if r.type == RegionType.EXIT]
    region_map = {r.id: r for r in config.regions}
    node_map = {n.id: (r, n) for r in config.regions for n in r.nodes}
    users = config.users

    default_region = region_map[routing.hub_default]
    rules: list[dict] = []

    # 1. DNS localhost
    rules.append(
        {
            "ip": ["127.0.0.1", "::1"],
            "port": 53,
            "outboundTag": SpecialDestination.DIRECT,
        }
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
        if route.destination == SpecialDestination.BLOCKED and route.domains:
            rules.append(
                {
                    "domain": route.domains,
                    "outboundTag": SpecialDestination.BLOCKED,
                }
            )

    # 5 & 6. Portal domain + IP routes (per user, with user filter)
    for user in users:
        if not user.portals:
            continue
        u_email = ns.user_email(user.username)
        for portal in user.portals:
            portal_tag = f"{portal.label}{TagSuffix.PORTAL}"
            if portal.routes.domains:
                rules.append(
                    {
                        "domain": portal.routes.domains,
                        "user": [u_email],
                        "outboundTag": portal_tag,
                    }
                )
            if portal.routes.ips:
                rules.append(
                    {
                        "ip": portal.routes.ips,
                        "user": [u_email],
                        "outboundTag": portal_tag,
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
        if route.domains:
            rules.append(
                {
                    "domain": route.domains,
                    out_key: out_tag,
                }
            )
        if route.ips:
            rules.append(
                {
                    "ip": route.ips,
                    out_key: out_tag,
                }
            )

    # 8 & 9. Direct domain + IP routes
    for route in routing.hub_routes:
        if route.destination != SpecialDestination.DIRECT:
            continue
        if route.domains:
            rules.append(
                {
                    "domain": route.domains,
                    "outboundTag": SpecialDestination.DIRECT,
                }
            )
        if route.ips:
            rules.append(
                {
                    "ip": route.ips,
                    "outboundTag": SpecialDestination.DIRECT,
                }
            )

    # 10. Blocked IP rules
    for route in routing.hub_routes:
        if route.destination == SpecialDestination.BLOCKED and route.ips:
            rules.append(
                {
                    "ip": route.ips,
                    "outboundTag": SpecialDestination.BLOCKED,
                }
            )

    # 11. Portal catch-all (user → portal outbound)
    for user in users:
        if not user.portals:
            continue
        for portal in user.portals:
            rules.append(
                {
                    "user": [ns.portal_email(portal.label, user.username)],
                    "outboundTag": f"{portal.label}{TagSuffix.PORTAL}",
                }
            )

    # 12. Default fallthrough
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
