import base64
import hashlib
import hmac
import ipaddress
from collections.abc import Iterator
from dataclasses import dataclass
from uuid import UUID

from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from jinja2 import Environment, PackageLoader

from hexrift.components.derive.identity import Namespace
from hexrift.components.keys.reality import urlsafe_b64decode_unpadded, x25519_raw_bytes
from hexrift.components.schema.models.users import User
from hexrift.constants import AccessType
from hexrift.errors import DeriveError


@dataclass(frozen=True)
class WireguardPeer:
    """Single WireGuard peer: identity, allocated address, and kind."""

    email: str
    identity_uuid: UUID
    address: str
    kind: str
    label: str | None = None


def _derive_x25519_keypair_std(seed: bytes) -> tuple[str, str]:
    """Deterministically derive x25519 keypair from 32-byte seed."""

    private, public = x25519_raw_bytes(X25519PrivateKey.from_private_bytes(seed[:32]))
    return base64.b64encode(private).decode(), base64.b64encode(public).decode()


def derive_user_wireguard_keypair(reality_private_key: str, identity_uuid: UUID, ns_name: str) -> tuple[str, str]:
    """Deterministically derive WireGuard keypair for one identity (user/server/guest)."""

    key = urlsafe_b64decode_unpadded(reality_private_key)
    msg = f"{identity_uuid}.wireguard.{ns_name}".encode()
    seed = hmac.new(key, msg, hashlib.sha256).digest()
    return _derive_x25519_keypair_std(seed)


def iter_hub_wireguard_allocs(users: list[User], ns: Namespace, subnet: str) -> Iterator[WireguardPeer]:
    """Allocate hub WireGuard peers (user, server, guests) in order; first host reserved for server."""

    network = ipaddress.ip_network(subnet, strict=False)
    hosts = network.hosts()
    next(hosts, None)  # reserve first address for server

    def allocate(email: str, identity_uuid: UUID, kind: str, label: str | None = None) -> WireguardPeer:
        address = next(hosts, None)
        if address is None:
            raise DeriveError(f"wireguard subnet {subnet!r} does not have enough addresses for all peers")
        return WireguardPeer(
            email=email,
            identity_uuid=identity_uuid,
            address=f"{address}/{address.max_prefixlen}",
            kind=kind,
            label=label,
        )

    for u in users:
        if AccessType.WIREGUARD not in u.access:
            continue
        user_base = ns.user_uuid(u.username, override=u.uuid)
        yield allocate(ns.user_email(u.username), user_base, "user")
        if AccessType.SERVER in u.access:
            yield allocate(ns.server_email(u.username), ns.server_uuid(u.username, user_base=user_base), "server")
        for label in u.guests:
            yield allocate(
                ns.guest_email(label, u.username),
                ns.guest_uuid(label, u.username, user_base=user_base),
                "guest",
                label=label,
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


_env = Environment(
    loader=PackageLoader("hexrift", "templates/wireguard"),
    keep_trailing_newline=True,
    trim_blocks=True,
    lstrip_blocks=True,
    autoescape=False,  # noqa: S701
)


def render_wireguard_client_conf(
    *,
    private_key: str,
    address: str,
    dns: list[str],
    mtu: int,
    server_public_key: str,
    endpoint: str,
    allowed_ips: list[str],
    keepalive: int,
) -> str:
    template = _env.get_template("client.conf.j2")
    return template.render(
        private_key=private_key,
        address=address,
        dns=dns,
        mtu=mtu,
        server_public_key=server_public_key,
        endpoint=endpoint,
        allowed_ips=allowed_ips,
        keepalive=keepalive,
    )
