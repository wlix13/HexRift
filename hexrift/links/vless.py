"""VLESS over XHTTP + Reality hub→exit link."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from hexrift.components.derive.defaults import derive_server_names, derive_xhttp_host, resolve_node_reality
from hexrift.constants import ExitProtocol, XrayNetwork, XrayProtocol, XraySecurity
from hexrift.links.base import LinkContext, LinkEnv, LinkSpec
from hexrift.shared.xhttp import make_xhttp_settings
from hexrift.shared.xray_defaults import make_sockopt


@dataclass(frozen=True, kw_only=True)
class VlessLinkContext(LinkContext):
    protocol: ClassVar[ExitProtocol] = ExitProtocol.VLESS

    address: str  # {exitId}.{aphelion_domain}
    user_id: str  # hub-exit UUID
    encryption: str  # full encryption key string
    public_key: str  # exit node's reality public key
    fingerprint: str
    server_name: str  # exit node's server_name (first of server_names)
    short_id: str  # exit node's single shortId
    xhttp_host: str
    xhttp_path: str
    flow: str  # VLESS flow (empty when encryption disabled)


class VlessLinkSpec(LinkSpec[VlessLinkContext]):
    protocol: ClassVar[ExitProtocol] = ExitProtocol.VLESS
    context_type = VlessLinkContext

    def build_context(self, env: LinkEnv, identity: str, tag_prefix: str) -> VlessLinkContext:
        reality = resolve_node_reality(env.exit_node, env.exit_region, env.config.defaults)
        return VlessLinkContext(
            exit_id=env.exit_node.id,
            tag_prefix=tag_prefix,
            address=env.address,
            user_id=identity,
            encryption=env.exit_keys.encryption,
            public_key=env.exit_keys.reality_public_key,
            fingerprint=env.exit_connections.fingerprint,
            server_name=derive_server_names(reality)[0],
            short_id=env.ns.exit_short_id(env.exit_node.id),
            xhttp_host=derive_xhttp_host(reality),
            xhttp_path=reality.xhttp_path,
            flow=env.exit_keys.client_flow,
        )

    def fragment(self, ctx: VlessLinkContext, ipv6: bool) -> dict:
        return {
            "tag": ctx.tag,
            "protocol": XrayProtocol.VLESS,
            "settings": {
                "vnext": [
                    {
                        "address": ctx.address,
                        "port": 443,
                        "users": [
                            {
                                "id": ctx.user_id,
                                "encryption": ctx.encryption,
                                "flow": ctx.flow,
                            }
                        ],
                    }
                ],
            },
            "streamSettings": {
                "network": XrayNetwork.XHTTP,
                "security": XraySecurity.REALITY,
                "xhttpSettings": make_xhttp_settings(ctx.xhttp_host, ctx.xhttp_path),
                "realitySettings": {
                    "publicKey": ctx.public_key,
                    "fingerprint": ctx.fingerprint,
                    "serverName": ctx.server_name,
                    "shortId": ctx.short_id,
                },
                "sockopt": make_sockopt(ipv6),
            },
        }


VLESS_LINK = VlessLinkSpec()
