"""Hysteria 2 hub→exit link."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from hexrift.components.derive.defaults import resolve_node_reality
from hexrift.components.derive.hysteria import derive_hysteria_endpoint
from hexrift.components.schema.models.resolve import resolve_node_hysteria
from hexrift.constants import (
    HYSTERIA_ALPN,
    HYSTERIA_VERSION,
    ExitProtocol,
    HysteriaCongestion,
    XrayNetwork,
    XrayProtocol,
    XraySecurity,
)
from hexrift.errors import RenderError
from hexrift.links.base import LinkContext, LinkEnv, LinkSpec
from hexrift.shared.hysteria import hysteria_trunk_dialer_quic, make_hysteria_finalmask
from hexrift.shared.xray_defaults import make_udp_sockopt


@dataclass(frozen=True, kw_only=True)
class HysteriaLinkContext(LinkContext):
    protocol: ClassVar[ExitProtocol] = ExitProtocol.HYSTERIA

    address: str  # {exitId}.{aphelion_domain}
    port: int
    auth: str  # hub-exit UUID
    sni: str
    pin: str | None  # None: verify by CA roots
    obfs_password: str | None
    congestion: HysteriaCongestion
    brutal_up: str | None  # exit's down
    brutal_down: str | None  # exit's up
    chrome_parrot: bool  # False: the exit's cert can't be negotiated by Chrome's parroted ClientHello


class HysteriaLinkSpec(LinkSpec[HysteriaLinkContext]):
    protocol: ClassVar[ExitProtocol] = ExitProtocol.HYSTERIA
    context_type = HysteriaLinkContext

    def build_context(self, env: LinkEnv, identity: str, tag_prefix: str) -> HysteriaLinkContext:
        hysteria = resolve_node_hysteria(env.exit_node, env.exit_region, env.config.defaults)
        if hysteria is None:
            raise RenderError(f"Exit node {env.exit_node.id!r} renders no hysteria listener for hubs to dial")
        reality = resolve_node_reality(env.exit_node, env.exit_region, env.config.defaults)
        ep = derive_hysteria_endpoint(hysteria, reality, env.exit_keys.reality_private_key, env.ns.name)
        return HysteriaLinkContext(
            exit_id=env.exit_node.id,
            tag_prefix=tag_prefix,
            address=env.address,
            port=hysteria.port,
            auth=identity,
            sni=ep.sni,
            pin=ep.pin,
            obfs_password=ep.obfs_password,
            congestion=hysteria.congestion,
            brutal_up=hysteria.down,
            brutal_down=hysteria.up,
            chrome_parrot=ep.chrome_parrot,
        )

    def fragment(self, ctx: HysteriaLinkContext, ipv6: bool) -> dict:
        tls: dict = {"serverName": ctx.sni, "alpn": list(HYSTERIA_ALPN)}
        if ctx.pin is not None:
            tls["pinnedPeerCertSha256"] = ctx.pin
        tls["enableSessionResumption"] = True
        return {
            "tag": ctx.tag,
            "protocol": XrayProtocol.HYSTERIA,
            "settings": {
                "version": HYSTERIA_VERSION,
                "address": ctx.address,
                "port": ctx.port,
            },
            "streamSettings": {
                "network": XrayNetwork.HYSTERIA,
                "security": XraySecurity.TLS,
                "tlsSettings": tls,
                "hysteriaSettings": {"version": HYSTERIA_VERSION, "auth": ctx.auth},
                "finalmask": make_hysteria_finalmask(
                    ctx.congestion,
                    ctx.brutal_up,
                    ctx.brutal_down,
                    ctx.obfs_password,
                    hysteria_trunk_dialer_quic(ctx.chrome_parrot),
                ),
                "sockopt": make_udp_sockopt(ipv6),
            },
        }


HYSTERIA_LINK = HysteriaLinkSpec()
