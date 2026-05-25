from typing import Any

from hexrift.components.render.context import ExitContext, HubContext
from hexrift.components.render.xray import build_exit_config, build_hub_config
from hexrift.components.schema.models.defaults import ObservatoryConfig
from hexrift.components.schema.models.shared import RealityFallbackLimits


def _exit_ctx(**overrides: Any) -> ExitContext:
    defaults: dict[str, Any] = {
        "node_id": "nlA00",
        "hostname": "nlA00.ap.example.com",
        "ipv6": False,
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


def _hub_ctx(**overrides: Any) -> HubContext:
    defaults: dict[str, Any] = {
        "node_id": "mskA00",
        "hostname": "mskA00.ap.example.com",
        "ipv6": False,
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


class TestDnsPropagation:
    def test_exit_dns_default(self):
        config = build_exit_config(_exit_ctx())
        assert config["dns"]["servers"] == [{"address": "127.0.0.1", "port": 53}]

    def test_exit_dns_custom(self):
        config = build_exit_config(_exit_ctx(dns_address="169.254.0.53", dns_port=5353))
        assert config["dns"]["servers"] == [{"address": "169.254.0.53", "port": 5353}]

    def test_hub_dns_default(self):
        config = build_hub_config(_hub_ctx())
        assert config["dns"]["servers"] == [{"address": "127.0.0.1", "port": 53}]

    def test_hub_dns_custom(self):
        config = build_hub_config(_hub_ctx(dns_address="169.254.0.53", dns_port=5353))
        assert config["dns"]["servers"] == [{"address": "169.254.0.53", "port": 5353}]

    def test_dns_extra_options_always_present(self):
        config = build_exit_config(_exit_ctx())
        assert config["dns"]["enableParallelQuery"] is True
        assert config["dns"]["useSystemHosts"] is True
