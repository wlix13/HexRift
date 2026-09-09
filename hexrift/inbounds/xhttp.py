"""Direct VLESS inbound over XHTTP with Reality or TLS."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar
from urllib.parse import quote
from uuid import UUID

from hexrift.components.derive.defaults import derive_server_names, derive_xhttp_host, resolve_node_reality
from hexrift.components.derive.identity import Namespace
from hexrift.components.derive.topology import portal_tag
from hexrift.components.keys.store import NodeKeys
from hexrift.components.schema.models.groups import Group
from hexrift.components.schema.models.resolve import resolve_region_tls
from hexrift.components.schema.models.shared import RealityConfig, RealityFallbackLimits
from hexrift.constants import (
    REALITY_INBOUND_PORT,
    VLESS_FLOW,
    XHTTP_TLS_ALPN,
    AccessType,
    RegionType,
    Socket,
    XrayNetwork,
    XrayProtocol,
    XraySecurity,
)
from hexrift.errors import RenderError
from hexrift.inbounds.base import InboundContext, InboundEnv, InboundSpec, SharedContext
from hexrift.inbounds.clients import ClientEntry, get_exit_clients, get_hub_access_clients
from hexrift.shared.xhttp import make_xhttp_settings
from hexrift.shared.xray_defaults import make_inbound_sockopt, make_sniffing


if TYPE_CHECKING:
    from hexrift.components.schema.models.portals import Portal
    from hexrift.components.schema.models.regions import CertificateFiles, TlsConfig
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


@dataclass(frozen=True)
class XhttpContext(InboundContext):
    clients: list[ClientEntry]  # exit: hub-exit UUIDs; hub: users + servers + guests + portals
    xhttp_host: str
    xhttp_path: str


@dataclass(frozen=True)
class RealityXhttpContext(XhttpContext):
    short_ids: list[str]  # exit: single exit shortId; hub: group + per-user shortIds
    dest: str
    server_names: list[str]
    private_key: str
    fallback_limits: RealityFallbackLimits


@dataclass(frozen=True)
class TlsXhttpContext(XhttpContext):
    certificate: CertificateFiles  # operator cert for xhttp_host, node hostname


class XhttpSpec(InboundSpec[XhttpContext]):
    access_type: ClassVar[AccessType] = AccessType.XHTTP
    roles: ClassVar[frozenset[RegionType]] = frozenset({RegionType.EXIT, RegionType.HUB})
    context_type = XhttpContext

    def build_context(self, env: InboundEnv) -> XhttpContext:
        if env.role == RegionType.EXIT:
            clients = get_exit_clients(env.hub_nodes, env.exit_node, env.ns, flow=env.node_keys.flow)
            return self._reality_context(env, clients, [env.ns.exit_short_id(env.node.id)])
        tls = resolve_region_tls(env.hub_region, env.config.defaults)
        if tls is not None:
            return TlsXhttpContext(
                clients=get_hub_access_clients(
                    env.config.users, env.ns, AccessType.TLS, env.node_keys.flow, include_server=True
                )
                + get_portal_clients(env.config.portals, env.ns, env.node_keys.flow),
                xhttp_host=env.node.hostname,
                xhttp_path=tls.xhttp_path,
                certificate=tls.certificate,
            )
        clients = get_hub_vless_clients(env.config.users, env.config.portals, env.ns, flow=env.node_keys.flow)
        short_ids = (
            get_hub_short_ids(env.config.groups, env.ns)
            + get_hub_portal_short_ids(env.config.portals, env.ns)
            + get_hub_user_short_ids(env.config.users, env.ns)
        )
        return self._reality_context(env, clients, short_ids)

    @staticmethod
    def _reality_context(env: InboundEnv, clients: list[ClientEntry], short_ids: list[str]) -> RealityXhttpContext:
        reality = resolve_node_reality(env.node, env.region, env.config.defaults)
        return RealityXhttpContext(
            clients=clients,
            xhttp_host=derive_xhttp_host(reality),
            xhttp_path=reality.xhttp_path,
            short_ids=short_ids,
            dest=reality.dest,
            server_names=derive_server_names(reality),
            private_key=env.node_keys.reality_private_key,
            fallback_limits=reality.fallback_limits,
        )

    def fragment(self, ctx: XhttpContext, shared: SharedContext) -> dict:
        fragment: dict = {
            "tag": "direct-xhttp",
        }
        if shared.haproxy:
            fragment["listen"] = Socket.VLESS_REALITY
        else:
            # Xray binds only IPv4 if `0.0.0.0`, dualstack if `::` (if no ipv6Only sockopt)
            fragment["listen"] = "::" if shared.ipv6 else "0.0.0.0"  # noqa: S104
            fragment["port"] = REALITY_INBOUND_PORT
        if isinstance(ctx, TlsXhttpContext):
            security = XraySecurity.TLS
            settings: dict = {
                "alpn": list(XHTTP_TLS_ALPN),
                "certificates": [
                    {"certificateFile": ctx.certificate.cert_file, "keyFile": ctx.certificate.key_file},
                ],
            }
        elif isinstance(ctx, RealityXhttpContext):
            security = XraySecurity.REALITY
            settings = {
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
        else:
            raise RenderError(f"Direct inbound context {type(ctx).__name__} carries no security")
        fragment.update(
            {
                "protocol": XrayProtocol.VLESS,
                "settings": {
                    "clients": ctx.clients,
                    "decryption": shared.decryption,
                },
                "streamSettings": {
                    "network": XrayNetwork.XHTTP,
                    "security": security,
                    "xhttpSettings": make_xhttp_settings(ctx.xhttp_host, ctx.xhttp_path),
                    f"{security}Settings": settings,  # Xray keys them realitySettings / tlsSettings
                    "sockopt": make_inbound_sockopt(shared.ipv6, shared.trusted_forwarded_headers),
                },
                "sniffing": make_sniffing(shared.route_only),
            }
        )
        return fragment


XHTTP_SPEC = XhttpSpec()


def build_reality_share_url(
    *,
    identity_uuid: UUID,
    hostname: str,
    hub_keys: NodeKeys,
    reality: RealityConfig,
    short_id: str,
    fingerprint: str,
    fragment: str,
) -> str:
    """Build direct share URL: VLESS over XHTTP with Reality."""

    server_names = derive_server_names(reality)
    xhttp_host = derive_xhttp_host(reality)
    params = "&".join(
        [
            f"encryption={hub_keys.encryption}",
            f"flow={hub_keys.client_flow}",
            f"security={XraySecurity.REALITY}",
            f"sni={server_names[0]}",
            f"fp={fingerprint}",
            f"pbk={hub_keys.reality_public_key}",
            f"sid={short_id}",
            "type=xhttp",
            f"host={xhttp_host}",
            f"path={quote(reality.xhttp_path, safe='')}",
            "mode=auto",
        ]
    )
    return f"vless://{identity_uuid}@{hostname}:443?{params}#{quote(fragment, safe='')}"


def build_tls_share_url(
    *,
    identity_uuid: UUID,
    hostname: str,
    hub_keys: NodeKeys,
    tls: TlsConfig,
    fingerprint: str,
    fragment: str,
) -> str:
    """Build direct share URL: VLESS over XHTTP with TLS."""

    params = "&".join(
        [
            f"encryption={hub_keys.encryption}",
            f"flow={hub_keys.client_flow}",
            f"security={XraySecurity.TLS}",
            f"sni={hostname}",
            f"fp={fingerprint}",
            f"alpn={quote(','.join(XHTTP_TLS_ALPN), safe='')}",
            "type=xhttp",
            f"host={hostname}",
            f"path={quote(tls.xhttp_path, safe='')}",
            "mode=auto",
        ]
    )
    return f"vless://{identity_uuid}@{hostname}:443?{params}#{quote(fragment, safe='')}"
