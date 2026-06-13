from hexrift.components.keys.defaults import resolve_node_keys
from hexrift.components.schema.models.defaults import (
    DefaultsConfig,
    ExitConnectionsConfig,
    ExitDefaults,
    HubDefaults,
    KeysConfig,
    ObservatoryConfig,
)
from hexrift.components.schema.models.regions import Node, NodeKeysOverride, Region
from hexrift.components.schema.models.shared import RealityConfig
from hexrift.constants import AuthMethod, HandshakeMethod, RegionType, TlsFingerprint


_EXIT_KEYS = KeysConfig(mode="native", session_time="600s", auth=AuthMethod.MLKEM768)
_HUB_KEYS = KeysConfig(mode="native", session_time="600s", auth=AuthMethod.X25519)
_HUB_REALITY = RealityConfig(dest="vk.com:443", xhttp_path="/hub/")
_EXIT_CONNS = ExitConnectionsConfig(method=HandshakeMethod.MLKEM768, fingerprint=TlsFingerprint.CHROME)


def _defaults() -> DefaultsConfig:
    return DefaultsConfig(
        exit=ExitDefaults(ipv6=True, keys=_EXIT_KEYS),
        hub=HubDefaults(
            ipv6=False,
            keys=_HUB_KEYS,
            exit_connections=_EXIT_CONNS,
            reality=_HUB_REALITY,
            observatory=ObservatoryConfig(),
        ),
    )


def _exit_region() -> Region:
    return Region.model_validate(
        {
            "id": "exit1",
            "type": RegionType.EXIT,
            "vless_route": 1000,
            "nodes": [
                Node(
                    id="exitN1",
                    hostname="e.test.ns",
                    reality=RealityConfig(
                        dest="a.com:443",
                        xhttp_path="/x/",
                    ),
                ),
            ],
        }
    )


def _hub_region() -> Region:
    return Region.model_validate(
        {
            "id": "hub1",
            "type": RegionType.HUB,
            "nodes": [
                Node(
                    id="hubN1",
                    hostname="h.test.ns",
                )
            ],
        }
    )


class TestResolveNodeKeys:
    def test_exit_no_override_returns_exit_defaults(self):
        node = Node(id="n", hostname="h.example.com")
        result = resolve_node_keys(node, _exit_region(), _defaults())
        assert result.auth == "mlkem768"
        assert result.mode == "native"

    def test_hub_no_override_returns_hub_defaults(self):
        node = Node(id="n", hostname="h.example.com")
        result = resolve_node_keys(node, _hub_region(), _defaults())
        assert result.auth == "x25519"

    def test_override_mode_replaces_base(self):
        node = Node(id="n", hostname="h.example.com", keys=NodeKeysOverride(mode="auto"))
        result = resolve_node_keys(node, _exit_region(), _defaults())
        assert result.mode == "auto"
        assert result.session_time == "600s"  # not overridden

    def test_override_enabled_false(self):
        node = Node(id="n", hostname="h.example.com", keys=NodeKeysOverride(enabled=False))
        result = resolve_node_keys(node, _exit_region(), _defaults())
        assert result.enabled is False

    def test_partial_override_keeps_base_fields(self):
        node = Node(id="n", hostname="h.example.com", keys=NodeKeysOverride(session_time="300s"))
        result = resolve_node_keys(node, _exit_region(), _defaults())
        assert result.session_time == "300s"
        assert result.mode == "native"  # from base
