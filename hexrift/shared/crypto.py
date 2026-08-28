"""Pure x25519 / Ed25519 / HMAC / base64 encoding helpers."""

from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
from datetime import datetime

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from cryptography.x509.oid import NameOID


SECP256R1_ORDER = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551
"""Group order of the P-256 curve."""

type CertPrivateKey = Ed25519PrivateKey | ec.EllipticCurvePrivateKey
"""Key types `self_signed_cert` can sign with."""


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


def ed25519_key_from_seed(seed: bytes) -> Ed25519PrivateKey:
    """Ed25519 private key whose scalar seed is first 32 bytes of `seed`."""

    return Ed25519PrivateKey.from_private_bytes(seed[:32])


def ecdsa_p256_key_from_seed(seed: bytes) -> ec.EllipticCurvePrivateKey:
    """ECDSA P-256 private key whose scalar is first 32 bytes of `seed` reduced into [1, order - 1]."""

    scalar = int.from_bytes(seed[:32], "big") % (SECP256R1_ORDER - 1) + 1
    return ec.derive_private_key(scalar, ec.SECP256R1())


def cert_serial_from_seed(seed: bytes) -> int:
    """Positive 159-bit odd serial derived from `seed`."""

    return (int.from_bytes(hashlib.sha256(seed).digest()[:20], "big") >> 1) | 1


def self_signed_cert(
    key: CertPrivateKey,
    common_name: str,
    not_before: datetime,
    not_after: datetime,
    *,
    serial: int,
) -> tuple[str, str, bytes]:
    """Deterministic self-signed leaf for `common_name`: (cert PEM, PKCS#8 key PEM, DER SHA-256)."""

    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    try:
        san: x509.GeneralName = x509.IPAddress(ipaddress.ip_address(common_name))
    except ValueError:
        san = x509.DNSName(common_name)
    builder = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(serial)
        .not_valid_before(not_before)
        .not_valid_after(not_after)
        .add_extension(x509.SubjectAlternativeName([san]), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
    )
    if isinstance(key, Ed25519PrivateKey):
        cert = builder.sign(key, algorithm=None)
    else:
        cert = builder.sign(key, hashes.SHA256(), ecdsa_deterministic=True)
    key_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    der = cert.public_bytes(serialization.Encoding.DER)
    return cert.public_bytes(serialization.Encoding.PEM).decode(), key_pem.decode(), hashlib.sha256(der).digest()
