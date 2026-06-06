import base64
import hashlib
import hmac
import ipaddress
from uuid import UUID

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

from hexrift.components.derive.identity import Namespace
from hexrift.components.schema.models.users import User
from hexrift.constants import AccessType


def _derive_x25519_keypair_std(seed: bytes) -> tuple[str, str]:
    """Deterministically derive x25519 keypair from 32-byte seed."""

    private_key = X25519PrivateKey.from_private_bytes(seed[:32])
    private = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return base64.b64encode(private).decode(), base64.b64encode(public).decode()


def derive_user_wireguard_keypair(reality_private_key: str, user_base: UUID, ns_name: str) -> tuple[str, str]:
    """Deterministically derive user's WireGuard keypair."""

    padding = "=" * (-len(reality_private_key) % 4)
    key = base64.urlsafe_b64decode(reality_private_key + padding)
    msg = f"{user_base}.wireguard.{ns_name}".encode()
    seed = hmac.new(key, msg, hashlib.sha256).digest()
    return _derive_x25519_keypair_std(seed)


def get_hub_wireguard_peers(
    users: list[User], ns: Namespace, subnet: str, reality_private_key: str, keepalive: int = 0
) -> list[dict]:
    """Peers for the hub wireguard inbound.

    Each peer's keypair is derived from the user's UUID and the hub's reality private key.
    """

    network = ipaddress.ip_network(subnet, strict=False)
    hosts = network.hosts()
    next(hosts, None)  # reserve first address for server

    peers = []
    for u in users:
        if AccessType.WIREGUARD not in u.access:
            continue
        address = next(hosts, None)
        if address is None:
            raise ValueError(f"wireguard subnet {subnet!r} has not enoght addresses for all peers")
        user_base = ns.user_uuid(u.username, override=u.uuid)
        _priv, pub = derive_user_wireguard_keypair(reality_private_key, user_base, ns.name)
        peers.append(
            {
                "email": ns.user_email(u.username),
                "publicKey": pub,
                "allowedIPs": [f"{address}/{address.max_prefixlen}"],
                "keepAlive": keepalive,
            }
        )
    return peers
