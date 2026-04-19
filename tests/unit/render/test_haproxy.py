from typing import Any

from hexrift.components.render.context import ExitContext, HubContext
from hexrift.components.render.haproxy import render_haproxy
from hexrift.components.schema.models.defaults import ObservatoryConfig
from hexrift.components.schema.models.shared import RealityFallbackLimits
from hexrift.constants import RegionType


def _exit_ctx(**overrides: Any) -> ExitContext:
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
        "warp_domains": [],
        "extra_routes": [],
    }
    defaults.update(overrides)
    return ExitContext(**defaults)


def _hub_ctx(**overrides: Any) -> HubContext:
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
        "portals": [],
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


class TestExitHaproxy:
    def test_basic_exit_contains_reality_backend(self):
        result = render_haproxy(_exit_ctx(), RegionType.EXIT)
        assert "bk_reality" in result

    def test_basic_exit_no_cdn_sections(self):
        result = render_haproxy(_exit_ctx(), RegionType.EXIT)
        assert "crt-store" not in result
        assert "cdn" not in result.lower()

    def test_exit_with_cdn_has_crt_store(self):
        ctx = _exit_ctx(
            cdn_cert_alias="pluto",
            cdn_xhttp_host="nlA00.pluto.example.com",
            cdn_xhttp_path="/cdn/",
        )
        result = render_haproxy(ctx, RegionType.EXIT)
        assert "crt-store" in result
        assert "pluto" in result

    def test_exit_ipv6_has_dual_bind(self):
        result = render_haproxy(_exit_ctx(ipv6=True), RegionType.EXIT)
        assert "[::]:443" in result

    def test_exit_no_ipv6_no_dual_bind(self):
        result = render_haproxy(_exit_ctx(ipv6=False), RegionType.EXIT)
        assert "[::]:443" not in result

    def test_no_mtproto_section(self):
        result = render_haproxy(_exit_ctx(), RegionType.EXIT)
        assert "mtproto" not in result.lower()

    def test_with_mtproto_section(self):
        ctx = _exit_ctx(mtproto_domain="tg.example.com", mtproto_port=1234)
        result = render_haproxy(ctx, RegionType.EXIT)
        assert "tg.example.com" in result

    def test_ends_with_newline(self):
        result = render_haproxy(_exit_ctx(), RegionType.EXIT)
        assert result.endswith("\n")


class TestHubHaproxy:
    def test_basic_hub_contains_reality_backend(self):
        result = render_haproxy(_hub_ctx(), RegionType.HUB)
        assert "bk_reality" in result

    def test_hub_with_cdn_has_crt_store(self):
        ctx = _hub_ctx(
            cdn_cert_alias="mercury",
            cdn_xhttp_host="mercury.example.com",
            cdn_xhttp_path="/cdn/",
        )
        result = render_haproxy(ctx, RegionType.HUB)
        assert "crt-store" in result
        assert "mercury" in result

    def test_hub_ipv6_has_dual_bind(self):
        result = render_haproxy(_hub_ctx(ipv6=True), RegionType.HUB)
        assert "[::]:443" in result

    def test_hub_no_ipv6_no_dual_bind(self):
        result = render_haproxy(_hub_ctx(ipv6=False), RegionType.HUB)
        assert "[::]:443" not in result

    def test_ends_with_newline(self):
        result = render_haproxy(_hub_ctx(), RegionType.HUB)
        assert result.endswith("\n")
