"""Hysteria 2 inbound."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar
from urllib.parse import quote
from uuid import UUID

from hexrift.components.derive.defaults import resolve_node_reality
from hexrift.components.derive.hysteria import derive_hysteria_endpoint, derive_hysteria_masquerade_url
from hexrift.components.schema.models.regions import HysteriaConfig
from hexrift.components.schema.models.resolve import resolve_node_hysteria
from hexrift.constants import (
    HYSTERIA_ALPN,
    HYSTERIA_VERSION,
    AccessType,
    RegionType,
    XrayNetwork,
    XrayProtocol,
    XraySecurity,
)
from hexrift.inbounds.base import InboundContext, InboundEnv, InboundSpec, SharedContext
from hexrift.inbounds.clients import HysteriaUser, get_exit_clients, get_hub_access_clients, hysteria_users
from hexrift.shared.hysteria import HYSTERIA_TRUNK_LISTENER_QUIC, make_hysteria_finalmask
from hexrift.shared.xray_defaults import make_sniffing


@dataclass(frozen=True)
class HysteriaContext(InboundContext):
    users: list[HysteriaUser]  # exit: hub-exit UUIDs; hub: users + servers + guests
    config: HysteriaConfig
    sni: str
    masquerade_url: str
    certificates: list[dict]  # tlsSettings.certificates entries
    obfs_password: str | None
    trunk: bool  # exit-side listener dialed by hubs


class HysteriaSpec(InboundSpec[HysteriaContext]):
    access_type: ClassVar[AccessType] = AccessType.HYSTERIA
    roles: ClassVar[frozenset[RegionType]] = frozenset({RegionType.EXIT, RegionType.HUB})
    context_type = HysteriaContext

    def build_context(self, env: InboundEnv) -> HysteriaContext | None:
        hysteria = resolve_node_hysteria(env.node, env.region, env.config.defaults)
        if hysteria is None:
            return None
        if env.role == RegionType.EXIT:
            clients = get_exit_clients(env.hub_nodes, env.node, env.ns)
        else:
            clients = get_hub_access_clients(env.config.users, env.ns, AccessType.HYSTERIA, "", include_server=True)
        if not clients:
            return None
        reality = resolve_node_reality(env.node, env.region, env.config.defaults)
        ep = derive_hysteria_endpoint(hysteria, reality, env.node_keys.reality_private_key, env.ns.name)
        return HysteriaContext(
            users=hysteria_users(clients),
            config=hysteria,
            sni=ep.sni,
            masquerade_url=derive_hysteria_masquerade_url(hysteria, ep.sni),
            certificates=ep.certificates,
            obfs_password=ep.obfs_password,
            trunk=env.role == RegionType.EXIT,
        )

    def fragment(self, ctx: HysteriaContext, shared: SharedContext) -> dict:
        cfg = ctx.config
        return {
            "tag": "hysteria-in",
            "listen": "::" if shared.ipv6 else "0.0.0.0",  # noqa: S104
            "port": cfg.port,
            "protocol": XrayProtocol.HYSTERIA,
            "settings": {
                "version": HYSTERIA_VERSION,
                "users": ctx.users,
            },
            "streamSettings": {
                "network": XrayNetwork.HYSTERIA,
                "security": XraySecurity.TLS,
                "tlsSettings": {
                    "certificates": ctx.certificates,
                    "alpn": list(HYSTERIA_ALPN),
                    "minVersion": "1.3",
                    "enableSessionResumption": True,
                },
                "hysteriaSettings": {
                    "version": HYSTERIA_VERSION,
                    "masquerade": {"type": "proxy", "url": ctx.masquerade_url, "rewriteHost": True},
                },
                "finalmask": make_hysteria_finalmask(
                    cfg.congestion,
                    cfg.up,
                    cfg.down,
                    ctx.obfs_password,
                    HYSTERIA_TRUNK_LISTENER_QUIC if ctx.trunk else None,
                ),
            },
            "sniffing": make_sniffing(shared.route_only),
        }


HYSTERIA_SPEC = HysteriaSpec()


def build_hysteria_share_url(
    *,
    identity_uuid: UUID,
    hostname: str,
    port: int,
    sni: str,
    pin: str | None,
    obfs_password: str | None,
    fragment: str,
) -> str:
    """Build a hysteria2:// share URL; a pinned cert is self-trusted, so the URL also sets insecure=1."""

    params = [f"sni={sni}"]
    if pin is not None:
        params += ["insecure=1", f"pinSHA256={pin}"]
    else:
        params.append("insecure=0")
    if obfs_password is not None:
        params += ["obfs=salamander", f"obfs-password={quote(obfs_password, safe='')}"]
    return f"hysteria2://{identity_uuid}@{hostname}:{port}/?{'&'.join(params)}#{quote(fragment, safe='')}"
