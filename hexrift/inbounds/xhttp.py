"""Direct VLESS inbound over XHTTP with Reality."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar
from urllib.parse import quote
from uuid import UUID

from hexrift.components.derive.defaults import derive_server_names, derive_xhttp_host, resolve_node_reality
from hexrift.components.derive.identity import Namespace
from hexrift.components.derive.topology import portal_tag
from hexrift.components.keys.store import NodeKeys
from hexrift.components.schema.models.groups import Group
from hexrift.components.schema.models.shared import RealityConfig, RealityFallbackLimits
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
from hexrift.inbounds.base import InboundContext, InboundEnv, InboundSpec, SharedContext
from hexrift.inbounds.clients import ClientEntry, get_exit_clients
from hexrift.shared.xhttp import make_xhttp_settings
from hexrift.shared.xray_defaults import SNIFFING, make_inbound_sockopt


def get_hub_vless_clients(
    users: list[User],
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
    for user in users:
        if user.portals:
            user_base = ns.user_uuid(user.username, override=user.uuid)
            for portal in user.portals:
                pt = portal_tag(portal.label)
                clients.append(
                    {
                        "email": ns.portal_email(portal.label, user.username),
                        "id": str(ns.portal_uuid(portal.label, user.username, user_base=user_base)),
                        "flow": flow,
                        "reverse": {"tag": pt},
                    }
                )
    return clients


def get_hub_short_ids(groups: list[Group], ns: Namespace) -> list[str]:
    """Hub node shortIds = group shortIds only."""

    return [ns.group_short_id(group) for group in groups]


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
    short_ids: list[str]  # exit: single exit shortId; hub: group + per-user shortIds
    dest: str
    server_names: list[str]
    private_key: str
    xhttp_host: str
    xhttp_path: str
    fallback_limits: RealityFallbackLimits


class XhttpSpec(InboundSpec[XhttpContext]):
    access_type: ClassVar[AccessType] = AccessType.XHTTP
    roles: ClassVar[frozenset[RegionType]] = frozenset({RegionType.EXIT, RegionType.HUB})
    context_type = XhttpContext

    def build_context(self, env: InboundEnv) -> XhttpContext:
        reality = resolve_node_reality(env.node, env.region, env.config.defaults)
        if env.role == RegionType.EXIT:
            clients = get_exit_clients(env.hub_nodes, env.node, env.ns, flow=env.node_keys.flow)
            short_ids = [env.ns.exit_short_id(env.node.id)]
        else:
            clients = get_hub_vless_clients(env.config.users, env.ns, flow=env.node_keys.flow)
            short_ids = get_hub_short_ids(env.config.groups, env.ns) + get_hub_user_short_ids(env.config.users, env.ns)
        return XhttpContext(
            clients=clients,
            short_ids=short_ids,
            dest=reality.dest,
            server_names=derive_server_names(reality),
            private_key=env.node_keys.reality_private_key,
            xhttp_host=derive_xhttp_host(reality),
            xhttp_path=reality.xhttp_path,
            fallback_limits=reality.fallback_limits,
        )

    def fragment(self, ctx: XhttpContext, shared: SharedContext) -> dict:
        return {
            "tag": "direct-xhttp",
            "listen": Socket.VLESS_REALITY,
            "protocol": XrayProtocol.VLESS,
            "settings": {
                "clients": ctx.clients,
                "decryption": shared.decryption,
            },
            "streamSettings": {
                "network": XrayNetwork.XHTTP,
                "security": XraySecurity.REALITY,
                "xhttpSettings": make_xhttp_settings(ctx.xhttp_host, ctx.xhttp_path),
                "realitySettings": {
                    "xver": 0,
                    "show": False,
                    "maxTimeDiff": 60000,
                    "dest": ctx.dest,
                    "serverNames": ctx.server_names,
                    "privateKey": ctx.private_key,
                    "shortIds": ctx.short_ids,
                    "limitFallbackUpload": ctx.fallback_limits.xray_settings,
                    "limitFallbackDownload": ctx.fallback_limits.xray_settings,
                },
                "sockopt": make_inbound_sockopt(shared.ipv6, shared.trusted_forwarded_headers),
            },
            "sniffing": SNIFFING,
        }


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
