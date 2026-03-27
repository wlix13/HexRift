"""Build matched decryption/encryption key string pairs.

The handshake method is always mlkem768x25519plus (the only method in Xray).
The auth key (last block) can be either:
  - x25519:  32-byte private key (server) / 32-byte public key (client)
  - mlkem768: 64-byte seed (server) / 1184-byte encapsulation key (client)
Xray distinguishes them purely by the byte length of the decoded last block.
"""

from __future__ import annotations

import base64
import os

from kyber_py.ml_kem import ML_KEM_768

from hexrift.components.keys.reality import generate_x25519_keypair
from hexrift.constants import HANDSHAKE_METHOD, AuthMethod


def _mlkem768_auth() -> tuple[str, str]:
    """Generate ML-KEM-768 auth key material from fresh 64-byte seed.

    Returns:
        (seed_b64url, encap_key_b64url)
        seed (64 bytes)        — server decryption: Xray re-derives the decap key at runtime
        encap_key (1184 bytes) — client encryption: the ML-KEM-768 encapsulation (public) key
    """

    seed = os.urandom(64)
    ek, _ = ML_KEM_768.key_derive(seed)
    return (
        base64.urlsafe_b64encode(seed).rstrip(b"=").decode(),
        base64.urlsafe_b64encode(ek).rstrip(b"=").decode(),
    )


def generate_auth_keypair(
    auth: AuthMethod,
    mode: str,
    session_time: str,
    padding: str | None = None,
) -> tuple[str, str]:
    """Generate a matched decryption + encryption key string pair.

    Args:
        auth: "mlkem768" for post-quantum ML-KEM-768 auth keys.
              "x25519" for classical X25519 auth keys.
        mode: encryption mode block (e.g. "native").
        session_time: session resumption ticket validity (e.g. "600s").
        padding: optional padding block(s) inserted before the auth key.

    Returns:
        (decryption_string, encryption_string)
        decryption: mlkem768x25519plus.{mode}.{session_time}[.{padding}].{key_b64}   — server inbound
        encryption: mlkem768x25519plus.{mode}.0rtt.{key_b64}                         — client outbound
    """

    if auth == AuthMethod.MLKEM768:
        server_b64, client_b64 = _mlkem768_auth()
    else:
        server_b64, client_b64 = generate_x25519_keypair()

    dec_parts = [HANDSHAKE_METHOD, mode, session_time]
    if padding:
        dec_parts.append(padding)
    dec_parts.append(server_b64)

    return ".".join(dec_parts), f"{HANDSHAKE_METHOD}.{mode}.0rtt.{client_b64}"
