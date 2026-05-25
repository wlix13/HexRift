from hexrift.components.render.haproxy import render_haproxy
from hexrift.constants import RegionType
from tests.unit.render.helpers import exit_ctx as _exit_ctx
from tests.unit.render.helpers import hub_ctx as _hub_ctx


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

    def test_cdn_uses_default_trusted_header(self):
        ctx = _exit_ctx(
            cdn_cert_alias="pluto",
            cdn_xhttp_host="nlA00.pluto.example.com",
            cdn_xhttp_path="/cdn/",
        )
        result = render_haproxy(ctx, RegionType.EXIT)
        assert "set-header X-Real-IP" in result

    def test_cdn_uses_custom_trusted_header(self):
        ctx = _exit_ctx(
            cdn_cert_alias="pluto",
            cdn_xhttp_host="nlA00.pluto.example.com",
            cdn_xhttp_path="/cdn/",
            trusted_forwarded_headers=["CF-Connecting-IP"],
        )
        result = render_haproxy(ctx, RegionType.EXIT)
        assert "set-header CF-Connecting-IP" in result
        assert "set-header X-Real-IP" not in result

    def test_cdn_invalid_trusted_header_falls_back_to_default(self):
        ctx = _exit_ctx(
            cdn_cert_alias="pluto",
            cdn_xhttp_host="nlA00.pluto.example.com",
            cdn_xhttp_path="/cdn/",
            trusted_forwarded_headers=["CF-Connecting-IP\n"],
        )
        result = render_haproxy(ctx, RegionType.EXIT)
        assert "set-header X-Real-IP" in result
        assert "CF-Connecting-IP" not in result


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
