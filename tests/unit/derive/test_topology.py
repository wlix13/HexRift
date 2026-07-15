from hexrift.components.derive.topology import (
    build_balancers,
    build_burst_observatory_selectors,
    build_hub_routing_rules,
    region_outbound_tag,
    region_warp_outbound_tag,
)
from hexrift.components.schema.models.regions import LeastLoadSettings, Node, Region, WarpConfig
from hexrift.components.schema.models.root import ConglomerateConfig
from hexrift.constants import LbRole, RegionType


def _minimal_cfg_dict(**overrides) -> dict:
    base = {
        "global": {
            "namespace": "t.ns",
            "aphelion_domain": "ap.t.ns",
        },
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
            },
        ],
        "routing": {"hub_default": "hub1"},
        "regions": [
            {
                "id": "exit1",
                "type": "exit",
                "vless_route": 1000,
                "nodes": [
                    {
                        "id": "exitN1",
                        "hostname": "e.t.ns",
                        "reality": {
                            "dest": "a.com:443",
                            "xhttp_path": "/x/",
                        },
                    },
                ],
            },
            {
                "id": "hub1",
                "type": "hub",
                "nodes": [
                    {
                        "id": "hubN1",
                        "hostname": "h.t.ns",
                    },
                ],
            },
        ],
    }
    base.update(overrides)
    return base


def _make_cfg(**routing_overrides) -> ConglomerateConfig:
    d = _minimal_cfg_dict()
    if routing_overrides:
        d["routing"].update(routing_overrides)
    return ConglomerateConfig.model_validate(d)


def _make_region(
    region_id: str = "exit1",
    rtype: RegionType = RegionType.EXIT,
    nodes: list[Node] | None = None,
    lb_strategy: str | None = None,
    lb_fallback: str | None = None,
    warp: WarpConfig | None = None,
) -> Region:
    if nodes is None:
        nodes = [Node(id="n1", hostname="n1.test")]
    return Region.model_construct(
        id=region_id,
        type=rtype,
        vless_route=1000,
        cdn_xhttp_path=None,
        lb_strategy=lb_strategy,
        lb_fallback=lb_fallback,
        lb_least_load=None,
        routing=None,
        warp=warp,
        nodes=nodes,
    )


class TestBuildHubRoutingRules:
    def test_dns_rule_is_first(self):
        cfg = _make_cfg()
        rules = build_hub_routing_rules(cfg)
        assert rules[0] == {"ip": ["127.0.0.1", "::1"], "port": 53, "outboundTag": "direct"}

    def test_dns_rule_covers_custom_dns_server(self):
        d = _minimal_cfg_dict()
        d["global"]["dns"] = {"address": "10.0.0.53", "port": 5353}
        cfg = ConglomerateConfig.model_validate(d)
        rules = build_hub_routing_rules(cfg)
        assert rules[0] == {
            "ip": ["127.0.0.1", "::1", "10.0.0.53"],
            "port": 5353,
            "outboundTag": "direct",
        }

    def test_vless_route_rule_per_exit_region(self):
        cfg = _make_cfg()
        rules = build_hub_routing_rules(cfg)
        vless_rules = [r for r in rules if "vlessRoute" in r]
        assert len(vless_rules) == 1
        assert vless_rules[0]["vlessRoute"] == "1000"

    def test_no_warp_vless_route_when_no_warp(self):
        cfg = _make_cfg()
        rules = build_hub_routing_rules(cfg)
        # Only one vlessRoute rule (the regular one)
        vless_rules = [r for r in rules if "vlessRoute" in r]
        assert len(vless_rules) == 1

    def test_warp_vless_route_present_when_configured(self):
        d = _minimal_cfg_dict()
        d["regions"][0]["warp"] = {"vless_route": 65535}
        cfg = ConglomerateConfig.model_validate(d)
        rules = build_hub_routing_rules(cfg)
        vless_rules = [r for r in rules if "vlessRoute" in r]
        assert len(vless_rules) == 2
        warp_rule = next(r for r in vless_rules if r["vlessRoute"] == "65535")
        assert "warp" in warp_rule.get("outboundTag", warp_rule.get("balancerTag", ""))

    def test_blocked_domain_rule(self):
        d = _minimal_cfg_dict()
        d["routing"]["hub_routes"] = [{"destination": "blocked", "domains": ["evil.com"]}]
        cfg = ConglomerateConfig.model_validate(d)
        rules = build_hub_routing_rules(cfg)
        blocked = [r for r in rules if r.get("outboundTag") == "blocked"]
        assert any(r.get("domain") == ["evil.com"] for r in blocked)

    def test_blocked_ip_rule_appears(self):
        d = _minimal_cfg_dict()
        d["routing"]["hub_routes"] = [{"destination": "blocked", "ips": ["10.0.0.0/8"]}]
        cfg = ConglomerateConfig.model_validate(d)
        rules = build_hub_routing_rules(cfg)
        blocked_ip = [r for r in rules if r.get("outboundTag") == "blocked" and "ip" in r]
        assert len(blocked_ip) == 1
        assert "10.0.0.0/8" in blocked_ip[0]["ip"]

    def test_blocked_user_filter_only_rule(self):
        d = _minimal_cfg_dict()
        d["routing"]["hub_routes"] = [{"destination": "blocked", "users": ["alice"]}]
        cfg = ConglomerateConfig.model_validate(d)
        rules = build_hub_routing_rules(cfg)
        blocked = [r for r in rules if r.get("outboundTag") == "blocked"]
        # user-only blocked rule: has "user" key but no "domain" or "ip"
        user_only = [r for r in blocked if "user" in r and "domain" not in r and "ip" not in r]
        assert len(user_only) == 1

    def test_portal_domain_rule(self):
        d = _minimal_cfg_dict()
        d["users"] = [
            {
                "username": "alice",
                "group": "grp1",
                "access": ["xhttp"],
                "portals": [
                    {
                        "label": "home",
                        "routes": {"domains": ["home.alice.example.com"]},
                    }
                ],
            }
        ]
        cfg = ConglomerateConfig.model_validate(d)
        rules = build_hub_routing_rules(cfg)
        portal_domain = next(
            (
                r
                for r in rules
                if r.get("domain") == ["home.alice.example.com"] and r.get("outboundTag") == "home-portal"
            ),
            None,
        )
        assert portal_domain is not None
        assert "user" in portal_domain  # user-filtered

    def test_portal_ip_rule(self):
        d = _minimal_cfg_dict()
        d["users"] = [
            {
                "username": "alice",
                "group": "grp1",
                "access": ["xhttp"],
                "portals": [{"label": "home", "routes": {"ips": ["192.168.1.0/24"]}}],
            }
        ]
        cfg = ConglomerateConfig.model_validate(d)
        rules = build_hub_routing_rules(cfg)
        portal_ip = next(
            (r for r in rules if r.get("ip") == ["192.168.1.0/24"] and r.get("outboundTag") == "home-portal"),
            None,
        )
        assert portal_ip is not None

    def test_hub_route_to_node_destination(self):
        d = _minimal_cfg_dict()
        d["routing"]["hub_routes"] = [{"destination": "exitN1", "domains": ["specific.com"]}]
        cfg = ConglomerateConfig.model_validate(d)
        rules = build_hub_routing_rules(cfg)
        node_rule = next((r for r in rules if r.get("outboundTag") == "exitN1" and "domain" in r), None)
        assert node_rule is not None
        assert node_rule["domain"] == ["specific.com"]

    def test_hub_route_to_warp_destination(self):
        d = _minimal_cfg_dict()
        d["routing"]["hub_routes"] = [{"destination": "warp", "domains": ["torrent.com"]}]
        cfg = ConglomerateConfig.model_validate(d)
        rules = build_hub_routing_rules(cfg)
        warp_rule = next((r for r in rules if r.get("outboundTag") == "warp"), None)
        assert warp_rule is not None

    def test_hub_route_proxy_users_filter(self):
        d = _minimal_cfg_dict()
        # proxy_users must be known usernames; they are inserted verbatim into user filter
        d["routing"]["hub_routes"] = [
            {
                "destination": "direct",
                "domains": ["internal.com"],
                "proxy_users": ["alice"],
            }
        ]
        cfg = ConglomerateConfig.model_validate(d)
        rules = build_hub_routing_rules(cfg)
        direct = next((r for r in rules if r.get("outboundTag") == "direct" and "domain" in r), None)
        assert direct is not None
        assert "user" in direct
        assert "alice" in direct["user"]

    def test_direct_domain_rule(self):
        d = _minimal_cfg_dict()
        d["routing"]["hub_routes"] = [
            {
                "destination": "direct",
                "domains": ["internal.com"],
            }
        ]
        cfg = ConglomerateConfig.model_validate(d)
        rules = build_hub_routing_rules(cfg)
        direct = next((r for r in rules if r.get("outboundTag") == "direct" and r.get("domain")), None)
        assert direct is not None
        assert "internal.com" in direct["domain"]

    def test_direct_ip_rule(self):
        d = _minimal_cfg_dict()
        d["routing"]["hub_routes"] = [{"destination": "direct", "ips": ["10.0.0.0/8"]}]
        cfg = ConglomerateConfig.model_validate(d)
        rules = build_hub_routing_rules(cfg)
        # Skip the DNS localhost rule which also has ip + outboundTag=direct
        direct_ip = next(
            (r for r in rules if r.get("outboundTag") == "direct" and "10.0.0.0/8" in r.get("ip", [])),
            None,
        )
        assert direct_ip is not None
        assert "10.0.0.0/8" in direct_ip["ip"]

    def test_no_portal_catchall_rule(self):
        d = _minimal_cfg_dict()
        d["users"] = [
            {
                "username": "alice",
                "group": "grp1",
                "access": ["xhttp", "server"],
                "portals": [{"label": "home", "routes": {"domains": ["home.alice.com"]}}],
            }
        ]
        cfg = ConglomerateConfig.model_validate(d)
        rules = build_hub_routing_rules(cfg)
        catchall = next(
            (r for r in rules if r.get("user") == ["home-portal@alice"]),
            None,
        )
        assert catchall is None

    def test_default_rule_is_last(self):
        cfg = _make_cfg()
        rules = build_hub_routing_rules(cfg)
        last = rules[-1]
        assert last["network"] == "TCP,UDP"
        assert "outboundTag" in last or "balancerTag" in last

    def test_default_rule_special_destination_direct(self):
        cfg = _make_cfg(hub_default="direct")
        rules = build_hub_routing_rules(cfg)
        assert rules[-1] == {"network": "TCP,UDP", "outboundTag": "direct"}

    def test_all_in_one_no_exit_regions(self):
        d = _minimal_cfg_dict()
        # Drop exit regions: all-in-one hub egresses everything itself
        d["regions"] = [r for r in d["regions"] if r["type"] == "hub"]
        d["routing"]["hub_default"] = "direct"
        cfg = ConglomerateConfig.model_validate(d)
        rules = build_hub_routing_rules(cfg)
        assert [r for r in rules if "vlessRoute" in r] == []
        assert rules[-1] == {"network": "TCP,UDP", "outboundTag": "direct"}


class TestBuildBalancers:
    def test_empty_when_no_lb_strategy(self):
        r = _make_region(lb_strategy=None)
        result = build_balancers([r])
        assert result == []

    def test_has_lb_tag_when_strategy_set(self):
        r = _make_region(region_id="exit1", lb_strategy="random")
        result = build_balancers([r])
        assert len(result) == 1
        assert result[0]["tag"] == "lb-exit1"

    def test_includes_warp_balancer(self):
        r = _make_region(region_id="exit1", lb_strategy="random", warp=WarpConfig(vless_route=65535))
        result = build_balancers([r])
        tags = [b["tag"] for b in result]
        assert "lb-exit1" in tags
        assert "lb-warp-exit1" in tags

    def test_fallback_tag_backup_role(self):
        n_primary = Node.model_construct(
            id="n1",
            hostname="n1.test",
            lb_role=None,
            reality=None,
            keys=None,
            exit_connections=None,
            proxy_inbound=None,
            ipv6=None,
        )
        n_backup = Node.model_construct(
            id="n2",
            hostname="n2.test",
            lb_role=LbRole.BACKUP,
            reality=None,
            keys=None,
            exit_connections=None,
            proxy_inbound=None,
            ipv6=None,
        )
        r = _make_region(region_id="exit1", lb_strategy="random", nodes=[n_primary, n_backup], lb_fallback="n2")
        result = build_balancers([r])
        assert result[0]["fallbackTag"] == "backup-n2"

    def test_least_load_strategy_includes_settings(self):
        r = _make_region(region_id="exit1", lb_strategy="leastLoad")
        r.lb_least_load = LeastLoadSettings()
        result = build_balancers([r])
        assert "settings" in result[0]["strategy"]


class TestRegionOutboundTag:
    def test_with_lb_strategy_returns_lb_prefix(self):
        r = _make_region(region_id="exit1", lb_strategy="random")
        assert region_outbound_tag(r) == "lb-exit1"

    def test_without_lb_returns_primary_node_id(self):
        r = _make_region(region_id="exit1", lb_strategy=None)
        assert region_outbound_tag(r) == "n1"

    def test_warp_tag_with_lb(self):
        r = _make_region(region_id="exit1", lb_strategy="random")
        assert region_warp_outbound_tag(r) == "lb-warp-exit1"

    def test_warp_tag_without_lb(self):
        r = _make_region(region_id="exit1", lb_strategy=None)
        assert region_warp_outbound_tag(r) == "warp-n1"


class TestBuildBurstObservatorySelectors:
    def test_empty_without_lb(self):
        r = _make_region(lb_strategy=None)
        assert build_burst_observatory_selectors([r]) == []

    def test_region_id_with_lb(self):
        r = _make_region(region_id="exit1", lb_strategy="random")
        result = build_burst_observatory_selectors([r])
        assert "exit1" in result

    def test_includes_warp_variant(self):
        r = _make_region(region_id="exit1", lb_strategy="random", warp=WarpConfig(vless_route=65535))
        result = build_burst_observatory_selectors([r])
        assert "exit1" in result
        assert "warp-exit1" in result
