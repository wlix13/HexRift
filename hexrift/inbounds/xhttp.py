"""Direct VLESS inbound: XHTTP, or raw TCP on exits, over Reality or TLS."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from hexrift.components.derive.defaults import derive_server_names, derive_xhttp_host, resolve_node_reality
from hexrift.components.derive.identity import Namespace
from hexrift.components.derive.topology import direct_tag, portal_tag
from hexrift.components.schema.models.groups import Group
from hexrift.components.schema.models.resolve import (
    resolve_exit_transport,
    resolve_node_xhttp,
    resolve_region_tls,
)
from hexrift.components.schema.models.shared import RealityFallbackLimits
from hexrift.constants import (
    REALITY_INBOUND_PORT,
    VLESS_FLOW,
    XHTTP_TLS_ALPN,
    AccessType,
    ExitTransport,
    RegionType,
    Socket,
    XrayNetwork,
    XrayProtocol,
    XraySecurity,
)
from hexrift.errors import RenderError
from hexrift.inbounds.base import InboundContext, InboundEnv, InboundSpec, ShareClient, SharedContext
from hexrift.inbounds.clients import ClientEntry, get_exit_clients, get_hub_access_clients
from hexrift.shared.share_url import vless_share_url
from hexrift.shared.xhttp import make_xhttp_settings, make_xhttp_share_params
from hexrift.shared.xray_defaults import make_inbound_sockopt, make_sniffing


if TYPE_CHECKING:
    from hexrift.components.schema.models.portals import Portal
    from hexrift.components.schema.models.regions import CertificateFiles
    from hexrift.components.schema.models.shared import XhttpConfig
    from hexrift.components.schema.models.users import User


def get_hub_vless_clients(
    users: list[User],
    portals: list[Portal],
    ns: Namespace,
    flow: str = VLESS_FLOW,
) -> list[ClientEntry]:
    """Clients for hub VLESS-XHTTP inbound."""

    clients: list[ClientEntry] = []
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
    return clients + get_portal_clients(portals, ns, flow)


def get_portal_clients(portals: list[Portal], ns: Namespace, flow: str = VLESS_FLOW) -> list[ClientEntry]:
    """One reverse client per portal."""

    return [
        {
            "email": ns.portal_email(portal.id),
            "id": str(ns.portal_uuid(portal.id, override=portal.uuid)),
            "flow": flow,
            "reverse": {"tag": portal_tag(portal.id)},
        }
        for portal in portals
    ]


def get_hub_short_ids(groups: list[Group], ns: Namespace) -> list[str]:
    """Hub node shortIds = group shortIds only."""

    return [ns.group_short_id(group) for group in groups]


def get_hub_portal_short_ids(portals: list[Portal], ns: Namespace) -> list[str]:
    """One shortId per portal."""

    return [ns.portal_short_id(portal.id) for portal in portals]


def get_hub_user_short_ids(users: list[User], ns: Namespace) -> list[str]:
    """One shortId per user with guests."""

    seen: set[str] = set()
    result: list[str] = []
    for user in users:
        if not user.guests:
            continue
        if AccessType.XHTTP not in user.access and AccessType.CDN not in user.access:
            continue
        sid = ns.user_short_id(user.username)
        if sid not in seen:
            seen.add(sid)
            result.append(sid)
    return result


@dataclass(frozen=True, kw_only=True)
class DirectInboundContext(InboundContext):
    clients: list[ClientEntry]  # exit: hub-exit UUIDs; hub: users + servers + guests + portals


@dataclass(frozen=True, kw_only=True)
class RealityXhttpContext(DirectInboundContext):
    xhttp_host: str
    xhttp_path: str
    short_ids: list[str]  # exit: single exit shortId; hub: group + per-user shortIds
    dest: str
    server_names: list[str]
    private_key: str
    fallback_limits: RealityFallbackLimits


@dataclass(frozen=True, kw_only=True)
class TcpRealityContext(DirectInboundContext):
    """Exit inbound on raw TCP, Reality only, no HTTP layer."""

    short_ids: list[str]
    dest: str
    server_names: list[str]
    private_key: str
    fallback_limits: RealityFallbackLimits


@dataclass(frozen=True, kw_only=True)
class TlsXhttpContext(DirectInboundContext):
    xhttp_host: str
    xhttp_path: str
    certificate: CertificateFiles  # operator cert for node hostname


class DirectInboundSpec(InboundSpec[DirectInboundContext]):
    access_type: ClassVar[AccessType] = AccessType.XHTTP
    roles: ClassVar[frozenset[RegionType]] = frozenset({RegionType.EXIT, RegionType.HUB})
    context_type = DirectInboundContext

    def build_context(self, env: InboundEnv) -> DirectInboundContext:
        if env.role == RegionType.EXIT:
            clients = get_exit_clients(env.hub_nodes, env.exit_node, env.ns, flow=env.node_keys.flow)
            short_ids = [env.ns.exit_short_id(env.node.id)]
            if resolve_exit_transport(env.exit_region) is ExitTransport.TCP:
                return self._tcp_context(env, clients, short_ids)
            xhttp = resolve_node_xhttp(env.node, env.region, env.config.defaults)
            return self._reality_context(
                env,
                xhttp,
                clients,
                short_ids,
            )
        xhttp = resolve_node_xhttp(env.node, env.region, env.config.defaults)
        tls = resolve_region_tls(env.hub_region, env.config.defaults)
        if tls is not None:
            return TlsXhttpContext(
                clients=get_hub_access_clients(
                    env.config.users, env.ns, AccessType.TLS, env.node_keys.flow, include_server=True
                )
                + get_portal_clients(env.config.portals, env.ns, env.node_keys.flow),
                xhttp_host=xhttp.host if xhttp.host is not None else env.node.hostname,
                xhttp_path=xhttp.path,
                certificate=tls.certificate,
            )
        clients = get_hub_vless_clients(env.config.users, env.config.portals, env.ns, flow=env.node_keys.flow)
        short_ids = (
            get_hub_short_ids(env.config.groups, env.ns)
            + get_hub_portal_short_ids(env.config.portals, env.ns)
            + get_hub_user_short_ids(env.config.users, env.ns)
        )
        return self._reality_context(
            env,
            xhttp,
            clients,
            short_ids,
        )

    @staticmethod
    def _reality_context(
        env: InboundEnv,
        xhttp: XhttpConfig,
        clients: list[ClientEntry],
        short_ids: list[str],
    ) -> RealityXhttpContext:
        reality = resolve_node_reality(env.node, env.region, env.config.defaults)
        return RealityXhttpContext(
            clients=clients,
            xhttp_host=derive_xhttp_host(reality, xhttp),
            xhttp_path=xhttp.path,
            short_ids=short_ids,
            dest=reality.dest,
            server_names=derive_server_names(reality),
            private_key=env.node_keys.reality_private_key,
            fallback_limits=reality.fallback_limits,
        )

    @staticmethod
    def _tcp_context(env: InboundEnv, clients: list[ClientEntry], short_ids: list[str]) -> TcpRealityContext:
        reality = resolve_node_reality(env.node, env.region, env.config.defaults)
        return TcpRealityContext(
            clients=clients,
            short_ids=short_ids,
            dest=reality.dest,
            server_names=derive_server_names(reality),
            private_key=env.node_keys.reality_private_key,
            fallback_limits=reality.fallback_limits,
        )

    @staticmethod
    def _reality_settings(ctx: RealityXhttpContext | TcpRealityContext) -> dict:
        return {
            "xver": 0,
            "show": False,
            "maxTimeDiff": 60000,
            "dest": ctx.dest,
            "serverNames": ctx.server_names,
            "privateKey": ctx.private_key,
            "shortIds": ctx.short_ids,
            "limitFallbackUpload": ctx.fallback_limits.xray_settings,
            "limitFallbackDownload": ctx.fallback_limits.xray_settings,
        }

    def fragment(self, ctx: DirectInboundContext, shared: SharedContext) -> dict:
        transport = ExitTransport.TCP if isinstance(ctx, TcpRealityContext) else ExitTransport.XHTTP
        fragment: dict = {
            "tag": direct_tag(transport),
        }
        if shared.haproxy:
            fragment["listen"] = Socket.VLESS_REALITY
        else:
            # Xray binds only IPv4 if `0.0.0.0`, dualstack if `::` (if no ipv6Only sockopt)
            fragment["listen"] = "::" if shared.ipv6 else "0.0.0.0"  # noqa: S104
            fragment["port"] = REALITY_INBOUND_PORT
        security: XraySecurity
        if isinstance(ctx, TlsXhttpContext):
            security = XraySecurity.TLS
            network = XrayNetwork.XHTTP
        elif isinstance(ctx, TcpRealityContext):
            security = XraySecurity.REALITY
            network = XrayNetwork.TCP
        elif isinstance(ctx, RealityXhttpContext):
            security = XraySecurity.REALITY
            network = XrayNetwork.XHTTP
        else:
            raise RenderError(f"Direct inbound context {type(ctx).__name__} carries no security")
        stream: dict = {"network": network, "security": security}
        if isinstance(ctx, TlsXhttpContext | RealityXhttpContext):
            stream["xhttpSettings"] = make_xhttp_settings(ctx.xhttp_host, ctx.xhttp_path)
        if isinstance(ctx, TlsXhttpContext):
            stream["tlsSettings"] = {
                "alpn": list(XHTTP_TLS_ALPN),
                "certificates": [
                    {"certificateFile": ctx.certificate.cert_file, "keyFile": ctx.certificate.key_file},
                ],
            }
        else:
            stream["realitySettings"] = self._reality_settings(ctx)
        stream["sockopt"] = make_inbound_sockopt(shared.ipv6, shared.trusted_forwarded_headers)
        fragment.update(
            {
                "protocol": XrayProtocol.VLESS,
                "settings": {
                    "clients": ctx.clients,
                    "decryption": shared.decryption,
                },
                "streamSettings": stream,
                "sniffing": make_sniffing(shared.route_only),
            }
        )
        return fragment

    def share_url(self, ctx: DirectInboundContext, env: InboundEnv, client: ShareClient) -> str:
        keys = env.node_keys
        params: dict[str, str] = {"encryption": keys.encryption, "flow": keys.client_flow}
        if isinstance(ctx, TlsXhttpContext):
            params |= {
                "security": XraySecurity.TLS,
                "sni": env.node.hostname,  # operator cert names node hostname
                "fp": client.fingerprint,
                "alpn": ",".join(XHTTP_TLS_ALPN),
            }
        elif isinstance(ctx, TcpRealityContext | RealityXhttpContext):
            params |= {
                "security": XraySecurity.REALITY,
                "sni": ctx.server_names[0],
                "fp": client.fingerprint,
                "pbk": keys.reality_public_key,
                "sid": client.short_id,
            }
        else:
            raise RenderError(f"Direct inbound context {type(ctx).__name__} carries no security")
        if isinstance(ctx, TcpRealityContext):
            params |= {"type": XrayNetwork.TCP}
        else:
            params |= make_xhttp_share_params(ctx.xhttp_host, ctx.xhttp_path)
        return vless_share_url(client.uuid, env.node.hostname, params, client.fragment)


XHTTP_SPEC = DirectInboundSpec()
