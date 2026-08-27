import hashlib

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.x509.oid import NameOID

from hexrift.components.derive.hysteria import (
    derive_hysteria_certificate,
    derive_hysteria_endpoint,
    derive_hysteria_masquerade_url,
    derive_hysteria_obfs_password,
)
from hexrift.components.schema.models.regions import HysteriaCertificate, HysteriaConfig
from hexrift.components.schema.models.shared import RealityConfig


_PRIV = "mZ0iHOiFoN3JfGgq_7D7GwvEcMwqJEbT7T5VyqK7Rnk"
_REALITY = RealityConfig(dest="vk.com:443", xhttp_path="/x/")


class TestDeriveHysteriaCertificate:
    def test_deterministic_and_pin_is_der_sha256(self):
        a = derive_hysteria_certificate(_PRIV, "vk.com", "t.ns")
        assert a == derive_hysteria_certificate(_PRIV, "vk.com", "t.ns")
        cert = x509.load_pem_x509_certificate(a.cert_pem.encode())
        der = cert.public_bytes(serialization.Encoding.DER)
        assert a.pin == ":".join(f"{b:02X}" for b in hashlib.sha256(der).digest())
        assert cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value == "vk.com"
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        assert san.get_values_for_type(x509.DNSName) == ["vk.com"]

    def test_ip_literal_sni_gets_ip_san(self):
        cert = x509.load_pem_x509_certificate(
            derive_hysteria_certificate(_PRIV, "203.0.113.7", "t.ns").cert_pem.encode()
        )
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        assert [str(ip) for ip in san.get_values_for_type(x509.IPAddress)] == ["203.0.113.7"]

    def test_sni_and_key_both_change_the_pin(self):
        base = derive_hysteria_certificate(_PRIV, "vk.com", "t.ns").pin
        assert derive_hysteria_certificate(_PRIV, "ok.ru", "t.ns").pin != base
        assert derive_hysteria_certificate("UH7E3J0NAZgzdhkkZ6nZlZ1fsQ6DvTOSf-3GDy6nCUQ", "vk.com", "t.ns").pin != base


class TestDeriveHysteriaEndpoint:
    def test_defaults_sni_from_reality_and_pins_derived_cert(self):
        ep = derive_hysteria_endpoint(HysteriaConfig(), _REALITY, _PRIV, "t.ns")
        assert ep.sni == "vk.com"
        assert ep.pin == derive_hysteria_certificate(_PRIV, "vk.com", "t.ns").pin
        assert ep.obfs_password is None

    def test_operator_certificate_disables_pin(self):
        hy = HysteriaConfig(sni="hub.example.com", certificate=HysteriaCertificate(cert_file="/c", key_file="/k"))
        ep = derive_hysteria_endpoint(hy, _REALITY, _PRIV, "t.ns")
        assert ep.sni == "hub.example.com"
        assert ep.certificates == [{"certificateFile": "/c", "keyFile": "/k"}]
        assert ep.pin is None

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
