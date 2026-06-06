"""x25519 keypair generation for Reality TLS."""

from __future__ import annotations

import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey


def generate_x25519_keypair() -> tuple[str, str]:
    """Generate an x25519 keypair.

    Returns:
        (private_key_b64url, public_key_b64url) — raw 32-byte keys, URL-safe base64, no padding.
    """

    private_key = X25519PrivateKey.generate()
    private = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    priv_b64 = base64.urlsafe_b64encode(private).rstrip(b"=").decode()
    pub_b64 = base64.urlsafe_b64encode(public).rstrip(b"=").decode()
    return priv_b64, pub_b64


def x25519_urlsafe_to_std(key_b64url: str) -> str:
    """Re-encode a URL-safe, unpadded x25519 key to standard base64."""

    padding = "=" * (-len(key_b64url) % 4)
    raw = base64.urlsafe_b64decode(key_b64url + padding)
    return base64.b64encode(raw).decode()


def derive_x25519_keypair_std(seed: bytes) -> tuple[str, str]:
    """Deterministically derive an x25519 keypair from a 32-byte seed."""

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
