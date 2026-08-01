"""DNS service inbound over mKCP transport."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from hexrift.components.derive.identity import Namespace
from hexrift.components.schema.models.regions import XdnsConfig
from hexrift.components.schema.models.resolve import resolve_node_xdns
from hexrift.components.schema.models.users import User
from hexrift.constants import AccessType, RegionType, XrayNetwork, XrayProtocol
from hexrift.inbounds.base import InboundContext, InboundEnv, InboundSpec, SharedContext
from hexrift.inbounds.clients import ClientEntry, get_hub_access_clients
from hexrift.shared.xray_defaults import MKCP_SETTINGS_XDNS, make_sniffing, make_sockopt


def get_hub_xdns_clients(
    users: list[User],
    ns: Namespace,
) -> list[ClientEntry]:
    """Clients for hub xdns inbound.

    xdns runs over non-TLS mKCP, where xtls-rprx-vision is useless, so flow is empty.
    """

    return get_hub_access_clients(users, ns, AccessType.XDNS, flow="")


@dataclass(frozen=True)
class XdnsContext(InboundContext):
    config: XdnsConfig
    clients: list[ClientEntry]


class XdnsSpec(InboundSpec[XdnsContext]):
    access_type: ClassVar[AccessType] = AccessType.XDNS
    roles: ClassVar[frozenset[RegionType]] = frozenset({RegionType.HUB})
    context_type = XdnsContext

    def build_context(self, env: InboundEnv) -> XdnsContext | None:
        xdns = resolve_node_xdns(env.node, env.config.defaults)
        if xdns is None:
            return None
        clients = get_hub_xdns_clients(env.config.users, env.ns)
        if not clients:
            return None
        return XdnsContext(config=xdns, clients=clients)

    def fragment(self, ctx: XdnsContext, shared: SharedContext) -> dict:
        return {
            "tag": "xdns",
            "listen": "0.0.0.0",  # noqa: S104
            "port": ctx.config.port,
            "protocol": XrayProtocol.VLESS,
            "settings": {
                "clients": ctx.clients,
                "decryption": shared.decryption,
            },
            "streamSettings": {
                "network": XrayNetwork.MKCP,
                "kcpSettings": MKCP_SETTINGS_XDNS,
                "finalmask": {
                    "udp": [
                        {
                            "type": "xdns",
                            "settings": {
                                "domains": ctx.config.domains,
                            },
                        },
                    ],
                },
                "sockopt": make_sockopt(shared.ipv6),
            },
            "sniffing": make_sniffing(shared.route_only),
        }


XDNS_SPEC = XdnsSpec()
