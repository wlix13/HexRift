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
