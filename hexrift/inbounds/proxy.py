"""Mixed-protocol proxy inbound with username/password auth."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from hexrift.components.schema.models.defaults import DefaultsConfig
from hexrift.components.schema.models.regions import Node
from hexrift.constants import AccessType, RegionType, Socket, XrayProtocol
from hexrift.inbounds.base import InboundContext, InboundEnv, InboundSpec, SharedContext
from hexrift.shared.xray_defaults import make_sniffing


def resolve_node_proxy_inbound(node: Node, defaults: DefaultsConfig) -> bool:
    if node.proxy_inbound is not None:
        return node.proxy_inbound
    return defaults.hub.proxy_inbound


@dataclass(frozen=True)
class ProxyContext(InboundContext):
    accounts: list[dict]  # [{"user": username, "pass": user_uuid_str}]; may be empty


class ProxySpec(InboundSpec[ProxyContext]):
    access_type: ClassVar[AccessType] = AccessType.PROXY
    roles: ClassVar[frozenset[RegionType]] = frozenset({RegionType.HUB})
    context_type = ProxyContext

    def build_context(self, env: InboundEnv) -> ProxyContext | None:
        if not resolve_node_proxy_inbound(env.node, env.config.defaults):
            return None
        ns = env.ns
        accounts: list[dict] = []
        for u in env.config.users:
            if AccessType.PROXY not in u.access:
                continue
            user_base = ns.user_uuid(u.username, override=u.uuid)
            accounts.append(
                {
                    "user": u.username,
                    "pass": str(user_base),
                }
            )
            for label in u.guests:
                accounts.append(
                    {
                        "user": ns.guest_email(label, u.username),
                        "pass": str(ns.guest_uuid(label, u.username, user_base=user_base)),
                    }
                )
        return ProxyContext(accounts=accounts)

    def fragment(self, ctx: ProxyContext, shared: SharedContext) -> dict:
        return {
            "tag": "mixed-inbound",
            "listen": Socket.MIXED,
            "port": 80,
            "protocol": XrayProtocol.MIXED,
            "settings": {
                "auth": "password",
                "accounts": ctx.accounts,
                "allowTransparent": True,
                "udp": True,
                "ip": "127.0.0.1",
            },
            "sniffing": make_sniffing(shared.route_only),
        }


PROXY_SPEC = ProxySpec()
