import base64

from hexrift.shared.crypto import (
    generate_x25519_keypair,
    urlsafe_b64decode_unpadded,
    urlsafe_b64encode_unpadded,
    x25519_keypair_from_seed,
)


class TestGenerateX25519Keypair:
    def test_returns_two_strings(self):
        result = generate_x25519_keypair()
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert all(isinstance(s, str) for s in result)

    def test_private_key_decodes_to_32_bytes(self):
        priv, _ = generate_x25519_keypair()
        raw = urlsafe_b64decode_unpadded(priv)
        assert len(raw) == 32

    def test_public_key_decodes_to_32_bytes(self):
        _, pub = generate_x25519_keypair()
        raw = urlsafe_b64decode_unpadded(pub)
        assert len(raw) == 32

    def test_no_padding_in_output(self):
        priv, pub = generate_x25519_keypair()
        assert "=" not in priv
        assert "=" not in pub

    def test_url_safe_characters(self):
        """No + or / (standard base64 chars) should appear."""

        priv, pub = generate_x25519_keypair()
        assert "+" not in priv and "/" not in priv
        assert "+" not in pub and "/" not in pub

    def test_keys_are_unique(self):
        k1 = generate_x25519_keypair()
        k2 = generate_x25519_keypair()
        assert k1[0] != k2[0]
        assert k1[1] != k2[1]


class TestUrlsafeB64EncodeUnpadded:
    def test_matches_manual_idiom(self):
        data = bytes(range(40))
        assert urlsafe_b64encode_unpadded(data) == base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    def test_no_padding(self):
        # 1 byte → 2 base64 chars + 2 pad chars normally; padding must be stripped
        assert "=" not in urlsafe_b64encode_unpadded(b"\x00")

    def test_round_trips_with_decode(self):
        data = b"\x00\x11\x22\xff arbitrary bytes \x99"
        assert urlsafe_b64decode_unpadded(urlsafe_b64encode_unpadded(data)) == data

    def test_url_safe_alphabet(self):
        # 0xFB,0xFF,0xBF encodes to a sequence containing '+'/'/' under standard base64
        encoded = urlsafe_b64encode_unpadded(b"\xfb\xff\xbf")
        assert "+" not in encoded and "/" not in encoded


class TestX25519KeypairFromSeed:
    def test_deterministic_for_fixed_seed(self):
        seed = bytes(range(32))
        assert x25519_keypair_from_seed(seed) == x25519_keypair_from_seed(seed)

    def test_distinct_seeds_distinct_keys(self):
        a = x25519_keypair_from_seed(bytes([0] * 32))
        b = x25519_keypair_from_seed(bytes([1] * 32))
        assert a != b

    def test_returns_standard_base64_32_byte_keys(self):
        priv, pub = x25519_keypair_from_seed(bytes(range(32)))
        assert len(base64.b64decode(priv)) == 32
        assert len(base64.b64decode(pub)) == 32

    def test_uses_only_first_32_bytes_of_seed(self):
        seed = bytes(range(32))
        assert x25519_keypair_from_seed(seed) == x25519_keypair_from_seed(seed + b"ignored tail")
