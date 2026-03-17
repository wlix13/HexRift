from __future__ import annotations

from dataclasses import dataclass, field

from hexrift.components.derive.defaults import (
    derive_server_names,
    derive_xhttp_host,
    resolve_exit_connections,
    resolve_node_ipv6,
    resolve_node_proxy_inbound,
    resolve_node_reality,
)
from hexrift.components.derive.identity import Namespace
from hexrift.components.derive.topology import (
    build_balancers,
    build_burst_observatory_selectors,
    build_hub_routing_rules,
    get_exit_cdn_clients,
    get_exit_direct_clients,
    get_hub_cdn_clients,
    get_hub_short_ids,
    get_hub_vless_clients,
)
from hexrift.components.keys.store import NodeKeys
from hexrift.components.schema.models.regions import Node, Region
from hexrift.components.schema.models.root import ConglomerateConfig
from hexrift.constants import VLESS_FLOW, AccessType, LbRole, RegionType, TagPrefix


def _flow_for_keys(keys: NodeKeys) -> str:
    """Return VLESS flow string, or empty when encryption is disabled."""

    return VLESS_FLOW if keys.encryption != "none" else ""


@dataclass
class ExitContext:
    node_id: str
    hostname: str
    ipv6: bool

    # Reality inbound
    reality_dest: str
    reality_server_names: list[str]
    reality_private_key: str
    reality_public_key: str  # not used in config but kept for reference
    reality_xhttp_host: str
    reality_xhttp_path: str
    reality_short_id: str
    decryption: str

    # Client lists
    direct_clients: list[dict]  # hub-exit UUIDs

    # Routing
    warp_domains: list[str]  # region warp_extra + exit_warp_global (domain-based warp routing)

    # CDN inbound (None when CDN is not configured)
    cdn_xhttp_host: str | None = None
    cdn_xhttp_path: str | None = None
    cdn_cert_alias: str | None = None
    cdn_clients: list[dict] = field(default_factory=list)


@dataclass
class PortalContext:
    label: str
    domain: str  # {label}.{bridge_domain}
    user_email: str  # {username}@{namespace}
    portal_email: str  # {label}-portal@{username}


@dataclass
class HubOutboundContext:
    exit_id: str
    address: str  # {exitId}.{aphelion_domain}
    user_id: str  # hub-exit UUID
    encryption: str  # full encryption key string
    public_key: str  # exit node's reality public key
    fingerprint: str
    server_name: str  # exit node's server_name (first of server_names)
    short_id: str  # exit node's single shortId
    xhttp_host: str  # exit node's xhttp host
    xhttp_path: str  # exit node's xhttp path
    flow: str  # VLESS flow (empty when encryption disabled)
    tag_prefix: str = ""  # "backup-" if lb_role==backup, "warp-" for warp variant


@dataclass
class HubContext:
    node_id: str
    hostname: str
    ipv6: bool

    # Reality inbound
    reality_dest: str
    reality_server_names: list[str]
    reality_private_key: str
    reality_xhttp_host: str
    reality_xhttp_path: str
    reality_short_ids: list[str]
    decryption: str

    # Client lists
    vless_clients: list[dict]

    # Portals
    portals: list[PortalContext]

    # Outbounds
    outbounds: list[HubOutboundContext]  # one per exit node (normal)
    warp_outbounds: list[HubOutboundContext]  # one per exit node (warp variant)

    # Routing / balancers
    balancers: list[dict]
    routing_rules: list[dict]
    observatory_selectors: list[str]

    # Proxy inbound
    proxy_inbound: bool
    proxy_inbound_accounts: list[dict]  # [{"user": username, "pass": user_uuid_str}]

    # CDN inbound (None when CDN is not configured)
    cdn_xhttp_host: str | None = None
    cdn_xhttp_path: str | None = None
    cdn_cert_alias: str | None = None
    cdn_clients: list[dict] = field(default_factory=list)


def build_exit_context(
    config: ConglomerateConfig,
    region: Region,
    node: Node,
    node_keys: NodeKeys,
    hub_nodes: list[Node],
) -> ExitContext:
    ns = Namespace(config.global_.namespace)
    reality = resolve_node_reality(node, region, config.defaults)
    ipv6 = resolve_node_ipv6(node, region, config.defaults)
    server_names = derive_server_names(reality)
    xhttp_host = derive_xhttp_host(reality)

    # CDN host and cert alias
    cdn = config.global_.cdn
    cdn_host = cdn_path = cert_alias = None
    cdn_clients: list[dict] = []
    if cdn and region.cdn_xhttp_path:
        cdn_host = f"{node.id}.{cdn.exit_domain}"
        cdn_path = region.cdn_xhttp_path
        cert_alias = cdn.exit_domain.split(".")[0]
        cdn_clients = get_exit_cdn_clients(hub_nodes, node, ns, flow=_flow_for_keys(node_keys))

    # warp_domains: domain-based warp routing on exit
    warp_domains: list[str] = []
    if region.routing and region.routing.warp_extra:
        warp_domains.extend(region.routing.warp_extra)
    warp_domains.extend(config.routing.exit_warp_global)

    return ExitContext(
        node_id=node.id,
        hostname=node.hostname,
        ipv6=ipv6,
        reality_dest=reality.dest,
        reality_server_names=server_names,
        reality_private_key=node_keys.reality_private_key,
        reality_public_key=node_keys.reality_public_key,
        reality_xhttp_host=xhttp_host,
        reality_xhttp_path=reality.xhttp_path,
        reality_short_id=ns.exit_short_id(node.id),
        decryption=node_keys.decryption,
        direct_clients=get_exit_direct_clients(hub_nodes, node, ns, flow=_flow_for_keys(node_keys)),
        cdn_xhttp_host=cdn_host,
        cdn_xhttp_path=cdn_path,
        cdn_cert_alias=cert_alias,
        cdn_clients=cdn_clients,
        warp_domains=warp_domains,
    )


def build_hub_context(
    config: ConglomerateConfig,
    region: Region,
    node: Node,
    node_keys: NodeKeys,
    exit_node_keys: dict[str, NodeKeys],  # {exitNodeId: NodeKeys}
) -> HubContext:
    ns = Namespace(config.global_.namespace)
    reality = resolve_node_reality(node, region, config.defaults)
    ipv6 = resolve_node_ipv6(node, region, config.defaults)
    server_names = derive_server_names(reality)
    xhttp_host = derive_xhttp_host(reality)

    # CDN host and cert alias
    cdn = config.global_.cdn
    cdn_hub_domain = cdn_path = cert_alias = None
    if cdn and region.cdn_xhttp_path:
        cdn_hub_domain = cdn.hub_domain
        cdn_path = region.cdn_xhttp_path
        cert_alias = cdn_hub_domain.split(".")[0]

    # Short IDs
    short_ids = get_hub_short_ids(config.groups, ns)

    # Portals
    portals: list[PortalContext] = []
    for user in config.users:
        if not user.portals:
            continue
        for portal in user.portals:
            portals.append(
                PortalContext(
                    label=portal.label,
                    domain=f"{portal.label}.{config.global_.bridge_domain}",
                    user_email=ns.user_email(user.username),
                    portal_email=ns.portal_email(portal.label, user.username),
                )
            )

    # Build exit outbounds
    exit_regions = [r for r in config.regions if r.type == RegionType.EXIT]

    ec = resolve_exit_connections(node, config.defaults)
    outbounds: list[HubOutboundContext] = []
    warp_outbounds: list[HubOutboundContext] = []

    for exit_region in exit_regions:
        warp_vless_route = exit_region.warp.vless_route if exit_region.warp else None
        for exit_node in exit_region.nodes:
            ex_reality = resolve_node_reality(exit_node, exit_region, config.defaults)
            ex_server_names = derive_server_names(ex_reality)
            ex_xhttp_host = derive_xhttp_host(ex_reality)
            ex_keys = exit_node_keys[exit_node.id]
            ex_flow = _flow_for_keys(ex_keys)
            uid = ns.hub_exit_uuid(node.id, exit_node.id)
            short = ns.exit_short_id(exit_node.id)
            address = f"{exit_node.id}.{config.global_.aphelion_domain}"
            tag_prefix = TagPrefix.BACKUP if exit_node.lb_role == LbRole.BACKUP else TagPrefix.NONE

            outbounds.append(
                HubOutboundContext(
                    exit_id=exit_node.id,
                    address=address,
                    user_id=str(uid),
                    encryption=ex_keys.encryption,
                    public_key=ex_keys.reality_public_key,
                    fingerprint=ec.fingerprint,
                    server_name=ex_server_names[0],
                    short_id=short,
                    xhttp_host=ex_xhttp_host,
                    xhttp_path=ex_reality.xhttp_path,
                    flow=ex_flow,
                    tag_prefix=tag_prefix,
                )
            )

            if warp_vless_route is not None:
                w_uid = ns.warp_uuid(uid)
                warp_outbounds.append(
                    HubOutboundContext(
                        exit_id=exit_node.id,
                        address=address,
                        user_id=str(w_uid),
                        encryption=ex_keys.encryption,
                        public_key=ex_keys.reality_public_key,
                        fingerprint=ec.fingerprint,
                        server_name=ex_server_names[0],
                        short_id=short,
                        xhttp_host=ex_xhttp_host,
                        xhttp_path=ex_reality.xhttp_path,
                        flow=ex_flow,
                        tag_prefix=TagPrefix.WARP + tag_prefix,
                    )
                )

    proxy_accounts = []
    for u in config.users:
        if AccessType.PROXY not in u.access:
            continue
        user_base = ns.user_uuid(u.username, override=u.uuid)
        proxy_accounts.append(
            {
                "user": u.username,
                "pass": str(user_base),
            }
        )
        for label in u.guests:
            proxy_accounts.append(
                {
                    "user": ns.guest_email(label, u.username),
                    "pass": str(ns.guest_uuid(label, u.username, user_base=user_base)),
                }
            )

    return HubContext(
        node_id=node.id,
        hostname=node.hostname,
        ipv6=ipv6,
        reality_dest=reality.dest,
        reality_server_names=server_names,
        reality_private_key=node_keys.reality_private_key,
        reality_xhttp_host=xhttp_host,
        reality_xhttp_path=reality.xhttp_path,
        reality_short_ids=short_ids,
        decryption=node_keys.decryption,
        vless_clients=get_hub_vless_clients(config.users, ns, flow=_flow_for_keys(node_keys)),
        cdn_xhttp_host=cdn_hub_domain,
        cdn_xhttp_path=cdn_path,
        cdn_cert_alias=cert_alias,
        cdn_clients=get_hub_cdn_clients(config.users, ns, flow=_flow_for_keys(node_keys)) if cdn_hub_domain else [],
        portals=portals,
        outbounds=outbounds,
        warp_outbounds=warp_outbounds,
        balancers=build_balancers(exit_regions),
        routing_rules=build_hub_routing_rules(config),
        observatory_selectors=build_burst_observatory_selectors(exit_regions),
        proxy_inbound=(proxy_enabled := resolve_node_proxy_inbound(node, config.defaults)),
        proxy_inbound_accounts=proxy_accounts if proxy_enabled else [],
    )
