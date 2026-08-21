import pytest

from hexrift.components.render.haproxy import render_haproxy
from hexrift.errors import RenderError
from tests.unit.render.helpers import default_slots, make_cdn, make_shared
from tests.unit.render.helpers import exit_ctx as _exit_ctx
from tests.unit.render.helpers import hub_ctx as _hub_ctx


class TestExitHaproxy:
    def test_basic_exit_contains_reality_backend(self):
        result = render_haproxy(_exit_ctx())
        assert "bk_reality" in result

    def test_basic_exit_no_cdn_sections(self):
        result = render_haproxy(_exit_ctx())
        assert "crt-store" not in result
        assert "cdn" not in result.lower()

    def test_exit_with_cdn_has_crt_store(self):
        ctx = _exit_ctx(slots=default_slots(cdn=make_cdn()))
        result = render_haproxy(ctx)
        assert "crt-store" in result
        assert "pluto" in result

    def test_exit_ipv6_has_dual_bind(self):
        result = render_haproxy(_exit_ctx(shared=make_shared(ipv6=True)))
        assert "[::]:443" in result

    def test_exit_no_ipv6_no_dual_bind(self):
        result = render_haproxy(_exit_ctx(shared=make_shared(ipv6=False)))
        assert "[::]:443" not in result

    def test_cdn_uses_default_trusted_header(self):
        ctx = _exit_ctx(slots=default_slots(cdn=make_cdn()))
        result = render_haproxy(ctx)
        assert "set-header X-Real-IP" in result

    def test_cdn_uses_custom_trusted_header(self):
        ctx = _exit_ctx(
            shared=make_shared(trusted_forwarded_headers=["CF-Connecting-IP"]),
            slots=default_slots(cdn=make_cdn()),
        )
        result = render_haproxy(ctx)
        assert "set-header CF-Connecting-IP" in result
        assert "set-header X-Real-IP" not in result

    def test_cdn_empty_trusted_headers_uses_default(self):
        # No CDN configured at the topology level → empty header list → default.
        ctx = _exit_ctx(
            shared=make_shared(trusted_forwarded_headers=[]),
            slots=default_slots(cdn=make_cdn()),
        )
        result = render_haproxy(ctx)
        assert "set-header X-Real-IP" in result

    @pytest.mark.parametrize("evil", ["X-Real-IP\nhttp-request deny", "X Real IP", ""])
    def test_malformed_trusted_header_rejected(self, evil: str):
        ctx = _exit_ctx(
            shared=make_shared(trusted_forwarded_headers=[evil]),
            slots=default_slots(cdn=make_cdn()),
        )
        with pytest.raises(RenderError, match="Invalid trusted forwarded header"):
            render_haproxy(ctx)


class TestHubHaproxy:
    def test_basic_hub_contains_reality_backend(self):
        result = render_haproxy(_hub_ctx())
        assert "bk_reality" in result

    def test_hub_with_cdn_has_crt_store(self):
        ctx = _hub_ctx(
            slots=default_slots(
                cdn=make_cdn(
                    xhttp_host="mercury.example.com",
                    cert_alias="mercury",
                    domain="mercury.example.com",
                )
            )
        )
        result = render_haproxy(ctx)
        assert "crt-store" in result
        assert "mercury" in result

    def test_hub_ipv6_has_dual_bind(self):
        result = render_haproxy(_hub_ctx(shared=make_shared(ipv6=True)))
        assert "[::]:443" in result

    def test_hub_no_ipv6_no_dual_bind(self):
        result = render_haproxy(_hub_ctx(shared=make_shared(ipv6=False)))
        assert "[::]:443" not in result


class TestDisabledHaproxy:
    def test_exit_direct_bind_returns_stub(self):
        result = render_haproxy(_exit_ctx(shared=make_shared(haproxy=False)))
        assert "DISABLED" in result
        assert "frontend" not in result
        assert "backend" not in result
        assert "bind *:443" not in result

    def test_hub_direct_bind_returns_stub(self):
        result = render_haproxy(_hub_ctx(shared=make_shared(haproxy=False)))
        assert "DISABLED" in result
        assert "frontend" not in result

    def test_stub_has_global_and_defaults(self):
        result = render_haproxy(_exit_ctx(shared=make_shared(haproxy=False)))
        assert "\nglobal\n" in result
        assert "\ndefaults\n" in result


class TestBlankLines:
    @pytest.mark.parametrize(
        "ctx",
        [
            _exit_ctx(),
            _exit_ctx(slots=default_slots(cdn=make_cdn())),
            _exit_ctx(shared=make_shared(ipv6=True)),
            _exit_ctx(shared=make_shared(haproxy=False)),
            _hub_ctx(),
            _hub_ctx(slots=default_slots(cdn=make_cdn())),
        ],
    )
    def test_single_trailing_newline_and_no_blank_runs(self, ctx):
        result = render_haproxy(ctx)
        assert result.endswith("\n")
        assert not result.endswith("\n\n")
        assert "\n\n\n" not in result
