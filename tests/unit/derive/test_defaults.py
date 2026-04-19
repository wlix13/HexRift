import pytest

from hexrift.components.derive.defaults import (
    derive_server_names,
    derive_xhttp_host,
    resolve_node_ipv6,
    resolve_node_keys,
    resolve_node_mtproto,
    resolve_node_reality,
)
from hexrift.components.schema.models.defaults import (
    DefaultsConfig,
    ExitConnectionsConfig,
    ExitDefaults,
    HubDefaults,
    KeysConfig,
    ObservatoryConfig,
)
from hexrift.components.schema.models.regions import (
    MtprotoConfig,
    Node,
    NodeKeysOverride,
    NodeMtprotoOverride,
    Region,
)
from hexrift.components.schema.models.shared import RealityConfig
from hexrift.constants import AuthMethod, RegionType


_EXIT_KEYS = KeysConfig(mode="native", session_time="600s", auth=AuthMethod.MLKEM768)
_HUB_KEYS = KeysConfig(mode="native", session_time="600s", auth=AuthMethod.X25519)
_HUB_REALITY = RealityConfig(dest="vk.com:443", xhttp_path="/hub/")
_EXIT_CONNS = ExitConnectionsConfig(method="mlkem768x25519plus", fingerprint="chrome")


def _defaults(*, hub_mtproto: MtprotoConfig | None = None) -> DefaultsConfig:
    return DefaultsConfig(
        exit=ExitDefaults(ipv6=True, keys=_EXIT_KEYS),
        hub=HubDefaults(
            ipv6=False,
            keys=_HUB_KEYS,
            exit_connections=_EXIT_CONNS,
            reality=_HUB_REALITY,
            mtproto=hub_mtproto,
            observatory=ObservatoryConfig(),
        ),
    )


def _exit_region(**kwargs) -> Region:
    defaults = {
        "id": "exit1",
        "type": RegionType.EXIT,
        "vless_route": 1000,
        "nodes": [
            Node(
                id="exitN1",
                hostname="e.test.ns",
                reality=RealityConfig(dest="a.com:443", xhttp_path="/x/"),
            ),
        ],
    }
    defaults.update(kwargs)
    return Region.model_validate(defaults)


def _hub_region(**kwargs) -> Region:
    defaults = {
        "id": "hub1",
        "type": RegionType.HUB,
        "nodes": [
            Node(
                id="hubN1",
                hostname="h.test.ns",
            ),
        ],
    }
    defaults.update(kwargs)
    return Region.model_validate(defaults)


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


class TestResolveNodeReality:
    def test_node_override_returned_as_is(self):
        node_reality = RealityConfig(dest="b.com:443", xhttp_path="/b/")
        node = Node(id="n", hostname="h.example.com", reality=node_reality)
        result = resolve_node_reality(node, _exit_region(), _defaults())
        assert result.dest == "b.com:443"

    def test_hub_node_falls_back_to_hub_default(self):
        node = Node(id="n", hostname="h.example.com")
        result = resolve_node_reality(node, _hub_region(), _defaults())
        assert result.dest == _HUB_REALITY.dest

    def test_exit_node_no_reality_raises(self):
        node = Node(id="n", hostname="h.example.com")
        # Build exit region manually without requiring node reality (region doesn't validate this)
        region = Region(
            id="exit1",
            type=RegionType.EXIT,
            vless_route=1000,
            nodes=[
                Node(
                    id="n",
                    hostname="h.example.com",
                ),
            ],
        )
        with pytest.raises(ValueError, match="must have a reality config"):
            resolve_node_reality(node, region, _defaults())


class TestResolveNodeIpv6:
    def test_node_override_true(self):
        node = Node(id="n", hostname="h", ipv6=True)
        assert resolve_node_ipv6(node, _exit_region(), _defaults()) is True

    def test_node_override_false(self):
        node = Node(id="n", hostname="h", ipv6=False)
        assert resolve_node_ipv6(node, _exit_region(), _defaults()) is False

    def test_exit_default_when_none(self):
        node = Node(id="n", hostname="h")
        # defaults().exit.ipv6 = True
        assert resolve_node_ipv6(node, _exit_region(), _defaults()) is True

    def test_hub_default_when_none(self):
        node = Node(id="n", hostname="h")
        # defaults().hub.ipv6 = False
        assert resolve_node_ipv6(node, _hub_region(), _defaults()) is False


class TestResolveNodeMtproto:
    def test_no_override_no_base_returns_none(self):
        node = Node(id="n", hostname="h")
        assert resolve_node_mtproto(node, _defaults()) is None

    def test_no_override_with_base_returns_base(self):
        base = MtprotoConfig(domain="tg.example.com", port=4321)
        node = Node(id="n", hostname="h")
        result = resolve_node_mtproto(node, _defaults(hub_mtproto=base))
        assert result is not None
        assert result.domain == "tg.example.com"

    def test_enabled_false_returns_none(self):
        base = MtprotoConfig(domain="tg.example.com")
        node = Node(id="n", hostname="h", mtproto=NodeMtprotoOverride(enabled=False))
        assert resolve_node_mtproto(node, _defaults(hub_mtproto=base)) is None

    def test_domain_override_replaces_base(self):
        base = MtprotoConfig(domain="old.example.com")
        node = Node(id="n", hostname="h", mtproto=NodeMtprotoOverride(domain="new.example.com"))
        result = resolve_node_mtproto(node, _defaults(hub_mtproto=base))
        assert result is not None
        assert result.domain == "new.example.com"

    def test_override_without_domain_no_base_raises(self):
        node = Node(id="n", hostname="h", mtproto=NodeMtprotoOverride(port=5678))
        with pytest.raises(ValueError, match="domain must be set"):
            resolve_node_mtproto(node, _defaults())


class TestDeriveServerNames:
    def test_explicit_server_names_returned(self):
        r = RealityConfig(dest="a.com:443", server_names=["cdn.a.com"], xhttp_path="/p/")
        assert derive_server_names(r) == ["cdn.a.com"]

    def test_extracted_from_dest_host_port(self):
        r = RealityConfig(dest="vk.com:443", xhttp_path="/p/")
        assert derive_server_names(r) == ["vk.com"]

    def test_extracted_from_dest_without_port(self):
        r = RealityConfig(dest="vk.com", xhttp_path="/p/")
        # rsplit(":", 1)[0] with no ":" gives the whole string
        assert derive_server_names(r) == ["vk.com"]

    def test_ipv6_bracketed_dest(self):
        r = RealityConfig(dest="[::1]:443", xhttp_path="/p/")
        assert derive_server_names(r) == ["::1"]


class TestDeriveXhttpHost:
    def test_explicit_xhttp_host_returned(self):
        r = RealityConfig(dest="a.com:443", xhttp_host="cdn.a.com", xhttp_path="/p/")
        assert derive_xhttp_host(r) == "cdn.a.com"

    def test_extracted_from_dest(self):
        r = RealityConfig(dest="vk.com:443", xhttp_path="/p/")
        assert derive_xhttp_host(r) == "vk.com"

    def test_malformed_ipv6_raises(self):
        r = RealityConfig.model_construct(
            dest="[::1",
            xhttp_path="/p/",
            xhttp_host=None,
            server_names=None,
            fallback_limits=None,
        )
        with pytest.raises(ValueError, match="missing"):
            derive_xhttp_host(r)
