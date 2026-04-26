from pathlib import Path

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


@pytest.fixture()
def topology_yaml(tmp_path: Path) -> Path:
    p = tmp_path / "topology.yaml"
    p.write_text(yaml.dump(MINIMAL_TOPOLOGY))
    return p


@pytest.fixture()
def app(topology_yaml: Path) -> HexRiftApp:
    return HexRiftApp(yaml_path=topology_yaml)
