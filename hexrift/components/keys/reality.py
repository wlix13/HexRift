"""x25519 keypair generation for Reality TLS."""

from __future__ import annotations

import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey


def urlsafe_b64decode_unpadded(value: str) -> bytes:
    """Decode URL-safe base64 with stripped padding."""

    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def x25519_raw_bytes(private_key: X25519PrivateKey) -> tuple[bytes, bytes]:
    """Return raw (private, public) bytes of x25519 key."""

    private = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return private, public


def generate_x25519_keypair() -> tuple[str, str]:
    """Generate an x25519 keypair.

    Returns:
        (private_key_b64url, public_key_b64url) — raw 32-byte keys, URL-safe base64, no padding.
    """

    private, public = x25519_raw_bytes(X25519PrivateKey.generate())
    priv_b64 = base64.urlsafe_b64encode(private).rstrip(b"=").decode()
    pub_b64 = base64.urlsafe_b64encode(public).rstrip(b"=").decode()
    return priv_b64, pub_b64


def x25519_urlsafe_to_std(key_b64url: str) -> str:
    """Re-encode a URL-safe, unpadded x25519 key to standard base64."""

    return base64.b64encode(urlsafe_b64decode_unpadded(key_b64url)).decode()
