from typing import Any

from hexrift.components.keys.store import NodeKeys
from hexrift.components.render.portal import build_portal_config, build_portal_rules
from hexrift.components.schema.models.portals import Portal
from hexrift.components.schema.models.root import ConglomerateConfig


KEYS = NodeKeys(
    reality_private_key="FAKE_PRIV",
    reality_public_key="FAKE_PUB",
    decryption="none",
    encryption="none",
)


def _portal(**overrides: Any) -> Portal:
    base: dict[str, Any] = {
        "id": "home",
        "users": ["alice"],
        "routes": {"domains": ["home.example.com"], "ips": ["192.168.1.0/24"]},
    }
    base.update(overrides)
    return Portal.model_validate(base)


def _config(**portal_overrides: Any) -> ConglomerateConfig:
    portal: dict[str, Any] = {
        "id": "home",
        "users": ["alice"],
        "routes": {"domains": ["home.example.com"]},
    }
    portal.update(portal_overrides)
    return ConglomerateConfig.model_validate(
        {
            "global": {"namespace": "t.ns", "aphelion_domain": "ap.t.ns"},
            "defaults": {
                "exit": {
                    "ipv6": True,
                    "keys": {
                        "auth": "mlkem768",
                        "mode": "native",
                        "session_time": "600s",
                    },
                },
                "hub": {
                    "ipv6": True,
                    "keys": {
                        "auth": "x25519",
                        "mode": "native",
                        "session_time": "600s",
                    },
                    "exit_connections": {
                        "method": "mlkem768x25519plus",
                        "fingerprint": "chrome",
                    },
                    "reality": {
                        "dest": "a.com:443",
                        "xhttp_path": "/x/",
                    },
                },
            },
            "groups": [{"id": "grp1"}],
            "users": [
                {
                    "username": "alice",
                    "group": "grp1",
                    "access": ["xhttp"],
                }
            ],
            "portals": [portal],
            "routing": {
                "hub_default": "direct",
            },
            "regions": [
                {
                    "id": "hub1",
                    "type": "hub",
                    "nodes": [
                        {
                            "id": "hubN1",
                            "hostname": "h.t.ns",
                        }
                    ],
                },
            ],
        }
    )


class TestBuildPortalRules:
    def test_strict_mirrors_matchers_then_blackholes(self):
        assert build_portal_rules(_portal(), "home-portal") == [
            {
                "inboundTag": ["home-portal"],
                "domain": ["home.example.com"],
                "outboundTag": "direct",
            },
            {
                "inboundTag": ["home-portal"],
                "ip": ["192.168.1.0/24"],
                "outboundTag": "direct",
            },
            {
                "inboundTag": ["home-portal"],
                "outboundTag": "blocked",
            },
        ]

    def test_matchers_copied_verbatim(self):
        portal = _portal(routes={"domains": ["regexp:^nas\\..*\\.lan$"]})
        assert build_portal_rules(portal, "home-portal")[0]["domain"] == ["regexp:^nas\\..*\\.lan$"]

    def test_non_strict_emits_single_catchall(self):
        assert build_portal_rules(_portal(strict=False), "home-portal") == [
            {
                "inboundTag": ["home-portal"],
                "outboundTag": "direct",
            },
        ]


class TestBuildPortalConfig:
    def test_strict_disables_reverse_sniffing(self):
        # routeOnly sniffing would route on the client-supplied SNI
        config = build_portal_config(
            _config(),
            "home",
            {"hubN1": KEYS},
            "chrome",
        )
        assert config["outbounds"][0]["settings"]["reverse"]["sniffing"] == {"enabled": False}

    def test_non_strict_keeps_reverse_sniffing(self):
        config = build_portal_config(
            _config(strict=False),
            "home",
            {"hubN1": KEYS},
            "chrome",
        )
        sniffing = config["outbounds"][0]["settings"]["reverse"]["sniffing"]
        assert (sniffing["enabled"], sniffing["routeOnly"]) == (True, True)

    def test_strict_adds_blackhole_outbound(self):
        config = build_portal_config(
            _config(),
            "home",
            {"hubN1": KEYS},
            "chrome",
        )
        assert [ob["tag"] for ob in config["outbounds"]] == ["portal-hubN1", "direct", "blocked"]

    def test_strict_resolves_on_demand(self):
        # The strict catch-all always matches first, so IPIfNonMatch would never re-run
        config = build_portal_config(
            _config(),
            "home",
            {"hubN1": KEYS},
            "chrome",
        )
        assert config["routing"]["domainStrategy"] == "IPOnDemand"

    def test_non_strict_keeps_if_non_match(self):
        config = build_portal_config(
            _config(strict=False),
            "home",
            {"hubN1": KEYS},
            "chrome",
        )
        assert config["routing"]["domainStrategy"] == "IPIfNonMatch"

    def test_strict_keeps_safety_pin_last(self):
        config = build_portal_config(
            _config(),
            "home",
            {"hubN1": KEYS},
            "chrome",
        )
        assert config["routing"]["rules"] == [
            {
                "inboundTag": ["home-portal"],
                "domain": ["home.example.com"],
                "outboundTag": "direct",
            },
            {
                "inboundTag": ["home-portal"],
                "outboundTag": "blocked",
            },
            {
                "network": "TCP,UDP",
                "outboundTag": "direct",
            },
        ]

    def test_non_strict_reproduces_catchall_output(self):
        config = build_portal_config(
            _config(strict=False),
            "home",
            {"hubN1": KEYS},
            "chrome",
        )
        assert [ob["tag"] for ob in config["outbounds"]] == ["portal-hubN1", "direct"]
        assert config["routing"]["rules"] == [
            {
                "inboundTag": ["home-portal"],
                "outboundTag": "direct",
            },
            {
                "network": "TCP,UDP",
                "outboundTag": "direct",
            },
        ]
