from types import SimpleNamespace
from typing import cast

import pytest

from hexrift.components.derive.identity import Namespace
from hexrift.components.derive.wireguard import derive_user_wireguard_keypair, iter_hub_wireguard_allocs
from hexrift.components.keys.store import NodeKeys
from hexrift.components.schema.models.regions import Node, NodeWireguardOverride, WireguardConfig
from hexrift.components.schema.models.root import ConglomerateConfig
from hexrift.errors import DeriveError
from hexrift.inbounds.base import InboundEnv
from hexrift.inbounds.wireguard import WIREGUARD_SPEC, get_hub_wireguard_peers, resolve_node_wireguard
from hexrift.shared.crypto import x25519_urlsafe_to_std
from tests.unit.inbounds.helpers import make_defaults, make_hub_region, make_user


_BASE_WG = WireguardConfig(subnet="10.0.0.0/24", port=443, mtu=1420, keepalive=25)
_PRIV = "mZ0iHOiFoN3JfGgq_7D7GwvEcMwqJEbT7T5VyqK7Rnk"  # any 32-byte urlsafe-b64 key


class TestResolveNodeWireguard:
    def test_falls_back_to_hub_default(self):
        node = Node(id="n", hostname="h.example.com")
        result = resolve_node_wireguard(node, make_defaults(wireguard=_BASE_WG))
        assert result == _BASE_WG

    def test_none_when_unconfigured(self):
        node = Node(id="n", hostname="h.example.com")
        assert resolve_node_wireguard(node, make_defaults()) is None

    def test_override_disabled(self):
        node = Node(id="n", hostname="h.example.com", wireguard=NodeWireguardOverride(enabled=False))
        assert resolve_node_wireguard(node, make_defaults(wireguard=_BASE_WG)) is None

    def test_override_merges_on_base(self):
        node = Node(id="n", hostname="h.example.com", wireguard=NodeWireguardOverride(port=51820))
        result = resolve_node_wireguard(node, make_defaults(wireguard=_BASE_WG))
        assert result is not None
        assert result.port == 51820
        assert result.subnet == "10.0.0.0/24"  # from base
        assert result.keepalive == 25  # from base

    def test_override_without_subnet_or_base_raises(self):
        node = Node(id="n", hostname="h.example.com", wireguard=NodeWireguardOverride(port=51820))
        with pytest.raises(DeriveError):
            resolve_node_wireguard(node, make_defaults())

    def test_override_subnet_without_base(self):
        node = Node(id="n", hostname="h.example.com", wireguard=NodeWireguardOverride(subnet="10.9.0.0/24"))
        result = resolve_node_wireguard(node, make_defaults())
        assert result is not None
        assert result.subnet == "10.9.0.0/24"
        assert result.port == 443  # built-in default


class TestGetHubWireguardPeers:
    def test_peer_per_identity_with_derived_keys(self):
        ns = Namespace("t.ns")
        users = [
            make_user(
                "alice",
                access=["wireguard", "server"],
                guests=["laptop"],
            ),
        ]
        peers = get_hub_wireguard_peers(users, ns, "10.0.0.0/24", _PRIV, keepalive=25)
        # Canonical order: user .2 (server holds .1), server identity .3, guest .4
        assert [p["email"] for p in peers] == [
            "alice@t.ns",
            "alice-server@alice",
            "laptop@alice",
        ]
        assert [p["allowedIPs"] for p in peers] == [
            ["10.0.0.2/32"],
            ["10.0.0.3/32"],
            ["10.0.0.4/32"],
        ]
        assert all(p["keepAlive"] == 25 for p in peers)
        alloc = next(iter_hub_wireguard_allocs(users, ns, "10.0.0.0/24"))
        _, expected_pub = derive_user_wireguard_keypair(_PRIV, alloc.identity_uuid, ns.name)
        assert peers[0]["publicKey"] == expected_pub

    def test_no_wireguard_users_no_peers(self):
        ns = Namespace("t.ns")
        users = [make_user("alice", access=["xhttp"])]
        assert get_hub_wireguard_peers(users, ns, "10.0.0.0/24", _PRIV) == []


def _make_env(users: list, wireguard: WireguardConfig | None = None) -> InboundEnv:
    cfg = cast(
        ConglomerateConfig,
        SimpleNamespace(
            defaults=make_defaults(wireguard=wireguard),
            users=users,
            global_=SimpleNamespace(namespace="t.ns"),
        ),
    )
    region = make_hub_region()
    node_keys = NodeKeys(
        reality_private_key=_PRIV,
        reality_public_key=_PRIV,
        decryption="none",
        encryption="none",
    )
    return InboundEnv(config=cfg, region=region, node=region.nodes[0], node_keys=node_keys)


class TestWireguardSpecBuildContext:
    def test_none_when_unconfigured(self):
        env = _make_env(users=[make_user(access=["wireguard"])])
        assert WIREGUARD_SPEC.build_context(env) is None

    def test_none_when_no_peers(self):
        env = _make_env(users=[make_user(access=["xhttp"])], wireguard=_BASE_WG)
        assert WIREGUARD_SPEC.build_context(env) is None

    def test_context_with_allocated_peers(self):
        env = _make_env(users=[make_user(access=["wireguard"], guests=["laptop"])], wireguard=_BASE_WG)
        ctx = WIREGUARD_SPEC.build_context(env)
        assert ctx is not None
        assert ctx.config == _BASE_WG
        assert ctx.secret_key == x25519_urlsafe_to_std(_PRIV)
        assert [p["allowedIPs"] for p in ctx.peers] == [["10.0.0.2/32"], ["10.0.0.3/32"]]
