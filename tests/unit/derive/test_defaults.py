from ipaddress import IPv4Address

import pytest
from pydantic import ValidationError

from hexrift.components.derive.defaults import (
    derive_server_names,
    derive_xhttp_host,
    resolve_node_haproxy,
    resolve_node_ipv6,
    resolve_node_observability,
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
from hexrift.components.schema.models.global_ import GlobalConfig
from hexrift.components.schema.models.observability import (
    LoggingOverride,
    MetricsOverride,
    ObservabilityConfig,
    ObservabilityOverride,
)
from hexrift.components.schema.models.regions import Node, Region
from hexrift.components.schema.models.shared import RealityConfig
from hexrift.constants import AuthMethod, HandshakeMethod, LogLevel, RegionType, TlsFingerprint
from hexrift.errors import DeriveError


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


def _global(observability: ObservabilityConfig | None = None) -> GlobalConfig:
    return GlobalConfig(
        namespace="test.ns",
        aphelion_domain="ap.test.ns",
        observability=observability if observability is not None else ObservabilityConfig(),
    )


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
        with pytest.raises(DeriveError, match="must have a reality config"):
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


class TestResolveNodeHaproxy:
    def test_node_override_false(self):
        node = Node(id="n", hostname="h", haproxy=False)
        assert resolve_node_haproxy(node, _exit_region(), _defaults()) is False

    def test_node_override_true_beats_default(self):
        defaults = DefaultsConfig(
            exit=ExitDefaults(ipv6=True, haproxy=False, keys=_EXIT_KEYS),
            hub=HubDefaults(
                ipv6=False,
                keys=_HUB_KEYS,
                exit_connections=_EXIT_CONNS,
                reality=_HUB_REALITY,
                observatory=ObservatoryConfig(),
            ),
        )
        node = Node(id="n", hostname="h", haproxy=True)
        assert resolve_node_haproxy(node, _exit_region(), defaults) is True

    def test_default_true_when_none(self):
        node = Node(id="n", hostname="h")
        assert resolve_node_haproxy(node, _exit_region(), _defaults()) is True
        assert resolve_node_haproxy(node, _hub_region(), _defaults()) is True

    def test_exit_default_false_honored(self):
        defaults = DefaultsConfig(
            exit=ExitDefaults(ipv6=True, haproxy=False, keys=_EXIT_KEYS),
            hub=HubDefaults(
                ipv6=False,
                keys=_HUB_KEYS,
                exit_connections=_EXIT_CONNS,
                reality=_HUB_REALITY,
                observatory=ObservatoryConfig(),
            ),
        )
        node = Node(id="n", hostname="h")
        assert resolve_node_haproxy(node, _exit_region(), defaults) is False
        # hub default still True
        assert resolve_node_haproxy(node, _hub_region(), defaults) is True


class TestResolveNodeObservability:
    def test_global_only_when_no_overrides(self):
        global_ = _global(
            ObservabilityConfig.model_validate(
                {
                    "metrics": {"enabled": True, "port": 9000},
                    "logging": {"loglevel": "info"},
                },
            )
        )
        node = Node(id="n", hostname="h")
        result = resolve_node_observability(node, _hub_region(), _defaults(), global_)
        assert result.metrics.enabled is True
        assert result.metrics.port == 9000
        assert result.logging.loglevel is LogLevel.INFO

    def test_built_in_defaults_when_nothing_configured(self):
        node = Node(id="n", hostname="h")
        result = resolve_node_observability(node, _hub_region(), _defaults(), _global())
        assert result.metrics.enabled is False
        assert result.metrics.listen == IPv4Address("127.0.0.1")
        assert result.metrics.port == 10085
        assert result.logging.loglevel is LogLevel.NONE

    def test_role_override_beats_global(self):
        global_ = _global(
            ObservabilityConfig.model_validate(
                {
                    "metrics": {
                        "enabled": False,
                        "port": 9000,
                    },
                },
            )
        )
        defaults = DefaultsConfig(
            exit=ExitDefaults(ipv6=True, keys=_EXIT_KEYS),
            hub=HubDefaults(
                ipv6=False,
                keys=_HUB_KEYS,
                exit_connections=_EXIT_CONNS,
                reality=_HUB_REALITY,
                observatory=ObservatoryConfig(),
                observability=ObservabilityOverride(metrics=MetricsOverride(enabled=True)),
            ),
        )
        node = Node(id="n", hostname="h")
        result = resolve_node_observability(node, _hub_region(), defaults, global_)
        assert result.metrics.enabled is True  # role override wins
        assert result.metrics.port == 9000  # inherited from global (role didn't set it)

    def test_role_override_only_applies_to_matching_region_type(self):
        defaults = DefaultsConfig(
            exit=ExitDefaults(ipv6=True, keys=_EXIT_KEYS),
            hub=HubDefaults(
                ipv6=False,
                keys=_HUB_KEYS,
                exit_connections=_EXIT_CONNS,
                reality=_HUB_REALITY,
                observatory=ObservatoryConfig(),
                observability=ObservabilityOverride(metrics=MetricsOverride(enabled=True)),
            ),
        )
        node = Node(id="n", hostname="h")
        # exit region: hub-scoped role override must not apply
        result = resolve_node_observability(node, _exit_region(), defaults, _global())
        assert result.metrics.enabled is False

    def test_node_override_beats_role_and_global(self):
        global_ = _global(
            ObservabilityConfig.model_validate(
                {
                    "metrics": {
                        "port": 9000,
                    },
                },
            )
        )
        defaults = DefaultsConfig(
            exit=ExitDefaults(ipv6=True, keys=_EXIT_KEYS),
            hub=HubDefaults(
                ipv6=False,
                keys=_HUB_KEYS,
                exit_connections=_EXIT_CONNS,
                reality=_HUB_REALITY,
                observatory=ObservatoryConfig(),
                observability=ObservabilityOverride(
                    metrics=MetricsOverride(
                        enabled=True,
                        port=9001,
                    ),
                ),
            ),
        )
        node = Node(
            id="n",
            hostname="h",
            observability=ObservabilityOverride(
                metrics=MetricsOverride(
                    port=9002,
                ),
            ),
        )
        result = resolve_node_observability(node, _hub_region(), defaults, global_)
        assert result.metrics.enabled is True  # inherited from role (node didn't set it)
        assert result.metrics.port == 9002  # node override wins over role and global

    def test_none_fields_inherit_individually(self):
        # node override only sets `online`; enabled/listen/port/user_stats fall through
        # role -> global -> built-in default, and logging is untouched entirely.
        global_ = _global(
            ObservabilityConfig.model_validate(
                {
                    "metrics": {
                        "enabled": True,
                        "listen": "10.0.0.5",
                        "port": 9000,
                    },
                },
            )
        )
        node = Node(
            id="n",
            hostname="h",
            observability=ObservabilityOverride(
                metrics=MetricsOverride(online=False),
            ),
        )
        result = resolve_node_observability(node, _hub_region(), _defaults(), global_)
        assert result.metrics.enabled is True
        assert result.metrics.listen == IPv4Address("10.0.0.5")
        assert result.metrics.port == 9000
        assert result.metrics.user_stats is True
        assert result.metrics.online is False
        assert result.logging.loglevel is LogLevel.NONE

    def test_node_logging_override_independent_of_metrics(self):
        node = Node(
            id="n",
            hostname="h",
            observability=ObservabilityOverride(
                logging=LoggingOverride(loglevel=LogLevel.WARNING),
            ),
        )
        result = resolve_node_observability(node, _hub_region(), _defaults(), _global())
        assert result.logging.loglevel is LogLevel.WARNING
        assert result.logging.access == "none"
        assert result.metrics.enabled is False


class TestDeriveServerNames:
    def test_explicit_server_names_returned(self):
        r = RealityConfig(dest="a.com:443", server_names=["cdn.a.com"], xhttp_path="/p/")
        assert derive_server_names(r) == ["cdn.a.com"]

    def test_extracted_from_dest_host_port(self):
        r = RealityConfig(dest="vk.com:443", xhttp_path="/p/")
        assert derive_server_names(r) == ["vk.com"]

    def test_dest_without_port_rejected(self):
        # reality dest must be host:port; a port-less dest is now rejected at the model level.
        with pytest.raises(ValidationError, match="host:port"):
            RealityConfig(dest="vk.com", xhttp_path="/p/")

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
        with pytest.raises(DeriveError, match="missing"):
            derive_xhttp_host(r)
