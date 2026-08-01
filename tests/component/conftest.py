import copy
from pathlib import Path
from typing import Any

import pytest
import yaml

from hexrift.app import HexRiftApp


MINIMAL_TOPOLOGY: dict = {
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
    "portals": [
        {
            "id": "home",
            "users": ["alice"],
            "routes": {
                "domains": [
                    "home.alice.example.com",
                ],
            },
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
                    "reality": {"dest": "a.com:443", "xhttp_path": "/x/"},
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


def _deep_merge(base: dict, overrides: dict) -> dict:
    """Recursively merge `overrides` into `base`."""

    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def make_topology(**overrides: Any) -> dict:
    """Return deep copy of `MINIMAL_TOPOLOGY` with per-test overrides deep-merged in."""

    return _deep_merge(copy.deepcopy(MINIMAL_TOPOLOGY), overrides)


@pytest.fixture()
def topology_yaml(tmp_path: Path) -> Path:
    p = tmp_path / "topology.yaml"
    p.write_text(yaml.dump(MINIMAL_TOPOLOGY))
    return p


@pytest.fixture()
def app(topology_yaml: Path) -> HexRiftApp:
    return HexRiftApp(yaml_path=topology_yaml)
