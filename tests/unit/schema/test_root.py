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


def test_warp_vless_route_duplicate_with_exit():
    d = copy.deepcopy(_valid_config())
    # Set warp vless_route same as the exit region's vless_route
    d["regions"][0]["warp"] = {"vless_route": 1000}
    with pytest.raises(ValidationError, match="Duplicate warp vless_route"):
        ConglomerateConfig.model_validate(d)
