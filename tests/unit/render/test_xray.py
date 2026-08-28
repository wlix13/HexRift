from hexrift.components.render.xray import build_exit_config, build_hub_config
from hexrift.components.schema.models.observability import LoggingConfig, MetricsConfig, ObservabilityConfig
from hexrift.constants import HysteriaCongestion, LogLevel, Socket
from hexrift.shared.hysteria import HYSTERIA_TRUNK_DIALER_QUIC
from tests.unit.render.helpers import (
    default_slots,
    make_hysteria,
    make_hysteria_outbound,
    make_shared,
    make_wireguard,
    make_xdns,
)
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

    def test_exit_dns_direct_rule_default(self):
        config = build_exit_config(_exit_ctx())
        assert config["routing"]["rules"][0] == {
            "ip": ["127.0.0.1", "::1"],
            "port": 53,
            "outboundTag": "direct",
        }

    def test_exit_dns_direct_rule_covers_custom_dns_server(self):
        config = build_exit_config(_exit_ctx(shared=make_shared(dns_address="169.254.0.53", dns_port=5353)))
        assert config["routing"]["rules"][0] == {
            "ip": ["127.0.0.1", "::1", "169.254.0.53"],
            "port": 5353,
            "outboundTag": "direct",
        }

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


class TestHysteria:
    def test_inbound_present_only_with_slot(self):
        assert "hysteria-in" not in [ib["tag"] for ib in build_hub_config(_hub_ctx())["inbounds"]]
        config = build_hub_config(_hub_ctx(slots=default_slots(hysteria=make_hysteria())))
        assert "hysteria-in" in [ib["tag"] for ib in config["inbounds"]]

    def test_pinned_outbound_shape(self):
        ob = make_hysteria_outbound(
            obfs_password="pw",  # noqa: S106
            congestion=HysteriaCongestion.BRUTAL,
            brutal_up="500 mbps",
            brutal_down="200 mbps",
        )
        config = build_hub_config(_hub_ctx(outbounds=[ob]))
        out = next(o for o in config["outbounds"] if o["tag"] == "deA00")
        assert out["protocol"] == "hysteria"
        assert out["settings"] == {"version": 2, "address": "deA00.ap.example.com", "port": 443}
        assert out["streamSettings"] == {
            "network": "hysteria",
            "security": "tls",
            "tlsSettings": {
                "serverName": "vk.com",
                "alpn": ["h3"],
                "pinnedPeerCertSha256": "AA:BB",
                "enableSessionResumption": True,
            },
            "hysteriaSettings": {"version": 2, "auth": "bbbbbbbb-0000-0000-0000-000000000000"},
            "finalmask": {
                "quicParams": {
                    "congestion": "brutal",
                    "brutalUp": "500 mbps",
                    "brutalDown": "200 mbps",
                    **HYSTERIA_TRUNK_DIALER_QUIC,
                    "disableChromeParrot": False,
                },
                "udp": [{"type": "salamander", "settings": {"password": "pw"}}],
            },
            "sockopt": {"domainStrategy": "UseIPv6v4"},
        }

    def test_operator_cert_outbound_has_no_pin_and_warp_prefix_tags(self):
        ob = make_hysteria_outbound(pin=None, tag_prefix="warp-")
        config = build_hub_config(_hub_ctx(warp_outbounds=[ob]))
        out = next(o for o in config["outbounds"] if o["tag"] == "warp-deA00")
        assert "pinnedPeerCertSha256" not in out["streamSettings"]["tlsSettings"]


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


class TestLogRendering:
    def test_exit_default_log_matches_prior_hardcoded_block(self):
        config = build_exit_config(_exit_ctx())
        assert config["log"] == {
            "loglevel": "none",
            "access": "none",
            "error": "none",
            "dnsLog": False,
        }

    def test_hub_default_log_matches_prior_hardcoded_block(self):
        config = build_hub_config(_hub_ctx())
        assert config["log"] == {
            "loglevel": "none",
            "access": "none",
            "error": "none",
            "dnsLog": False,
        }

    def test_exit_log_override_renders(self):
        observability = ObservabilityConfig(
            logging=LoggingConfig(
                loglevel=LogLevel.WARNING,
                access="/var/log/xray/access.log",
                dns_log=True,
            )
        )
        config = build_exit_config(_exit_ctx(shared=make_shared(observability=observability)))
        assert config["log"] == {
            "loglevel": "warning",
            "access": "/var/log/xray/access.log",
            "error": "none",
            "dnsLog": True,
        }

    def test_hub_log_override_renders(self):
        observability = ObservabilityConfig(logging=LoggingConfig(loglevel=LogLevel.ERROR))
        config = build_hub_config(_hub_ctx(shared=make_shared(observability=observability)))
        assert config["log"]["loglevel"] == "error"


class TestStatsApiPolicyBlocks:
    def test_exit_blocks_absent_when_disabled(self):
        config = build_exit_config(_exit_ctx())
        assert "stats" not in config
        assert "api" not in config
        assert "policy" not in config

    def test_hub_blocks_absent_when_disabled(self):
        config = build_hub_config(_hub_ctx())
        assert "stats" not in config
        assert "api" not in config
        assert "policy" not in config

    def test_exit_blocks_present_when_enabled(self):
        observability = ObservabilityConfig(metrics=MetricsConfig(enabled=True))
        config = build_exit_config(_exit_ctx(shared=make_shared(observability=observability)))
        assert config["stats"] == {}
        assert config["api"] == {
            "tag": "api",
            "listen": "127.0.0.1:10085",
            "services": ["StatsService"],
        }
        assert config["policy"]["system"] == {
            "statsInboundUplink": True,
            "statsInboundDownlink": True,
            "statsOutboundUplink": True,
            "statsOutboundDownlink": True,
        }
        assert config["policy"]["levels"] == {
            "0": {
                "statsUserUplink": True,
                "statsUserDownlink": True,
                "statsUserOnline": True,
            },
        }

    def test_hub_blocks_present_when_enabled(self):
        observability = ObservabilityConfig(metrics=MetricsConfig(enabled=True, port=9000))
        config = build_hub_config(_hub_ctx(shared=make_shared(observability=observability)))
        assert config["api"]["listen"] == "127.0.0.1:9000"
        assert config["stats"] == {}

    def test_levels_key_omitted_when_user_stats_and_online_both_false(self):
        observability = ObservabilityConfig(metrics=MetricsConfig(enabled=True, user_stats=False, online=False))
        config = build_exit_config(_exit_ctx(shared=make_shared(observability=observability)))
        assert "levels" not in config["policy"]
        assert "system" in config["policy"]

    def test_levels_key_present_with_only_user_stats(self):
        observability = ObservabilityConfig(metrics=MetricsConfig(enabled=True, user_stats=True, online=False))
        config = build_exit_config(_exit_ctx(shared=make_shared(observability=observability)))
        assert config["policy"]["levels"] == {"0": {"statsUserUplink": True, "statsUserDownlink": True}}

    def test_levels_key_present_with_only_online(self):
        observability = ObservabilityConfig(metrics=MetricsConfig(enabled=True, user_stats=False, online=True))
        config = build_exit_config(_exit_ctx(shared=make_shared(observability=observability)))
        assert config["policy"]["levels"] == {"0": {"statsUserOnline": True}}

    def test_ipv4_listen_not_bracketed(self):
        observability = ObservabilityConfig(metrics=MetricsConfig(enabled=True, listen="10.0.0.5"))
        config = build_exit_config(_exit_ctx(shared=make_shared(observability=observability)))
        assert config["api"]["listen"] == "10.0.0.5:10085"

    def test_ipv6_listen_bracketed(self):
        observability = ObservabilityConfig(metrics=MetricsConfig(enabled=True, listen="::1"))
        config = build_exit_config(_exit_ctx(shared=make_shared(observability=observability)))
        assert config["api"]["listen"] == "[::1]:10085"

    def test_hub_blocks_inserted_after_burst_observatory(self):
        observability = ObservabilityConfig(metrics=MetricsConfig(enabled=True))
        config = build_hub_config(
            _hub_ctx(
                shared=make_shared(observability=observability),
                observatory_selectors=["exit1"],
            )
        )
        keys = list(config.keys())
        assert keys.index("burstObservatory") < keys.index("stats")
