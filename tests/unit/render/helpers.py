from typing import Any

from hexrift.components.schema.models.defaults import ObservatoryConfig
from hexrift.components.schema.models.regions import WireguardConfig, XdnsConfig
from hexrift.components.schema.models.shared import RealityFallbackLimits
from hexrift.constants import AccessType
from hexrift.inbounds.base import InboundContext, SharedContext
from hexrift.inbounds.cdn import CdnContext
from hexrift.inbounds.context import ExitContext, HubContext
from hexrift.inbounds.proxy import ProxyContext
from hexrift.inbounds.wireguard import WireguardContext
from hexrift.inbounds.xdns import XdnsContext
from hexrift.inbounds.xhttp import XhttpContext


def make_shared(**overrides: Any) -> SharedContext:
    defaults: dict[str, Any] = {
        "node_id": "nlA00",
        "hostname": "nlA00.ap.example.com",
        "ipv6": True,
        "decryption": "mlkem768x25519plus.native.600s.FAKE",
        "dns_address": "127.0.0.1",
        "dns_port": 53,
        "trusted_forwarded_headers": [],
        "haproxy": True,
        "route_only": True,
    }
    defaults.update(overrides)
    return SharedContext(**defaults)


def make_xhttp(**overrides: Any) -> XhttpContext:
    defaults: dict[str, Any] = {
        "clients": [],
        "short_ids": ["abcdef0123456789"],
        "dest": "vk.com:443",
        "server_names": ["vk.com"],
        "private_key": "FAKE_PRIV_KEY",
        "xhttp_host": "vk.com",
        "xhttp_path": "/path/",
        "fallback_limits": RealityFallbackLimits(),
    }
    defaults.update(overrides)
    return XhttpContext(**defaults)


def make_cdn(**overrides: Any) -> CdnContext:
    defaults: dict[str, Any] = {
        "xhttp_host": "nlA00.pluto.example.com",
        "xhttp_path": "/cdn/",
        "cert_alias": "pluto",
        "domain": "pluto.example.com",
        "clients": [],
    }
    defaults.update(overrides)
    return CdnContext(**defaults)


def make_xdns(**overrides: Any) -> XdnsContext:
    defaults: dict[str, Any] = {
        "config": XdnsConfig(domains=["dns.google"]),
        "clients": [
            {
                "id": "aaaaaaaa-0000-0000-0000-000000000000",
                "email": "u@ns",
                "flow": "",
            },
        ],
    }
    defaults.update(overrides)
    return XdnsContext(**defaults)


def make_wireguard(**overrides: Any) -> WireguardContext:
    defaults: dict[str, Any] = {
        "config": WireguardConfig(subnet="10.0.0.0/24"),
        "peers": [
            {
                "email": "u@ns",
                "publicKey": "FAKE_PUB",
                "allowedIPs": ["10.0.0.2/32"],
                "keepAlive": 0,
            },
        ],
        "secret_key": "FAKE_SECRET_STD_B64",
    }
    defaults.update(overrides)
    return WireguardContext(**defaults)


def make_proxy(**overrides: Any) -> ProxyContext:
    defaults: dict[str, Any] = {"accounts": []}
    defaults.update(overrides)
    return ProxyContext(**defaults)


def default_slots(
    xhttp: XhttpContext | None = None,
    cdn: CdnContext | None = None,
    proxy: ProxyContext | None = None,
    xdns: XdnsContext | None = None,
    wireguard: WireguardContext | None = None,
) -> dict[AccessType, InboundContext]:
    slots: dict[AccessType, InboundContext] = {AccessType.XHTTP: xhttp if xhttp is not None else make_xhttp()}
    if cdn is not None:
        slots[AccessType.CDN] = cdn
    if proxy is not None:
        slots[AccessType.PROXY] = proxy
    if xdns is not None:
        slots[AccessType.XDNS] = xdns
    if wireguard is not None:
        slots[AccessType.WIREGUARD] = wireguard
    return slots


def exit_ctx(**overrides: Any) -> ExitContext:
    defaults: dict[str, Any] = {
        "shared": make_shared(),
        "slots": default_slots(),
        "warp_domains": [],
        "extra_routes": [],
    }
    defaults.update(overrides)
    return ExitContext(**defaults)


def hub_ctx(**overrides: Any) -> HubContext:
    defaults: dict[str, Any] = {
        "shared": make_shared(node_id="mskA00", hostname="mskA00.ap.example.com"),
        "slots": default_slots(),
        "observatory": ObservatoryConfig(),
        "outbounds": [],
        "warp_outbounds": [],
        "balancers": [],
        "routing_rules": [],
        "observatory_selectors": [],
    }
    defaults.update(overrides)
    return HubContext(**defaults)
