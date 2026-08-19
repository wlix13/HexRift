from pydantic import BaseModel, ConfigDict, Field, model_validator

from hexrift.components.schema.models.defaults import DefaultsConfig
from hexrift.components.schema.models.global_ import GlobalConfig
from hexrift.components.schema.models.groups import Group
from hexrift.components.schema.models.portals import Portal
from hexrift.components.schema.models.regions import HysteriaConfig, HysteriaOverride, Node, Region
from hexrift.components.schema.models.resolve import (
    resolve_node_hysteria,
    resolve_node_metrics,
    resolve_node_proxy_inbound,
    resolve_node_wireguard_port,
    resolve_node_xdns,
)
from hexrift.components.schema.models.routing import RoutingConfig
from hexrift.components.schema.models.users import User
from hexrift.constants import (
    PROXY_INBOUND_PORT,
    REALITY_INBOUND_PORT,
    ROUTABLE_ACCESS,
    SPECIAL_DESTINATIONS,
    AccessType,
    HysteriaCongestion,
    RegionType,
    TagPrefix,
    TagSuffix,
    Transport,
)


def _hub_rendered_access(
    region: Region,
    node: Node,
    defaults: DefaultsConfig,
    global_: GlobalConfig,
) -> set[AccessType]:
    """Routable access types whose inbound this hub node actually renders."""

    rendered = {AccessType.XHTTP}
    if global_.cdn is not None and region.cdn_xhttp_path:
        rendered.add(AccessType.CDN)
    if resolve_node_xdns(node, defaults) is not None:
        rendered.add(AccessType.XDNS)
    if resolve_node_wireguard_port(node, defaults) is not None:
        rendered.add(AccessType.WIREGUARD)
    if resolve_node_hysteria(node, region, defaults) is not None:
        rendered.add(AccessType.HYSTERIA)
    return rendered


def _validate_hysteria(owner: str, hy: HysteriaConfig) -> None:
    """Cross-field checks that only hold on the fully overlaid hysteria config."""

    if hy.congestion == HysteriaCongestion.BRUTAL and (hy.up is None or hy.down is None):
        raise ValueError(f"{owner}: hysteria congestion 'brutal' requires both up and down bandwidth")
    if hy.certificate is not None and hy.sni is None:
        raise ValueError(f"{owner}: hysteria certificate requires an explicit sni matching it")


def _reject_hub_only_enabled(owner: str, hysteria: HysteriaOverride | None) -> None:
    if hysteria is not None and hysteria.enabled is not None:
        raise ValueError(f"{owner}: hysteria.enabled is hub-only; set the exit region's protocol instead")


def _node_reserved_ports(
    region: Region,
    node: Node,
    defaults: DefaultsConfig,
    global_: GlobalConfig,
    users: list[User],
) -> dict[tuple[int, Transport], str]:
    """Sockets bound by a node, mapped to what binds them; rejects two inbounds on one socket."""

    reserved: dict[tuple[int, Transport], str] = {}

    def reserve(port: int, transport: Transport, owner: str) -> None:
        key = (port, transport)
        if key in reserved:
            raise ValueError(f"Node {node.id!r}: {owner} and {reserved[key]} both bind {transport} port {port}")
        reserved[key] = owner

    reserve(REALITY_INBOUND_PORT, Transport.TCP, "the reality inbound")

    hysteria = resolve_node_hysteria(node, region, defaults)
    if region.type == RegionType.EXIT:
        if hysteria is not None:
            reserve(hysteria.port, Transport.UDP, "the hysteria inbound")
    else:
        if resolve_node_proxy_inbound(node, defaults):
            reserve(PROXY_INBOUND_PORT, Transport.TCP, "the proxy inbound")

        xdns = resolve_node_xdns(node, defaults)
        if xdns is not None and any(AccessType.XDNS in u.access for u in users):
            reserve(xdns.port, Transport.UDP, "the xdns inbound")

        wireguard_port = resolve_node_wireguard_port(node, defaults)
        if wireguard_port is not None and any(AccessType.WIREGUARD in u.access for u in users):
            reserve(wireguard_port, Transport.UDP, "the wireguard inbound")

        if hysteria is not None and any(AccessType.HYSTERIA in u.access for u in users):
            reserve(hysteria.port, Transport.UDP, "the hysteria inbound")

    metrics = resolve_node_metrics(node, region, defaults, global_)
    if metrics.enabled:
        reserve(metrics.port, Transport.TCP, "the metrics api listener")

    return reserved


def _validate_portal_publish(
    portal: Portal,
    node_ids: set[str],
    hub_nodes: dict[str, tuple[Region, Node]],
    reserved_ports: dict[str, dict[tuple[int, Transport], str]],
    published_ports: dict[tuple[str, int], str],
) -> None:
    """Check one portal's published ports, recording each claim in `published_ports`."""

    for entry in portal.publish:
        for node_id in entry.nodes or []:
            if node_id not in node_ids:
                raise ValueError(f"Portal {portal.id!r} publish port {entry.port} references unknown node {node_id!r}")
            if node_id not in hub_nodes:
                raise ValueError(
                    f"Portal {portal.id!r} publish port {entry.port} references node {node_id!r}"
                    " outside a hub region; published ports are bound by hub nodes"
                )
        scope = sorted(entry.nodes) if entry.nodes else sorted(hub_nodes)
        for node_id in scope:
            reserved = reserved_ports[node_id]
            for transport in entry.network.transports:
                if (entry.port, transport) in reserved:
                    raise ValueError(
                        f"Portal {portal.id!r} publishes {transport} port {entry.port} on node {node_id!r},"
                        f" which already binds it for {reserved[(entry.port, transport)]}"
                    )
            # Keyed without transport: inbound tag is `{id}-publish-{port}`
            owner = published_ports.get((node_id, entry.port))
            if owner == portal.id:
                raise ValueError(
                    f"Portal {portal.id!r} publishes port {entry.port} on node {node_id!r} more"
                    " than once; each publish entry sharing a node must use a distinct port"
                )
            if owner is not None:
                raise ValueError(
                    f"Portal {portal.id!r} publishes port {entry.port} on node {node_id!r},"
                    f" already published by portal {owner!r}; publish entries sharing a node"
                    " must use distinct ports"
                )
            published_ports[(node_id, entry.port)] = portal.id


class ConglomerateConfig(BaseModel):
    global_: GlobalConfig = Field(alias="global")
    defaults: DefaultsConfig
    groups: list[Group]
    users: list[User]
    portals: list[Portal] = []
    routing: RoutingConfig
    regions: list[Region]

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    @model_validator(mode="after")
    def _validate_references(self) -> "ConglomerateConfig":
        group_ids = {g.id for g in self.groups}
        region_ids = {r.id for r in self.regions}
        node_ids: set[str] = set()
        hub_nodes: dict[str, tuple[Region, Node]] = {}

        # Unique region IDs
        if len(region_ids) != len(self.regions):
            seen: set[str] = set()
            for r in self.regions:
                if r.id in seen:
                    raise ValueError(f"Duplicate region id: {r.id!r}")
                seen.add(r.id)

        # Unique node IDs across all regions; exit regions need vless_route + reality
        seen_vless_routes: dict[int, str] = {}  # route → region id
        for region in self.regions:
            for node in region.nodes:
                if node.id in node_ids:
                    raise ValueError(f"Duplicate node id: {node.id!r}")
                node_ids.add(node.id)
                if region.type == RegionType.HUB:
                    hub_nodes[node.id] = (region, node)
                # CDN inbound requires HAProxy TLS termination
                if self.global_.cdn and region.cdn_xhttp_path:
                    eff_haproxy = (
                        node.haproxy
                        if node.haproxy is not None
                        else (
                            self.defaults.exit.haproxy if region.type == RegionType.EXIT else self.defaults.hub.haproxy
                        )
                    )
                    if not eff_haproxy:
                        raise ValueError(
                            f"Node {node.id!r} disables haproxy but region {region.id!r} enables CDN"
                            " (cdn_xhttp_path); CDN requires HAProxy TLS termination"
                        )
                if region.type == RegionType.EXIT:
                    if node.reality is None:
                        raise ValueError(f"Exit node {node.id!r} in region {region.id!r} must have reality config")
                    _reject_hub_only_enabled(f"Exit node {node.id!r}", node.hysteria)
                node_hysteria = resolve_node_hysteria(node, region, self.defaults)
                if node_hysteria is not None:
                    _validate_hysteria(f"Node {node.id!r}", node_hysteria)
            if region.type == RegionType.EXIT:
                if region.vless_route is None:
                    raise ValueError(f"Exit region {region.id!r} must have vless_route")
                if region.vless_route in seen_vless_routes:
                    raise ValueError(
                        f"Duplicate vless_route {region.vless_route} in region {region.id!r}"
                        f" (already used by {seen_vless_routes[region.vless_route]!r})"
                    )
                seen_vless_routes[region.vless_route] = region.id
                if region.warp is not None:
                    if region.warp.vless_route in seen_vless_routes:
                        raise ValueError(
                            f"Duplicate warp vless_route {region.warp.vless_route} in region {region.id!r}"
                            f" (already used by {seen_vless_routes[region.warp.vless_route]!r})"
                        )
                    seen_vless_routes[region.warp.vless_route] = f"{region.id}(warp)"
                if region.routing and region.routing.routes:
                    for route in region.routing.routes:
                        if route.destination not in SPECIAL_DESTINATIONS:
                            raise ValueError(
                                f"exit route destination {route.destination!r} in region {region.id!r}"
                                " must be a special destination"
                            )
                _reject_hub_only_enabled(f"Exit region {region.id!r}", region.hysteria)
            else:
                if region.protocol is not None or region.hysteria is not None:
                    raise ValueError(f"Non-exit region {region.id!r} must not define protocol or hysteria")
                if region.routing and region.routing.routes:
                    raise ValueError(f"Non-exit region {region.id!r} must not define routing.routes")
            if region.lb_fallback is not None:
                region_node_ids = {n.id for n in region.nodes}
                if region.lb_fallback not in region_node_ids:
                    raise ValueError(
                        f"lb_fallback {region.lb_fallback!r} in region {region.id!r} is not a node in that region"
                    )

        # Unique group IDs
        if len(group_ids) != len(self.groups):
            seen_g: set[str] = set()
            for g in self.groups:
                if g.id in seen_g:
                    raise ValueError(f"Duplicate group id: {g.id!r}")
                seen_g.add(g.id)

        # Unique usernames
        usernames: set[str] = set()
        for user in self.users:
            if user.username in usernames:
                raise ValueError(f"Duplicate username: {user.username!r}")
            usernames.add(user.username)
            if user.group not in group_ids:
                raise ValueError(f"User {user.username!r} references unknown group {user.group!r}")

        # Portals: unique ids kept out of node/region namespaces
        derived_tags = set(node_ids) | SPECIAL_DESTINATIONS
        for node_id in node_ids:
            derived_tags.add(f"{TagPrefix.BACKUP}{node_id}")
            derived_tags.add(f"{TagPrefix.WARP}{node_id}")
            derived_tags.add(f"{TagPrefix.WARP}{TagPrefix.BACKUP}{node_id}")
        for region in self.regions:
            derived_tags.add(f"{TagPrefix.LB}{region.id}")
            derived_tags.add(f"{TagPrefix.LB_WARP}{region.id}")
        exit_region_ids = [r.id for r in self.regions if r.type == RegionType.EXIT]
        user_access = {u.username: set(u.access) for u in self.users}
        seen_portal_ids: set[str] = set()
        reserved_ports = {
            node.id: _node_reserved_ports(region, node, self.defaults, self.global_, self.users)
            for region in self.regions
            for node in region.nodes
        }
        rendered_access: set[AccessType] = set()
        if self.portals:
            if not hub_nodes:
                raise ValueError(
                    "Portals require at least one hub node; a portal opens its reverse tunnel by dialing hub nodes"
                )
            for r, n in hub_nodes.values():
                rendered_access |= _hub_rendered_access(r, n, self.defaults, self.global_)
        published_ports: dict[tuple[str, int], str] = {}  # (node id, port) → portal id
        for portal in self.portals:
            if portal.id in seen_portal_ids:
                raise ValueError(f"Duplicate portal id: {portal.id!r}")
            seen_portal_ids.add(portal.id)
            if portal.id in node_ids or portal.id in region_ids or portal.id in SPECIAL_DESTINATIONS:
                raise ValueError(f"Portal id {portal.id!r} collides with a node id, region id, or special destination")
            tag = f"{portal.id}{TagSuffix.PORTAL}"
            if tag in derived_tags:
                raise ValueError(f"Portal {portal.id!r} tag {tag!r} collides with a derived outbound tag")
            for region_id in exit_region_ids:
                if tag.startswith(region_id) or tag.startswith(f"{TagPrefix.WARP}{region_id}"):
                    raise ValueError(
                        f"Portal {portal.id!r} tag {tag!r} starts with exit region {region_id!r};"
                        " balancer and observatory selectors match tag prefixes — rename the portal"
                    )
            for username in portal.users:
                if username not in usernames:
                    raise ValueError(f"Portal {portal.id!r} references unknown user {username!r}")
                if not user_access[username] & ROUTABLE_ACCESS & rendered_access:
                    raise ValueError(
                        f"Portal {portal.id!r} member {username!r} has no access type carrying a"
                        f" routable identity that a hub node renders (member has:"
                        f" {', '.join(sorted(user_access[username])) or 'none'};"
                        f" hub nodes render: {', '.join(sorted(rendered_access)) or 'none'});"
                        " the portal routing rule would match no traffic"
                    )
            _validate_portal_publish(portal, node_ids, hub_nodes, reserved_ports, published_ports)

        # hub_default references valid region or special destination
        hub_default = self.routing.hub_default
        if hub_default not in (region_ids | SPECIAL_DESTINATIONS):
            raise ValueError(f"hub_default {hub_default!r} is not a known region or special destination")

        # exit_routes_global destinations
        for route in self.routing.exit_routes_global:
            if route.destination not in SPECIAL_DESTINATIONS:
                raise ValueError(f"exit_routes_global destination {route.destination!r} must be a special destination")

        # hub_routes destinations
        valid_destinations = SPECIAL_DESTINATIONS | region_ids | node_ids
        for route in self.routing.hub_routes:
            if route.destination not in valid_destinations:
                raise ValueError(f"hub_route destination {route.destination!r} is unknown")
            for u in route.users or []:
                if u not in usernames:
                    raise ValueError(f"hub_route user {u!r} is not a known user")
            for u in route.proxy_users or []:
                if u not in usernames:
                    raise ValueError(f"hub_route proxy_user {u!r} is not a known user")

        return self
