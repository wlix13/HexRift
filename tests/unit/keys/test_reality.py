import base64

from hexrift.components.keys.reality import generate_x25519_keypair


def test_returns_two_strings():
    result = generate_x25519_keypair()
    assert isinstance(result, tuple)
    assert len(result) == 2
    assert all(isinstance(s, str) for s in result)


def test_private_key_decodes_to_32_bytes():
    priv, _ = generate_x25519_keypair()
    raw = base64.urlsafe_b64decode(priv + "==")
    assert len(raw) == 32


def test_public_key_decodes_to_32_bytes():
    _, pub = generate_x25519_keypair()
    raw = base64.urlsafe_b64decode(pub + "==")
    assert len(raw) == 32


def test_no_padding_in_output():
    priv, pub = generate_x25519_keypair()
    assert "=" not in priv
    assert "=" not in pub


def test_url_safe_characters():
    """No + or / (standard base64 chars) should appear."""

    priv, pub = generate_x25519_keypair()
    assert "+" not in priv and "/" not in priv
    assert "+" not in pub and "/" not in pub


def test_keys_are_unique():
    k1 = generate_x25519_keypair()
    k2 = generate_x25519_keypair()
    assert k1[0] != k2[0]
    assert k1[1] != k2[1]
