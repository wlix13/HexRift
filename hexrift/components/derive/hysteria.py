"""Deterministic Hysteria material derived from node keys."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from typing import Final

from hexrift.components.derive.defaults import derive_server_names
from hexrift.components.schema.models.fields import format_cert_pin
from hexrift.components.schema.models.regions import HysteriaConfig
from hexrift.components.schema.models.shared import RealityConfig
from hexrift.constants import HYSTERIA_DERIVED_KEY_TYPE, HysteriaKeyType
from hexrift.shared.crypto import (
    CertPrivateKey,
    cert_serial_from_seed,
    ecdsa_p256_key_from_seed,
    ed25519_key_from_seed,
    hmac_from_reality_key,
    self_signed_cert,
    urlsafe_b64encode_unpadded,
)
from hexrift.shared.hysteria import pem_lines


HYSTERIA_CERT_NOT_BEFORE = datetime(2020, 1, 1, tzinfo=UTC)
HYSTERIA_CERT_NOT_AFTER = datetime(2049, 12, 31, 23, 59, 59, tzinfo=UTC)

_CERT_KEY_FROM_SEED: Final[Mapping[HysteriaKeyType, Callable[[bytes], CertPrivateKey]]] = {
    HysteriaKeyType.ED25519: ed25519_key_from_seed,
    HysteriaKeyType.ECDSA_P256: ecdsa_p256_key_from_seed,
}

_CERT_SEED_LABEL: Final[Mapping[HysteriaKeyType, str]] = {
    HysteriaKeyType.ED25519: "hysteria-tls",
    HysteriaKeyType.ECDSA_P256: "hysteria-tls-ecdsa-p256",
}


@dataclass(frozen=True)
class HysteriaCert:
    """Self-signed leaf a node presents plus the pin clients verify it by."""

    cert_pem: str
    key_pem: str
    pin: str  # SHA-256 of the DER, AA:BB:… form


def derive_hysteria_obfs_password(reality_private_key: str, ns_name: str) -> str:
    return urlsafe_b64encode_unpadded(hmac_from_reality_key(reality_private_key, f"hysteria-obfs.{ns_name}"))


@lru_cache(maxsize=128)
def derive_hysteria_certificate(
    reality_private_key: str,
    sni: str,
    ns_name: str,
    key_type: HysteriaKeyType,
) -> HysteriaCert:
    seed = hmac_from_reality_key(reality_private_key, f"{_CERT_SEED_LABEL[key_type]}.{ns_name}")
    cert_pem, key_pem, digest = self_signed_cert(
        _CERT_KEY_FROM_SEED[key_type](seed),
        sni,
        HYSTERIA_CERT_NOT_BEFORE,
        HYSTERIA_CERT_NOT_AFTER,
        serial=cert_serial_from_seed(seed),
    )
    return HysteriaCert(cert_pem=cert_pem, key_pem=key_pem, pin=format_cert_pin(digest))


def derive_hysteria_sni(hysteria: HysteriaConfig, reality: RealityConfig) -> str:
    return hysteria.sni if hysteria.sni is not None else derive_server_names(reality)[0]


def derive_hysteria_masquerade_url(hysteria: HysteriaConfig, sni: str) -> str:
    return hysteria.masquerade_url if hysteria.masquerade_url is not None else f"https://{sni}/"


@dataclass(frozen=True)
class HysteriaEndpoint:
    """What a node's Hysteria listener serves and what peers need to dial it."""

    sni: str
    certificates: list[dict]  # tlsSettings.certificates entries
    key_type: HysteriaKeyType | None  # None: operator cert with no declared algorithm
    obfs_password: str | None
    pin: str | None  # None: peers verify by CA roots

    @property
    def chrome_parrot(self) -> bool:
        return self.key_type is None or self.key_type.supports_chrome_parrot


def derive_hysteria_endpoint(
    hysteria: HysteriaConfig,
    reality: RealityConfig,
    reality_private_key: str,
    ns_name: str,
) -> HysteriaEndpoint:
    sni = derive_hysteria_sni(hysteria, reality)
    if hysteria.certificate is not None:
        key_type = hysteria.key_type  # the operator's declaration, if any
        certificates = [{"certificateFile": hysteria.certificate.cert_file, "keyFile": hysteria.certificate.key_file}]
        pin = hysteria.certificate.pin_sha256
    else:
        key_type = hysteria.key_type if hysteria.key_type is not None else HYSTERIA_DERIVED_KEY_TYPE
        cert = derive_hysteria_certificate(reality_private_key, sni, ns_name, key_type)
        certificates = [{"certificate": pem_lines(cert.cert_pem), "key": pem_lines(cert.key_pem)}]
        pin = cert.pin
    return HysteriaEndpoint(
        sni=sni,
        certificates=certificates,
        key_type=key_type,
        obfs_password=derive_hysteria_obfs_password(reality_private_key, ns_name) if hysteria.obfs else None,
        pin=pin,
    )
