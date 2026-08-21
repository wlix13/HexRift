"""Pure x25519 / HMAC / base64 encoding helpers."""

from __future__ import annotations

import base64
import hashlib
import hmac

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey


def urlsafe_b64decode_unpadded(value: str) -> bytes:
    """Decode URL-safe base64 with stripped padding."""

    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def urlsafe_b64encode_unpadded(data: bytes) -> str:
    """Encode bytes as URL-safe base64 with stripped padding."""

    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def hmac_from_reality_key(reality_private_key: str, message: str) -> bytes:
    """HMAC-SHA256 of `message` keyed by a node's raw reality private key."""

    return hmac.new(urlsafe_b64decode_unpadded(reality_private_key), message.encode(), hashlib.sha256).digest()


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


def x25519_urlsafe_to_std(key_b64url: str) -> str:
    """Re-encode URL-safe, unpadded x25519 key to standard base64."""

    return base64.b64encode(urlsafe_b64decode_unpadded(key_b64url)).decode()


def generate_x25519_keypair() -> tuple[str, str]:
    """Generate random x25519 keypair.

    Returns (private, public) raw 32-byte keys as URL-safe base64, no padding.
    """

    private, public = x25519_raw_bytes(X25519PrivateKey.generate())
    return urlsafe_b64encode_unpadded(private), urlsafe_b64encode_unpadded(public)


def x25519_keypair_from_seed(seed: bytes) -> tuple[str, str]:
    """Deterministically derive x25519 keypair from 32-byte seed.

    Returns (private, public) as standard base64 (not URL-safe).
    """

    private, public = x25519_raw_bytes(X25519PrivateKey.from_private_bytes(seed[:32]))
    return base64.b64encode(private).decode(), base64.b64encode(public).decode()
