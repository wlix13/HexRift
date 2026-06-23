"""WireGuard protocol inbound with derived peers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from hexrift.components.derive.identity import Namespace
from hexrift.components.derive.wireguard import derive_user_wireguard_keypair, iter_hub_wireguard_allocs
from hexrift.components.schema.models.defaults import DefaultsConfig
from hexrift.components.schema.models.regions import Node, NodeWireguardOverride, WireguardConfig
from hexrift.components.schema.models.users import User
from hexrift.constants import AccessType, RegionType, XrayProtocol
from hexrift.errors import DeriveError
from hexrift.inbounds.base import InboundContext, InboundEnv, InboundSpec, SharedContext
from hexrift.shared.crypto import x25519_urlsafe_to_std
from hexrift.shared.xray_defaults import make_sniffing


def resolve_node_wireguard(node: Node, defaults: DefaultsConfig) -> WireguardConfig | None:
    override: NodeWireguardOverride | None = node.wireguard
    base: WireguardConfig | None = defaults.hub.wireguard

    if override is None:
        return base
    if override.enabled is False:
        return None

    # Merge override on top of base
    subnet = override.subnet or (base.subnet if base else None)
    if subnet is None:
        raise DeriveError(f"Node {node.id!r}: wireguard.subnet must be set (no default configured)")

    return WireguardConfig(
        port=override.port or (base.port if base else 443),
        mtu=override.mtu or (base.mtu if base else 1420),
        subnet=subnet,
        keepalive=override.keepalive if override.keepalive is not None else (base.keepalive if base else 0),
        kernel_mode=override.kernel_mode if override.kernel_mode is not None else (base.kernel_mode if base else False),
    )


def get_hub_wireguard_peers(
    users: list[User],
    ns: Namespace,
    subnet: str,
    reality_private_key: str,
    keepalive: int = 0,
) -> list[dict]:
    """Peers for hub wireguard inbound.

    Each peer keypair is derived from its identity UUID and hub reality private key.
    """

    peers = []
    for alloc in iter_hub_wireguard_allocs(users, ns, subnet):
        _priv, pub = derive_user_wireguard_keypair(reality_private_key, alloc.identity_uuid, ns.name)
        peers.append(
            {
                "email": alloc.email,
                "publicKey": pub,
                "allowedIPs": [alloc.address],
                "keepAlive": keepalive,
            }
        )
    return peers


@dataclass(frozen=True)
class WireguardContext(InboundContext):
    config: WireguardConfig
    peers: list[dict]
    secret_key: str  # node reality private key re-encoded to standard base64


class WireguardSpec(InboundSpec[WireguardContext]):
    access_type: ClassVar[AccessType] = AccessType.WIREGUARD
    roles: ClassVar[frozenset[RegionType]] = frozenset({RegionType.HUB})
    context_type = WireguardContext

    def build_context(self, env: InboundEnv) -> WireguardContext | None:
        wireguard = resolve_node_wireguard(env.node, env.config.defaults)
        if wireguard is None:
            return None
        peers = get_hub_wireguard_peers(
            env.config.users,
            env.ns,
            wireguard.subnet,
            env.node_keys.reality_private_key,
            keepalive=wireguard.keepalive,
        )
        if not peers:
            return None
        return WireguardContext(
            config=wireguard,
            peers=peers,
            secret_key=x25519_urlsafe_to_std(env.node_keys.reality_private_key),
        )

    def fragment(self, ctx: WireguardContext, shared: SharedContext) -> dict:
        return {
            "tag": "wireguard-in",
            "listen": "0.0.0.0",  # noqa: S104
            "port": ctx.config.port,
            "protocol": XrayProtocol.WIREGUARD,
            "settings": {
                "secretKey": ctx.secret_key,
                "mtu": ctx.config.mtu,
                "peers": ctx.peers,
            },
            "sniffing": make_sniffing(shared.route_only),
        }


WIREGUARD_SPEC = WireguardSpec()
