import copy

import pytest
from pydantic import ValidationError

from hexrift.components.schema.models.root import ConglomerateConfig


def _valid_config() -> dict:
    """Minimal valid ConglomerateConfig as a plain dict."""

    return {
        "global": {
            "namespace": "test.ns",
            "aphelion_domain": "ap.test.ns",
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
                    "dest": "vk.com:443",
                    "xhttp_path": "/idx/",
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
                        "hostname": "exitN1.ap.test.ns",
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
                        "hostname": "hubN1.ap.test.ns",
                    },
                ],
            },
        ],
    }


def test_valid_minimal_config():
    cfg = ConglomerateConfig.model_validate(_valid_config())
    assert cfg.global_.namespace == "test.ns"
    assert len(cfg.regions) == 2


def test_duplicate_region_ids():
    d = copy.deepcopy(_valid_config())
    d["regions"].append(copy.deepcopy(d["regions"][0]))
    with pytest.raises(ValidationError, match="Duplicate region id"):
        ConglomerateConfig.model_validate(d)


def test_duplicate_node_ids():
    d = copy.deepcopy(_valid_config())
    # Add a node with the same id in the second region
    d["regions"][1]["nodes"].append({"id": "exitN1", "hostname": "dup.test.ns"})
    with pytest.raises(ValidationError, match="Duplicate node id"):
        ConglomerateConfig.model_validate(d)


def test_exit_region_missing_vless_route():
    d = copy.deepcopy(_valid_config())
    del d["regions"][0]["vless_route"]
    with pytest.raises(ValidationError, match="must have vless_route"):
        ConglomerateConfig.model_validate(d)


def test_exit_region_duplicate_vless_route():
    d = copy.deepcopy(_valid_config())
    # Add second exit region with same vless_route
    second_exit = {
        "id": "exit2",
        "type": "exit",
        "vless_route": 1000,
        "nodes": [
            {
                "id": "exitN2",
                "hostname": "e2.test.ns",
                "reality": {
                    "dest": "b.com:443",
                    "xhttp_path": "/y/",
                },
            },
        ],
    }
    d["regions"].insert(1, second_exit)
    with pytest.raises(ValidationError, match="Duplicate vless_route"):
        ConglomerateConfig.model_validate(d)


def test_exit_node_missing_reality():
    d = copy.deepcopy(_valid_config())
    del d["regions"][0]["nodes"][0]["reality"]
    with pytest.raises(ValidationError, match="must have reality config"):
        ConglomerateConfig.model_validate(d)


def test_exit_routing_invalid_destination():
    d = copy.deepcopy(_valid_config())
    # Exit routes can only use special destinations (direct/blocked/warp)
    d["regions"][0]["routing"] = {
        "routes": [
            {
                "destination": "hub1",
                "domains": ["a.com"],
            },
        ]
    }
    with pytest.raises(ValidationError, match="must be a special destination"):
        ConglomerateConfig.model_validate(d)


def test_non_exit_region_routing_routes_forbidden():
    d = copy.deepcopy(_valid_config())
    d["regions"][1]["routing"] = {
        "routes": [
            {
                "destination": "direct",
                "domains": ["a.com"],
            },
        ]
    }
    with pytest.raises(ValidationError, match="must not define routing.routes"):
        ConglomerateConfig.model_validate(d)


def test_lb_fallback_not_in_region():
    d = copy.deepcopy(_valid_config())
    d["regions"][0]["lb_fallback"] = "hubN1"  # hubN1 is in hub1 region, not exit1
    with pytest.raises(ValidationError, match="is not a node in that region"):
        ConglomerateConfig.model_validate(d)


def test_lb_fallback_valid():
    d = copy.deepcopy(_valid_config())
    d["regions"][0]["lb_fallback"] = "exitN1"
    cfg = ConglomerateConfig.model_validate(d)
    assert cfg.regions[0].lb_fallback == "exitN1"


def test_duplicate_group_ids():
    d = copy.deepcopy(_valid_config())
    d["groups"].append({"id": "grp1"})
    with pytest.raises(ValidationError, match="Duplicate group id"):
        ConglomerateConfig.model_validate(d)


def test_duplicate_usernames():
    d = copy.deepcopy(_valid_config())
    d["users"].append(
        {
            "username": "alice",
            "group": "grp1",
            "access": ["xhttp"],
        },
    )
    with pytest.raises(ValidationError, match="Duplicate username"):
        ConglomerateConfig.model_validate(d)


def test_user_references_unknown_group():
    d = copy.deepcopy(_valid_config())
    d["users"][0]["group"] = "nonexistent"
    with pytest.raises(ValidationError, match="references unknown group"):
        ConglomerateConfig.model_validate(d)


def test_hub_default_not_valid_region():
    d = copy.deepcopy(_valid_config())
    d["routing"]["hub_default"] = "ghost"
    with pytest.raises(ValidationError, match="is not a known region"):
        ConglomerateConfig.model_validate(d)


def test_hub_default_direct_valid():
    d = copy.deepcopy(_valid_config())
    d["routing"]["hub_default"] = "direct"
    cfg = ConglomerateConfig.model_validate(d)
    assert cfg.routing.hub_default == "direct"


def test_all_in_one_hub_only_no_exit_regions_valid():
    d = copy.deepcopy(_valid_config())
    # All-in-one: only a hub region, everything egresses direct, no exits.
    d["regions"] = [r for r in d["regions"] if r["type"] == "hub"]
    d["routing"]["hub_default"] = "direct"
    cfg = ConglomerateConfig.model_validate(d)
    assert [r.id for r in cfg.regions] == ["hub1"]
    assert cfg.routing.hub_default == "direct"


def test_haproxy_disabled_node_without_cdn_valid():
    d = copy.deepcopy(_valid_config())
    d["regions"][0]["nodes"][0]["haproxy"] = False
    cfg = ConglomerateConfig.model_validate(d)
    assert cfg.regions[0].nodes[0].haproxy is False


def test_cdn_with_haproxy_disabled_node_rejected():
    d = copy.deepcopy(_valid_config())
    d["global"]["cdn"] = {"exit_domain": "cdn-exit.test.ns", "hub_domain": "cdn-hub.test.ns"}
    d["regions"][0]["cdn_xhttp_path"] = "/cdn/"
    d["regions"][0]["nodes"][0]["haproxy"] = False
    with pytest.raises(ValidationError, match="CDN requires HAProxy"):
        ConglomerateConfig.model_validate(d)


def test_cdn_with_haproxy_disabled_via_default_rejected():
    d = copy.deepcopy(_valid_config())
    d["global"]["cdn"] = {"exit_domain": "cdn-exit.test.ns", "hub_domain": "cdn-hub.test.ns"}
    d["defaults"]["exit"]["haproxy"] = False
    d["regions"][0]["cdn_xhttp_path"] = "/cdn/"
    with pytest.raises(ValidationError, match="CDN requires HAProxy"):
        ConglomerateConfig.model_validate(d)


def test_exit_routes_global_invalid_destination():
    d = copy.deepcopy(_valid_config())
    d["routing"]["exit_routes_global"] = [
        {
            "destination": "hub1",
            "domains": ["cdn.example.com"],
        },
    ]
    with pytest.raises(ValidationError, match="must be a special destination"):
        ConglomerateConfig.model_validate(d)


def test_exit_routes_global_valid_special_destination():
    d = copy.deepcopy(_valid_config())
    d["routing"]["exit_routes_global"] = [
        {
            "destination": "direct",
            "ips": ["1.1.1.1"],
        },
    ]
    cfg = ConglomerateConfig.model_validate(d)
    assert len(cfg.routing.exit_routes_global) == 1


def test_hub_route_destination_unknown():
    d = copy.deepcopy(_valid_config())
    d["routing"]["hub_routes"] = [
        {
            "destination": "ghost-node",
            "domains": ["a.com"],
        },
    ]
    with pytest.raises(ValidationError, match="is unknown"):
        ConglomerateConfig.model_validate(d)


def test_hub_route_destination_region_valid():
    d = copy.deepcopy(_valid_config())
    d["routing"]["hub_routes"] = [
        {
            "destination": "exit1",
            "domains": ["a.com"],
        },
    ]
    cfg = ConglomerateConfig.model_validate(d)
    assert cfg.routing.hub_routes[0].destination == "exit1"


def test_hub_route_destination_node_valid():
    d = copy.deepcopy(_valid_config())
    d["routing"]["hub_routes"] = [
        {
            "destination": "exitN1",
            "domains": ["a.com"],
        },
    ]
    cfg = ConglomerateConfig.model_validate(d)
    assert cfg.routing.hub_routes[0].destination == "exitN1"


def test_hub_route_destination_special_valid():
    d = copy.deepcopy(_valid_config())
    d["routing"]["hub_routes"] = [
        {
            "destination": "direct",
            "domains": ["local.example.com"],
        },
    ]
    cfg = ConglomerateConfig.model_validate(d)
    assert cfg.routing.hub_routes[0].destination == "direct"


def test_hub_route_unknown_user():
    d = copy.deepcopy(_valid_config())
    d["routing"]["hub_routes"] = [
        {
            "destination": "exit1",
            "users": ["nobody"],
        },
    ]
    with pytest.raises(ValidationError, match="is not a known user"):
        ConglomerateConfig.model_validate(d)


def test_hub_route_unknown_proxy_user():
    d = copy.deepcopy(_valid_config())
    d["routing"]["hub_routes"] = [
        {
            "destination": "exit1",
            "proxy_users": ["nobody"],
        },
    ]
    with pytest.raises(ValidationError, match="is not a known user"):
        ConglomerateConfig.model_validate(d)


def test_hub_route_known_user_valid():
    d = copy.deepcopy(_valid_config())
    d["routing"]["hub_routes"] = [
        {
            "destination": "exit1",
            "users": ["alice"],
        },
    ]
    cfg = ConglomerateConfig.model_validate(d)
    assert cfg.routing.hub_routes[0].users == ["alice"]


def _config_with_portal(member_access: list[str]) -> dict:
    d = copy.deepcopy(_valid_config())
    d["users"][0]["access"] = member_access
    d["portals"] = [{"id": "home", "users": ["alice"], "routes": {"domains": ["home.example.com"]}}]
    return d


def _config_with_portals(portals: list[dict]) -> dict:
    d = copy.deepcopy(_valid_config())
    d["portals"] = portals
    return d


def _portal(**overrides) -> dict:
    return {"id": "home", "users": ["alice"], "routes": {"domains": ["home.example.com"]}} | overrides


def test_duplicate_portal_id_rejected():
    d = _config_with_portals([_portal(), _portal()])
    with pytest.raises(ValidationError, match="Duplicate portal id: 'home'"):
        ConglomerateConfig.model_validate(d)


@pytest.mark.parametrize("portal_id", ["hubN1", "hub1", "direct"])
def test_portal_id_colliding_with_reserved_name_rejected(portal_id):
    # Portal ids share a namespace with node ids, region ids and special destinations
    d = _config_with_portals([_portal(id=portal_id)])
    with pytest.raises(ValidationError, match="collides with a node id, region id, or special destination"):
        ConglomerateConfig.model_validate(d)


def test_portal_tag_colliding_with_derived_outbound_rejected():
    # A node named "home-portal" already owns the tag portal "home" derives
    d = _config_with_portals([_portal()])
    d["regions"][1]["nodes"].append({"id": "home-portal", "hostname": "home-portal.ap.test.ns"})
    with pytest.raises(ValidationError, match="collides with a derived outbound tag"):
        ConglomerateConfig.model_validate(d)


def test_portal_tag_starting_with_exit_region_id_rejected():
    # Balancer and observatory selectors match tag prefixes
    d = _config_with_portals([_portal(id="exit1x")])
    with pytest.raises(ValidationError, match="starts with exit region 'exit1'"):
        ConglomerateConfig.model_validate(d)


def test_portal_unknown_user_rejected():
    d = _config_with_portals([_portal(users=["nobody"])])
    with pytest.raises(ValidationError, match="references unknown user 'nobody'"):
        ConglomerateConfig.model_validate(d)


@pytest.mark.parametrize("access", [[], ["proxy"], ["server"]])
def test_portal_member_without_routable_access_rejected(access):
    with pytest.raises(ValidationError, match="has no access type carrying a routable identity"):
        ConglomerateConfig.model_validate(_config_with_portal(access))


def test_portal_member_with_wireguard_access_valid():
    # WireGuard peers carry user_email too, so wireguard-only members are routable
    d = _config_with_portal(["wireguard"])
    d["defaults"]["hub"]["wireguard"] = {"port": 51820, "subnet": "10.0.0.0/24"}
    cfg = ConglomerateConfig.model_validate(d)
    assert cfg.portals[0].users == ["alice"]


def test_portal_member_access_the_hub_does_not_render_rejected():
    # With no wireguard block the hub renders no inbound carrying the member's identity
    d = _config_with_portal(["wireguard"])
    with pytest.raises(ValidationError, match="hub nodes render: xhttp"):
        ConglomerateConfig.model_validate(d)


def test_portal_member_cdn_access_without_cdn_config_rejected():
    d = _config_with_portal(["cdn"])
    with pytest.raises(ValidationError, match="no access type carrying a routable identity"):
        ConglomerateConfig.model_validate(d)


def test_portal_with_unresolvable_wireguard_does_not_leak_derive_error():
    # An unresolvable wireguard subnet is a render-time error, not a schema one
    d = _config_with_portal(["xhttp"])
    d["regions"][1]["nodes"][0]["wireguard"] = {"enabled": True}
    cfg = ConglomerateConfig.model_validate(d)
    assert cfg.portals[0].users == ["alice"]


def _config_with_publish(publish: list[dict]) -> dict:
    d = copy.deepcopy(_valid_config())
    d["portals"] = [
        {
            "id": "home",
            "users": ["alice"],
            "routes": {"domains": ["home.example.com"]},
            "publish": publish,
        },
    ]
    return d


def test_portal_publish_valid():
    cfg = ConglomerateConfig.model_validate(_config_with_publish([{"port": 8443, "target": "192.168.1.10:443"}]))
    assert cfg.portals[0].publish[0].port == 8443


def test_portal_publish_unknown_node():
    d = _config_with_publish(
        [
            {
                "port": 8443,
                "target": "1.2.3.4:443",
                "nodes": ["ghost"],
            },
        ]
    )
    with pytest.raises(ValidationError, match="references unknown node"):
        ConglomerateConfig.model_validate(d)


def test_portal_publish_exit_node_rejected():
    d = _config_with_publish(
        [
            {
                "port": 8443,
                "target": "1.2.3.4:443",
                "nodes": ["exitN1"],
            },
        ]
    )
    with pytest.raises(ValidationError, match="outside a hub region"):
        ConglomerateConfig.model_validate(d)


def test_portal_publish_reality_port_reserved():
    d = _config_with_publish(
        [
            {
                "port": 443,
                "target": "1.2.3.4:443",
            },
        ]
    )
    with pytest.raises(ValidationError, match="already binds it for the reality inbound"):
        ConglomerateConfig.model_validate(d)


def test_portal_publish_proxy_port_reserved():
    d = _config_with_publish(
        [
            {
                "port": 80,
                "target": "1.2.3.4:80",
            },
        ]
    )
    d["defaults"]["hub"]["proxy_inbound"] = True
    with pytest.raises(ValidationError, match="already binds it for the proxy inbound"):
        ConglomerateConfig.model_validate(d)


def test_portal_publish_proxy_port_free_when_node_disables():
    d = _config_with_publish(
        [
            {
                "port": 80,
                "target": "1.2.3.4:80",
            },
        ]
    )
    d["defaults"]["hub"]["proxy_inbound"] = True
    d["regions"][1]["nodes"][0]["proxy_inbound"] = False
    cfg = ConglomerateConfig.model_validate(d)
    assert cfg.portals[0].publish[0].port == 80


def test_portal_publish_xdns_port_reserved():
    d = _config_with_publish(
        [
            {
                "port": 5353,
                "target": "1.2.3.4:53",
                "network": "udp",
            },
        ]
    )
    d["defaults"]["hub"]["xdns"] = {"domains": ["dns.example.com"], "port": 5353}
    d["users"][0]["access"] = ["xhttp", "xdns"]
    with pytest.raises(ValidationError, match="already binds it for the xdns inbound"):
        ConglomerateConfig.model_validate(d)


def test_portal_publish_tcp_free_on_udp_only_xdns_port():
    # xdns listens over mkcp (UDP), so the TCP socket on the same port is free
    d = _config_with_publish(
        [
            {
                "port": 5353,
                "target": "1.2.3.4:53",
            },
        ]
    )
    d["defaults"]["hub"]["xdns"] = {"domains": ["dns.example.com"], "port": 5353}
    d["users"][0]["access"] = ["xhttp", "xdns"]
    cfg = ConglomerateConfig.model_validate(d)
    assert cfg.portals[0].publish[0].port == 5353


def test_portal_publish_xdns_port_free_without_xdns_users():
    # No user carries xdns access, so the node renders no xdns inbound and the port is free
    d = _config_with_publish(
        [
            {
                "port": 5353,
                "target": "1.2.3.4:53",
            },
        ]
    )
    d["defaults"]["hub"]["xdns"] = {"domains": ["dns.example.com"], "port": 5353}
    cfg = ConglomerateConfig.model_validate(d)
    assert cfg.portals[0].publish[0].port == 5353


def test_portal_publish_wireguard_port_reserved():
    d = _config_with_publish(
        [
            {
                "port": 51820,
                "target": "1.2.3.4:51820",
                "network": "tcp,udp",
            },
        ]
    )
    d["defaults"]["hub"]["wireguard"] = {"port": 51820, "subnet": "10.0.0.0/24"}
    d["users"][0]["access"] = ["xhttp", "wireguard"]
    with pytest.raises(ValidationError, match="already binds it for the wireguard inbound"):
        ConglomerateConfig.model_validate(d)


def test_portal_publish_wireguard_node_port_override_reserved():
    d = _config_with_publish(
        [
            {"port": 51820, "target": "1.2.3.4:51820", "network": "udp"},
            {"port": 51821, "target": "1.2.3.4:51821", "network": "udp"},
        ],
    )
    d["defaults"]["hub"]["wireguard"] = {"port": 51820, "subnet": "10.0.0.0/24"}
    d["regions"][1]["nodes"][0]["wireguard"] = {"port": 51821}
    d["users"][0]["access"] = ["xhttp", "wireguard"]
    with pytest.raises(
        ValidationError, match="udp port 51821 on node 'hubN1', which already binds it for the wireguard"
    ):
        ConglomerateConfig.model_validate(d)


def test_portal_publish_wireguard_port_free_when_node_disables():
    d = _config_with_publish(
        [
            {
                "port": 51820,
                "target": "1.2.3.4:51820",
            },
        ]
    )
    d["defaults"]["hub"]["wireguard"] = {"port": 51820, "subnet": "10.0.0.0/24"}
    d["regions"][1]["nodes"][0]["wireguard"] = {"enabled": False}
    d["users"][0]["access"] = ["xhttp", "wireguard"]
    cfg = ConglomerateConfig.model_validate(d)
    assert cfg.portals[0].publish[0].port == 51820


def test_portal_publish_wireguard_port_free_without_wireguard_users():
    d = _config_with_publish(
        [
            {
                "port": 51820,
                "target": "1.2.3.4:51820",
            },
        ]
    )
    d["defaults"]["hub"]["wireguard"] = {"port": 51820, "subnet": "10.0.0.0/24"}
    cfg = ConglomerateConfig.model_validate(d)
    assert cfg.portals[0].publish[0].port == 51820


def test_portal_publish_metrics_port_reserved():
    d = _config_with_publish(
        [
            {
                "port": 10085,
                "target": "1.2.3.4:80",
            },
        ]
    )
    d["global"]["observability"] = {"metrics": {"enabled": True}}
    with pytest.raises(ValidationError, match="already binds it for the metrics api listener"):
        ConglomerateConfig.model_validate(d)


def test_portal_publish_metrics_node_port_override_reserved():
    d = _config_with_publish(
        [
            {"port": 10085, "target": "1.2.3.4:80"},
            {"port": 20085, "target": "1.2.3.4:81"},
        ],
    )
    d["defaults"]["hub"]["observability"] = {"metrics": {"enabled": True, "port": 20086}}
    d["regions"][1]["nodes"][0]["observability"] = {"metrics": {"port": 20085}}
    with pytest.raises(ValidationError, match="port 20085 on node 'hubN1', which already binds it for the metrics"):
        ConglomerateConfig.model_validate(d)


def test_portal_publish_metrics_port_free_when_disabled():
    cfg = ConglomerateConfig.model_validate(_config_with_publish([{"port": 10085, "target": "1.2.3.4:80"}]))
    assert cfg.portals[0].publish[0].port == 10085


def test_portal_without_any_hub_node_rejected():
    d = _config_with_publish([{"port": 8443, "target": "192.168.1.10:443"}])
    d["regions"] = [r for r in d["regions"] if r["type"] != "hub"]
    d["routing"]["hub_default"] = "exit1"
    with pytest.raises(ValidationError, match="Portals require at least one hub node"):
        ConglomerateConfig.model_validate(d)


def test_portal_publish_same_port_different_transport_rejected():
    # Both entries would render inbounds tagged "{id}-publish-{port}"
    d = _config_with_publish(
        [
            {"port": 9000, "target": "192.168.1.10:443", "network": "tcp"},
            {"port": 9000, "target": "192.168.1.11:443", "network": "udp"},
        ],
    )
    with pytest.raises(ValidationError, match="more than once"):
        ConglomerateConfig.model_validate(d)


def test_portal_publish_duplicate_port_same_portal():
    d = _config_with_publish(
        [
            {"port": 8443, "target": "192.168.1.10:443"},
            {"port": 8443, "target": "192.168.1.11:443"},
        ],
    )
    with pytest.raises(ValidationError, match="on node 'hubN1' more than once"):
        ConglomerateConfig.model_validate(d)


def test_portal_publish_duplicate_port_disjoint_nodes_valid():
    d = _config_with_publish(
        [
            {"port": 8443, "target": "192.168.1.10:443", "nodes": ["hubN1"]},
            {"port": 8443, "target": "192.168.1.11:443", "nodes": ["hubN2"]},
        ],
    )
    d["regions"][1]["nodes"].append({"id": "hubN2", "hostname": "hubN2.ap.test.ns"})
    cfg = ConglomerateConfig.model_validate(d)
    assert [p.port for p in cfg.portals[0].publish] == [8443, 8443]


def test_portal_publish_duplicate_port_intersecting_nodes_rejected():
    d = _config_with_publish(
        [
            {"port": 8443, "target": "192.168.1.10:443", "nodes": ["hubN1"]},
            {"port": 8443, "target": "192.168.1.11:443"},
        ],
    )
    d["regions"][1]["nodes"].append({"id": "hubN2", "hostname": "hubN2.ap.test.ns"})
    with pytest.raises(ValidationError, match="on node 'hubN1' more than once"):
        ConglomerateConfig.model_validate(d)


def test_portal_publish_duplicate_port_across_portals():
    d = _config_with_publish(
        [
            {
                "port": 8443,
                "target": "192.168.1.10:443",
            },
        ]
    )
    d["users"].append({"username": "bob", "group": "grp1", "access": ["xhttp"]})
    d["portals"].append(
        {
            "id": "office",
            "users": ["bob"],
            "routes": {"domains": ["office.example.com"]},
            "publish": [{"port": 8443, "target": "10.0.0.5:443"}],
        },
    )
    with pytest.raises(ValidationError, match="already published by portal 'home'"):
        ConglomerateConfig.model_validate(d)


def test_warp_vless_route_duplicate_with_exit():
    d = copy.deepcopy(_valid_config())
    # Set warp vless_route same as the exit region's vless_route
    d["regions"][0]["warp"] = {"vless_route": 1000}
    with pytest.raises(ValidationError, match="Duplicate warp vless_route"):
        ConglomerateConfig.model_validate(d)
