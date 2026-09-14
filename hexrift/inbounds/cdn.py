"""CDN-fronted VLESS inbound over XHTTP with TLS termination in HAProxy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from hexrift.components.derive.identity import Namespace
from hexrift.components.schema.models.users import User
from hexrift.constants import (
    VLESS_FLOW,
    AccessType,
    RegionType,
    Socket,
    XrayNetwork,
    XrayProtocol,
    XraySecurity,
)
from hexrift.inbounds.base import InboundContext, InboundEnv, InboundSpec, ShareClient, SharedContext
from hexrift.inbounds.clients import ClientEntry, get_exit_clients, get_hub_access_clients
from hexrift.shared.share_url import vless_share_url
from hexrift.shared.xhttp import make_xhttp_settings, make_xhttp_share_params
from hexrift.shared.xray_defaults import make_inbound_sockopt, make_sniffing


def get_hub_cdn_clients(
    users: list[User],
    ns: Namespace,
    flow: str = VLESS_FLOW,
) -> list[ClientEntry]:
    """Clients for hub cdn-xhttp inbound."""

    return get_hub_access_clients(users, ns, AccessType.CDN, flow, include_server=True)


@dataclass(frozen=True)
class CdnContext(InboundContext):
    xhttp_host: str  # exit: {node_id}.{cdn.exit_domain}; hub: cdn.hub_domain
    xhttp_path: str
    cert_alias: str  # used in HAProxy crt-store
    domain: str  # used in HAProxy SNI matching
    clients: list[ClientEntry]


class CdnSpec(InboundSpec[CdnContext]):
    access_type: ClassVar[AccessType] = AccessType.CDN
    roles: ClassVar[frozenset[RegionType]] = frozenset({RegionType.EXIT, RegionType.HUB})
    context_type = CdnContext

    def build_context(self, env: InboundEnv) -> CdnContext | None:
        cdn = env.config.global_.cdn
        if not (cdn and env.region.cdn_xhttp_path):
            return None
        if env.role == RegionType.EXIT:
            domain = cdn.exit_domain
            xhttp_host = f"{env.node.id}.{cdn.exit_domain}"
            clients = get_exit_clients(
                env.hub_nodes,
                env.exit_node,
                env.ns,
                flow=env.node_keys.flow,
            )
        else:
            domain = cdn.hub_domain
            xhttp_host = cdn.hub_domain
            clients = get_hub_cdn_clients(
                env.config.users,
                env.ns,
                flow=env.node_keys.flow,
            )
        return CdnContext(
            xhttp_host=xhttp_host,
            xhttp_path=env.region.cdn_xhttp_path,
            cert_alias=domain.split(".")[0],
            domain=domain,
            clients=clients,
        )

    def fragment(self, ctx: CdnContext, shared: SharedContext) -> dict:
        return {
            "tag": "cdn-xhttp",
            "listen": Socket.VLESS_TLS,
            "protocol": XrayProtocol.VLESS,
            "settings": {
                "clients": ctx.clients,
                "decryption": shared.decryption,
            },
            "streamSettings": {
                "network": XrayNetwork.XHTTP,
                "security": XraySecurity.NONE,
                "xhttpSettings": make_xhttp_settings(ctx.xhttp_host, ctx.xhttp_path, cdn=True),
                "sockopt": make_inbound_sockopt(shared.ipv6, shared.trusted_forwarded_headers),
            },
            "sniffing": make_sniffing(shared.route_only),
        }

    def share_url(self, ctx: CdnContext, env: InboundEnv, client: ShareClient) -> str:
        keys = env.node_keys
        extras = make_xhttp_share_params(
            ctx.xhttp_host,
            ctx.xhttp_path,
            cdn=True,
        )
        params = {
            "encryption": keys.encryption,
            "flow": keys.client_flow,
            "security": XraySecurity.TLS,
            "sni": ctx.domain,
            "fp": client.fingerprint,
            "sid": client.short_id,
            "spx": "/",
            "alpn": "h3,h2,http/1.1",
            "insecure": "0",
            "allowInsecure": "0",
            **extras,
        }
        return vless_share_url(client.uuid, ctx.domain, params, client.fragment)


CDN_SPEC = CdnSpec()
