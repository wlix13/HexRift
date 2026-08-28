import hashlib

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519
from cryptography.x509.oid import NameOID, SignatureAlgorithmOID

from hexrift.components.derive.hysteria import (
    HysteriaCert,
    derive_hysteria_certificate,
    derive_hysteria_endpoint,
    derive_hysteria_masquerade_url,
    derive_hysteria_obfs_password,
)
from hexrift.components.schema.models.regions import HysteriaCertificate, HysteriaConfig
from hexrift.components.schema.models.shared import RealityConfig
from hexrift.constants import HysteriaKeyType


_PRIV = "mZ0iHOiFoN3JfGgq_7D7GwvEcMwqJEbT7T5VyqK7Rnk"
_REALITY = RealityConfig(dest="vk.com:443", xhttp_path="/x/")
_ED25519_PIN = "43:E7:FF:B3:6A:89:C9:6A:34:81:62:0D:46:57:C6:FD:75:1D:F6:80:96:B6:84:3E:E7:04:40:8A:89:B4:7F:45"


def _x509(cert: HysteriaCert) -> x509.Certificate:
    return x509.load_pem_x509_certificate(cert.cert_pem.encode())


class TestDeriveHysteriaCertificate:
    @pytest.mark.parametrize("key_type", list(HysteriaKeyType))
    def test_deterministic_and_pin_is_der_sha256(self, key_type: HysteriaKeyType):
        a = derive_hysteria_certificate(_PRIV, "vk.com", "t.ns", key_type)
        assert a == derive_hysteria_certificate(_PRIV, "vk.com", "t.ns", key_type)
        cert = _x509(a)
        der = cert.public_bytes(serialization.Encoding.DER)
        assert a.pin == ":".join(f"{b:02X}" for b in hashlib.sha256(der).digest())
        assert cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value == "vk.com"
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        assert san.get_values_for_type(x509.DNSName) == ["vk.com"]
        assert serialization.load_pem_private_key(a.key_pem.encode(), None).public_key() == cert.public_key()

    def test_ed25519_derivation_predates_key_type(self):
        assert derive_hysteria_certificate(_PRIV, "vk.com", "t.ns", HysteriaKeyType.ED25519).pin == _ED25519_PIN

    def test_key_type_selects_algorithm(self):
        ed = _x509(derive_hysteria_certificate(_PRIV, "vk.com", "t.ns", HysteriaKeyType.ED25519))
        assert isinstance(ed.public_key(), ed25519.Ed25519PublicKey)
        assert ed.signature_algorithm_oid == SignatureAlgorithmOID.ED25519
        p256 = _x509(derive_hysteria_certificate(_PRIV, "vk.com", "t.ns", HysteriaKeyType.ECDSA_P256))
        public = p256.public_key()
        assert isinstance(public, ec.EllipticCurvePublicKey) and public.curve.name == "secp256r1"
        assert p256.signature_algorithm_oid == SignatureAlgorithmOID.ECDSA_WITH_SHA256

    def test_ip_literal_sni_gets_ip_san(self):
        cert = _x509(derive_hysteria_certificate(_PRIV, "203.0.113.7", "t.ns", HysteriaKeyType.ED25519))
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        assert [str(ip) for ip in san.get_values_for_type(x509.IPAddress)] == ["203.0.113.7"]

    def test_sni_key_and_key_type_all_change_the_pin(self):
        base = derive_hysteria_certificate(_PRIV, "vk.com", "t.ns", HysteriaKeyType.ED25519).pin
        assert derive_hysteria_certificate(_PRIV, "ok.ru", "t.ns", HysteriaKeyType.ED25519).pin != base
        other_key = "UH7E3J0NAZgzdhkkZ6nZlZ1fsQ6DvTOSf-3GDy6nCUQ"
        assert derive_hysteria_certificate(other_key, "vk.com", "t.ns", HysteriaKeyType.ED25519).pin != base
        assert derive_hysteria_certificate(_PRIV, "vk.com", "t.ns", HysteriaKeyType.ECDSA_P256).pin != base


class TestDeriveHysteriaEndpoint:
    def test_defaults_sni_from_reality_and_pins_derived_ed25519_cert(self):
        ep = derive_hysteria_endpoint(HysteriaConfig(), _REALITY, _PRIV, "t.ns")
        assert ep.sni == "vk.com"
        assert ep.key_type is HysteriaKeyType.ED25519 and not ep.chrome_parrot
        assert ep.pin == derive_hysteria_certificate(_PRIV, "vk.com", "t.ns", HysteriaKeyType.ED25519).pin
        assert ep.obfs_password is None

    def test_key_type_selects_the_served_cert(self):
        ep = derive_hysteria_endpoint(HysteriaConfig(key_type=HysteriaKeyType.ECDSA_P256), _REALITY, _PRIV, "t.ns")
        cert = derive_hysteria_certificate(_PRIV, "vk.com", "t.ns", HysteriaKeyType.ECDSA_P256)
        assert ep.key_type is HysteriaKeyType.ECDSA_P256
        assert ep.pin == cert.pin
        assert ep.certificates == [{"certificate": cert.cert_pem.splitlines(), "key": cert.key_pem.splitlines()}]

    def test_operator_certificate_disables_pin(self):
        hy = HysteriaConfig(sni="hub.example.com", certificate=HysteriaCertificate(cert_file="/c", key_file="/k"))
        ep = derive_hysteria_endpoint(hy, _REALITY, _PRIV, "t.ns")
        assert ep.sni == "hub.example.com"
        assert ep.certificates == [{"certificateFile": "/c", "keyFile": "/k"}]
        assert ep.pin is None
        assert ep.key_type is None and ep.chrome_parrot  # undeclared: assumed CA-issued, not Ed25519

    def test_operator_certificate_key_type_is_a_declaration(self):
        cert = HysteriaCertificate(cert_file="/c", key_file="/k")
        hy = HysteriaConfig(sni="hub.example.com", certificate=cert, key_type=HysteriaKeyType.ECDSA_P256)
        ep = derive_hysteria_endpoint(hy, _REALITY, _PRIV, "t.ns")
        assert ep.key_type is HysteriaKeyType.ECDSA_P256
        assert ep.certificates == [{"certificateFile": "/c", "keyFile": "/k"}]

    def test_operator_certificate_pin_is_the_trust_anchor(self):
        cert = HysteriaCertificate(cert_file="/c", key_file="/k", pin_sha256="ab" * 32)
        ep = derive_hysteria_endpoint(HysteriaConfig(sni="hub.example.com", certificate=cert), _REALITY, _PRIV, "t.ns")
        assert ep.pin == ":".join(["AB"] * 32)

    def test_obfs_password_derived_when_enabled(self):
        ep = derive_hysteria_endpoint(HysteriaConfig(obfs=True), _REALITY, _PRIV, "t.ns")
        assert ep.obfs_password == derive_hysteria_obfs_password(_PRIV, "t.ns")
        assert ep.obfs_password != derive_hysteria_obfs_password(_PRIV, "other.ns")


def test_masquerade_url_defaults_to_sni():
    assert derive_hysteria_masquerade_url(HysteriaConfig(), "vk.com") == "https://vk.com/"
    assert derive_hysteria_masquerade_url(HysteriaConfig(masquerade_url="https://a.b/c"), "vk.com") == "https://a.b/c"
