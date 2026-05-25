from typing import Any

from hexrift.components.render.context import ExitContext, HubContext
from hexrift.components.schema.models.defaults import ObservatoryConfig
from hexrift.components.schema.models.shared import RealityFallbackLimits


def exit_ctx(**overrides: Any) -> ExitContext:
    defaults: dict[str, Any] = {
        "node_id": "nlA00",
        "hostname": "nlA00.ap.example.com",
        "ipv6": True,
        "reality_dest": "vk.com:443",
        "reality_server_names": ["vk.com"],
        "reality_private_key": "FAKE_PRIV_KEY",
        "reality_public_key": "FAKE_PUB_KEY",
        "reality_xhttp_host": "vk.com",
        "reality_xhttp_path": "/path/",
        "reality_short_id": "abcdef0123456789",
        "decryption": "mlkem768x25519plus.native.600s.FAKE",
        "reality_fallback_limits": RealityFallbackLimits(),
        "direct_clients": [],
        "dns_address": "127.0.0.1",
        "dns_port": 53,
        "trusted_forwarded_headers": [],
        "warp_domains": [],
        "extra_routes": [],
    }
    defaults.update(overrides)
    return ExitContext(**defaults)


def hub_ctx(**overrides: Any) -> HubContext:
    defaults: dict[str, Any] = {
        "node_id": "mskA00",
        "hostname": "mskA00.ap.example.com",
        "ipv6": True,
        "reality_dest": "vk.com:443",
        "reality_server_names": ["vk.com"],
        "reality_private_key": "FAKE_PRIV_KEY",
        "reality_xhttp_host": "vk.com",
        "reality_xhttp_path": "/path/",
        "reality_short_ids": ["abcdef0123456789"],
        "decryption": "mlkem768x25519plus.native.600s.FAKE",
        "reality_fallback_limits": RealityFallbackLimits(),
        "observatory": ObservatoryConfig(),
        "vless_clients": [],
        "dns_address": "127.0.0.1",
        "dns_port": 53,
        "trusted_forwarded_headers": [],
        "outbounds": [],
        "warp_outbounds": [],
        "balancers": [],
        "routing_rules": [],
        "observatory_selectors": [],
        "proxy_inbound": False,
        "proxy_inbound_accounts": [],
    }
    defaults.update(overrides)
    return HubContext(**defaults)
