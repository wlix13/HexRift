from hexrift.components.render.xray import build_exit_config, build_hub_config
from hexrift.constants import Socket
from tests.unit.render.helpers import default_slots, make_shared, make_wireguard, make_xdns
from tests.unit.render.helpers import exit_ctx as _exit_ctx
from tests.unit.render.helpers import hub_ctx as _hub_ctx


class TestDnsPropagation:
    def test_exit_dns_default(self):
        config = build_exit_config(_exit_ctx())
        assert config["dns"]["servers"] == [{"address": "127.0.0.1", "port": 53}]

    def test_exit_dns_custom(self):
        config = build_exit_config(_exit_ctx(shared=make_shared(dns_address="169.254.0.53", dns_port=5353)))
        assert config["dns"]["servers"] == [{"address": "169.254.0.53", "port": 5353}]

    def test_hub_dns_default(self):
        config = build_hub_config(_hub_ctx())
        assert config["dns"]["servers"] == [{"address": "127.0.0.1", "port": 53}]

    def test_hub_dns_custom(self):
        config = build_hub_config(_hub_ctx(shared=make_shared(dns_address="169.254.0.53", dns_port=5353)))
        assert config["dns"]["servers"] == [{"address": "169.254.0.53", "port": 5353}]

    def test_exit_dns_extra_options_always_present(self):
        config = build_exit_config(_exit_ctx())
        assert config["dns"]["enableParallelQuery"] is True
        assert config["dns"]["useSystemHosts"] is True

    def test_hub_dns_extra_options_always_present(self):
        config = build_hub_config(_hub_ctx())
        assert config["dns"]["enableParallelQuery"] is True
        assert config["dns"]["useSystemHosts"] is True


class TestExitIpv6Egress:
    @staticmethod
    def _direct(config: dict) -> dict:
        return next(ob for ob in config["outbounds"] if ob["tag"] == "direct")

    def test_exit_direct_prefers_ipv6_on_dualstack(self):
        config = build_exit_config(_exit_ctx(shared=make_shared(ipv6=True)))
        assert self._direct(config)["settings"]["domainStrategy"] == "UseIPv6v4"

    def test_exit_direct_forces_ipv4_when_no_ipv6(self):
        config = build_exit_config(_exit_ctx(shared=make_shared(ipv6=False)))
        assert self._direct(config)["settings"]["domainStrategy"] == "UseIPv4"

    def test_exit_inbound_route_only_false_overrides_dest(self):
        # routeOnly:false lets exit re-resolve sniffed domain to pick IPv6
        config = build_exit_config(_exit_ctx(shared=make_shared(route_only=False)))
        for ib in config["inbounds"]:
            assert ib["sniffing"]["routeOnly"] is False

    def test_hub_inbound_keeps_route_only_true(self):
        # hub must preserve destination for possible MTProto masquerade
        config = build_hub_config(_hub_ctx(shared=make_shared(route_only=True)))
        reality_ib = next(ib for ib in config["inbounds"] if ib["tag"] == "direct-xhttp")
        assert reality_ib["sniffing"]["routeOnly"] is True


class TestXdnsWireguardInbounds:
    def test_xdns_inbound_absent_without_slot(self):
        config = build_hub_config(_hub_ctx())
        tags = [ib["tag"] for ib in config["inbounds"]]
        assert "xdns" not in tags

    def test_xdns_inbound_present_with_slot(self):
        config = build_hub_config(_hub_ctx(slots=default_slots(xdns=make_xdns())))
        tags = [ib["tag"] for ib in config["inbounds"]]
        assert "xdns" in tags

    def test_wireguard_inbound_absent_without_slot(self):
        config = build_hub_config(_hub_ctx())
        tags = [ib["tag"] for ib in config["inbounds"]]
        assert "wireguard-in" not in tags

    def test_wireguard_inbound_present_with_slot(self):
        config = build_hub_config(_hub_ctx(slots=default_slots(wireguard=make_wireguard())))
        tags = [ib["tag"] for ib in config["inbounds"]]
        assert "wireguard-in" in tags


class TestDirectBindReality:
    @staticmethod
    def _reality(config: dict) -> dict:
        return next(ib for ib in config["inbounds"] if ib["tag"] == "direct-xhttp")

    def test_haproxy_true_uses_unix_socket(self):
        ib = self._reality(build_exit_config(_exit_ctx(shared=make_shared(haproxy=True))))
        assert ib["listen"] == Socket.VLESS_REALITY
        assert "port" not in ib

    def test_haproxy_false_binds_ipv4_443(self):
        ib = self._reality(build_exit_config(_exit_ctx(shared=make_shared(haproxy=False, ipv6=False))))
        assert ib["listen"] == "0.0.0.0"  # noqa: S104
        assert ib["port"] == 443

    def test_haproxy_false_binds_dualstack_when_ipv6(self):
        ib = self._reality(build_exit_config(_exit_ctx(shared=make_shared(haproxy=False, ipv6=True))))
        assert ib["listen"] == "::"
        assert ib["port"] == 443

    def test_hub_direct_bind_binds_443(self):
        ib = self._reality(build_hub_config(_hub_ctx(shared=make_shared(haproxy=False, ipv6=False))))
        assert ib["listen"] == "0.0.0.0"  # noqa: S104
        assert ib["port"] == 443


class TestTrustedXForwardedFor:
    @staticmethod
    def _xff(config: dict, tag: str = "direct-xhttp") -> list:
        ib = next(i for i in config["inbounds"] if i["tag"] == tag)
        return ib["streamSettings"]["sockopt"]["trustedXForwardedFor"]

    def test_defaults_to_x_real_ip_without_trusted_front(self):
        cfg = build_exit_config(_exit_ctx(shared=make_shared(trusted_forwarded_headers=[])))
        assert self._xff(cfg) == ["X-Real-IP"]

    def test_uses_configured_headers(self):
        cfg = build_exit_config(_exit_ctx(shared=make_shared(trusted_forwarded_headers=["CF-Connecting-IP"])))
        assert self._xff(cfg) == ["CF-Connecting-IP"]

    def test_direct_bind_still_sets_xff(self):
        cfg = build_exit_config(_exit_ctx(shared=make_shared(haproxy=False, trusted_forwarded_headers=[])))
        assert self._xff(cfg) == ["X-Real-IP"]
