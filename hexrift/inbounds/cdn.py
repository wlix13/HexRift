"""CDN-fronted VLESS inbound over XHTTP with TLS termination in HAProxy."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import ClassVar
from urllib.parse import quote
from uuid import UUID

from hexrift.components.derive.identity import Namespace
from hexrift.components.keys.store import NodeKeys
from hexrift.components.schema.models.users import User
from hexrift.constants import (
    VLESS_FLOW,
    AccessType,
    RegionType,
    Socket,
    UplinkHttpMethod,
    XrayNetwork,
    XrayProtocol,
    XraySecurity,
)
from hexrift.inbounds.base import InboundContext, InboundEnv, InboundSpec, SharedContext
from hexrift.inbounds.clients import ClientEntry, get_exit_clients, get_hub_access_clients
from hexrift.shared.xhttp import XHTTP_EXTRA_CDN, make_xhttp_settings
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
                env.node,
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


CDN_SPEC = CdnSpec()


def build_cdn_share_url(
    *,
    identity_uuid: UUID,
    cdn_domain: str,
    cdn_path: str,
    hub_keys: NodeKeys,
    short_id: str,
    fingerprint: str,
    fragment: str,
) -> str:
    """Build CDN share URL: VLESS over XHTTP through CDN with TLS."""

    extra = json.dumps(
        {
            **XHTTP_EXTRA_CDN,
            "uplinkHTTPMethod": UplinkHttpMethod.PATCH,
        },
        separators=(",", ":"),
    )
    params = "&".join(
        [
            f"encryption={hub_keys.encryption}",
            f"flow={hub_keys.client_flow}",
            f"security={XraySecurity.TLS}",
            f"sni={cdn_domain}",
            f"fp={fingerprint}",
            f"sid={short_id}",
            f"spx={quote('/', safe='')}",
            f"alpn={quote('h3,h2,http/1.1', safe='')}",
            "insecure=0",
            "allowInsecure=0",
            "type=xhttp",
            f"host={cdn_domain}",
            f"path={quote(cdn_path, safe='')}",
            "mode=auto",
            f"extra={quote(extra, safe='')}",
        ]
    )
    return f"vless://{identity_uuid}@{cdn_domain}:443?{params}#{quote(fragment, safe='')}"
