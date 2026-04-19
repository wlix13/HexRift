import base64

from hexrift.components.keys.decryption import generate_auth_keypair
from hexrift.constants import AuthMethod


def _decode_last_block(key_string: str) -> bytes:
    """Decode the last dot-separated block of a key string."""

    last = key_string.rsplit(".", 1)[-1]
    return base64.urlsafe_b64decode(last + "==")


class TestMlkem768Auth:
    def test_decryption_prefix(self):
        dec, _ = generate_auth_keypair(AuthMethod.MLKEM768, "native", "600s")
        assert dec.startswith("mlkem768x25519plus.native.600s.")

    def test_encryption_format(self):
        _, enc = generate_auth_keypair(AuthMethod.MLKEM768, "native", "600s")
        assert enc.startswith("mlkem768x25519plus.native.0rtt.")

    def test_server_key_is_64_bytes(self):
        dec, _ = generate_auth_keypair(AuthMethod.MLKEM768, "native", "600s")
        raw = _decode_last_block(dec)
        assert len(raw) == 64

    def test_client_key_is_1184_bytes(self):
        _, enc = generate_auth_keypair(AuthMethod.MLKEM768, "native", "600s")
        raw = _decode_last_block(enc)
        assert len(raw) == 1184

    def test_with_padding_in_decryption(self):
        dec, _ = generate_auth_keypair(AuthMethod.MLKEM768, "native", "600s", padding="1024-2048")
        assert "1024-2048" in dec

    def test_without_padding_not_in_decryption(self):
        dec, _ = generate_auth_keypair(AuthMethod.MLKEM768, "native", "600s")
        parts = dec.split(".")
        # Should be: method.mode.session_time.key  (4 parts)
        assert len(parts) == 4
        assert parts[:3] == ["mlkem768x25519plus", "native", "600s"]

    def test_unique_keys(self):
        dec1, enc1 = generate_auth_keypair(AuthMethod.MLKEM768, "native", "600s")
        dec2, enc2 = generate_auth_keypair(AuthMethod.MLKEM768, "native", "600s")
        assert dec1 != dec2
        assert enc1 != enc2


class TestX25519Auth:
    def test_decryption_prefix(self):
        dec, _ = generate_auth_keypair(AuthMethod.X25519, "native", "600s")
        assert dec.startswith("mlkem768x25519plus.native.600s.")

    def test_encryption_format(self):
        _, enc = generate_auth_keypair(AuthMethod.X25519, "native", "600s")
        assert enc.startswith("mlkem768x25519plus.native.0rtt.")

    def test_server_key_is_32_bytes(self):
        dec, _ = generate_auth_keypair(AuthMethod.X25519, "native", "600s")
        raw = _decode_last_block(dec)
        assert len(raw) == 32

    def test_client_key_is_32_bytes(self):
        _, enc = generate_auth_keypair(AuthMethod.X25519, "native", "600s")
        raw = _decode_last_block(enc)
        assert len(raw) == 32

    def test_unique_keys(self):
        dec1, enc1 = generate_auth_keypair(AuthMethod.X25519, "native", "600s")
        dec2, enc2 = generate_auth_keypair(AuthMethod.X25519, "native", "600s")
        assert dec1 != dec2
        assert enc1 != enc2
