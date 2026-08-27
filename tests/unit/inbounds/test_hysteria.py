from types import SimpleNamespace
from typing import cast
from uuid import UUID

from hexrift.components.derive.hysteria import derive_hysteria_certificate, derive_hysteria_obfs_password
from hexrift.components.derive.identity import Namespace
from hexrift.components.keys.store import NodeKeys
from hexrift.components.schema.models.regions import HysteriaCertificate, HysteriaConfig, HysteriaOverride, Node, Region
from hexrift.components.schema.models.resolve import resolve_node_hysteria
from hexrift.components.schema.models.root import ConglomerateConfig
from hexrift.components.schema.models.shared import RealityConfig
from hexrift.constants import ExitProtocol, HysteriaCongestion, RegionType
from hexrift.inbounds.base import InboundEnv
from hexrift.inbounds.hysteria import HYSTERIA_SPEC, build_hysteria_share_url
from hexrift.links.registry import render_link
from tests.unit.inbounds.helpers import make_defaults, make_hub_region, make_user
from tests.unit.render.helpers import make_shared


_PRIV = "mZ0iHOiFoN3JfGgq_7D7GwvEcMwqJEbT7T5VyqK7Rnk"
_KEYS = NodeKeys(reality_private_key=_PRIV, reality_public_key=_PRIV, decryption="none", encryption="none")
_EXIT_REALITY = RealityConfig(dest="a.com:443", xhttp_path="/x/")


def _hub_env(users: list, hysteria: HysteriaConfig | None = None, node: Node | None = None) -> InboundEnv:
    cfg = cast(
        ConglomerateConfig,
        SimpleNamespace(
            defaults=make_defaults(hysteria=hysteria), users=users, global_=SimpleNamespace(namespace="t.ns")
        ),
    )
    region = make_hub_region(nodes=[node]) if node is not None else make_hub_region()
    return InboundEnv(config=cfg, region=region, node=region.nodes[0], node_keys=_KEYS)


def _exit_env(hub_nodes: list[Node], protocol: ExitProtocol | None = ExitProtocol.HYSTERIA) -> InboundEnv:
    region = Region(
        id="exit1",
        type=RegionType.EXIT,
        vless_route=1000,
        protocol=protocol,
        nodes=[Node(id="exitN1", hostname="e.test.ns", reality=_EXIT_REALITY)],
    )
    hub_region = make_hub_region(nodes=hub_nodes)
    cfg = cast(
        ConglomerateConfig,
        SimpleNamespace(
            defaults=make_defaults(),
            users=[],
            regions=[region, hub_region],
            global_=SimpleNamespace(namespace="t.ns"),
        ),
    )
    return InboundEnv(config=cfg, region=region, node=region.nodes[0], node_keys=_KEYS)


class TestResolveNodeHysteria:
    def test_hub_none_when_unconfigured(self):
        region = make_hub_region()
        assert resolve_node_hysteria(region.nodes[0], region, make_defaults()) is None

    def test_hub_node_override_enables_over_built_in_defaults(self):
        node = Node(id="n", hostname="h.test.ns", hysteria=HysteriaOverride(port=8443))
        region = make_hub_region(nodes=[node])
        result = resolve_node_hysteria(node, region, make_defaults())
        assert result == HysteriaConfig(port=8443)

    def test_hub_node_override_disabled(self):
        node = Node(id="n", hostname="h.test.ns", hysteria=HysteriaOverride(enabled=False))
        region = make_hub_region(nodes=[node])
        assert resolve_node_hysteria(node, region, make_defaults(hysteria=HysteriaConfig())) is None

    def test_exit_layers_defaults_region_node(self):
        node = Node(id="e", hostname="e.test.ns", reality=_EXIT_REALITY, hysteria=HysteriaOverride(sni="e.example.com"))
        region = Region(
            id="exit1",
            type=RegionType.EXIT,
            vless_route=1,
            protocol=ExitProtocol.HYSTERIA,
            hysteria=HysteriaOverride(port=8443),
            nodes=[node],
        )
        defaults = make_defaults(exit_hysteria=HysteriaConfig(obfs=True, congestion=HysteriaCongestion.BBR))
        assert resolve_node_hysteria(node, region, defaults) == HysteriaConfig(
            port=8443, obfs=True, sni="e.example.com"
        )

    def test_exit_none_unless_region_protocol_is_hysteria(self):
        node = Node(id="e", hostname="e.test.ns", reality=_EXIT_REALITY)
        region = Region(id="exit1", type=RegionType.EXIT, vless_route=1, nodes=[node])
        assert resolve_node_hysteria(node, region, make_defaults(exit_hysteria=HysteriaConfig())) is None

    def test_exit_listens_when_hysteria_defined_under_vless(self):
        node = Node(id="e", hostname="e.test.ns", reality=_EXIT_REALITY, hysteria=HysteriaOverride(obfs=True))
        region = Region(id="exit1", type=RegionType.EXIT, vless_route=1, nodes=[node])
        hy = resolve_node_hysteria(node, region, make_defaults())
        assert hy is not None and hy.obfs is True


class TestHysteriaSpecBuildContext:
    def test_none_without_hysteria_users(self):
        env = _hub_env(users=[make_user(access=["xhttp"])], hysteria=HysteriaConfig())
        assert HYSTERIA_SPEC.build_context(env) is None

    def test_hub_users_are_uuid_auths_for_user_server_and_guests(self):
        user = make_user("alice", access=["hysteria", "server"], guests=["laptop"])
        ctx = HYSTERIA_SPEC.build_context(_hub_env(users=[user], hysteria=HysteriaConfig()))
        assert ctx is not None
        ns = Namespace("t.ns")
        base = ns.user_uuid("alice")
        assert ctx.users == [
            {"auth": str(base), "email": "alice@t.ns"},
            {"auth": str(ns.server_uuid("alice", user_base=base)), "email": "alice-server@alice"},
            {"auth": str(ns.guest_uuid("laptop", "alice", user_base=base)), "email": "laptop@alice"},
        ]
        assert ctx.sni == "vk.com"  # hub default reality dest host
        assert ctx.masquerade_url == "https://vk.com/"
        assert ctx.certificates[0]["certificate"][0] == "-----BEGIN CERTIFICATE-----"
        assert ctx.obfs_password is None

    def test_exit_users_are_hub_exit_identities(self):
        hubs = [Node(id="hubN1", hostname="h1.test.ns"), Node(id="hubN2", hostname="h2.test.ns")]
        ctx = HYSTERIA_SPEC.build_context(_exit_env(hubs))
        assert ctx is not None
        ns = Namespace("t.ns")
        assert ctx.users == [
            {"auth": str(ns.hub_exit_uuid("hubN1", "exitN1")), "email": "hubN1-exitN1@t.ns"},
            {"auth": str(ns.hub_exit_uuid("hubN2", "exitN1")), "email": "hubN2-exitN1@t.ns"},
        ]

    def test_exit_none_when_region_dials_over_vless(self):
        assert HYSTERIA_SPEC.build_context(_exit_env([Node(id="hubN1", hostname="h1.test.ns")], protocol=None)) is None

    def test_exit_none_without_hub_nodes(self):
        assert HYSTERIA_SPEC.build_context(_exit_env([])) is None

    def test_operator_certificate_files_and_obfs(self):
        hy = HysteriaConfig(
            obfs=True, sni="hub.example.com", certificate=HysteriaCertificate(cert_file="/c.pem", key_file="/k.pem")
        )
        ctx = HYSTERIA_SPEC.build_context(_hub_env(users=[make_user(access=["hysteria"])], hysteria=hy))
        assert ctx is not None
        assert ctx.certificates == [{"certificateFile": "/c.pem", "keyFile": "/k.pem"}]
        assert ctx.obfs_password == derive_hysteria_obfs_password(_PRIV, "t.ns")


class TestHysteriaSpecFragment:
    def test_fragment_shape(self):
        env = _hub_env(users=[make_user(access=["hysteria"])], hysteria=HysteriaConfig())
        ctx = HYSTERIA_SPEC.build_context(env)
        assert ctx is not None
        frag = HYSTERIA_SPEC.fragment(ctx, make_shared(ipv6=True, route_only=True))
        cert = derive_hysteria_certificate(_PRIV, "vk.com", "t.ns")
        assert frag["tag"] == "hysteria-in"
        assert (frag["listen"], frag["port"], frag["protocol"]) == ("::", 443, "hysteria")
        assert frag["settings"] == {"version": 2, "users": ctx.users}
        ss = frag["streamSettings"]
        assert (ss["network"], ss["security"]) == ("hysteria", "tls")
        assert ss["tlsSettings"] == {
            "certificates": [
                {"certificate": cert.cert_pem.strip().splitlines(), "key": cert.key_pem.strip().splitlines()}
            ],
            "alpn": ["h3"],
            "minVersion": "1.3",
            "enableSessionResumption": True,
        }
        assert ss["hysteriaSettings"] == {
            "version": 2,
            "masquerade": {"type": "proxy", "url": "https://vk.com/", "rewriteHost": True},
        }
        assert ss["finalmask"] == {"quicParams": {"congestion": "bbr"}}
        assert frag["sniffing"]["routeOnly"] is True

    def test_exit_trunk_listener_tuning(self):
        ctx = HYSTERIA_SPEC.build_context(_exit_env([Node(id="hubN1", hostname="h1.test.ns")]))
        assert ctx is not None and ctx.trunk
        frag = HYSTERIA_SPEC.fragment(ctx, make_shared(ipv6=True, route_only=False))
        assert frag["streamSettings"]["finalmask"]["quicParams"] == {
            "congestion": "bbr",
            "maxIncomingStreams": 16384,
            "maxStreamReceiveWindow": 16 * 1024 * 1024,
            "maxConnectionReceiveWindow": 64 * 1024 * 1024,
        }

    def test_ipv4_only_listen_brutal_and_salamander(self):
        hy = HysteriaConfig(obfs=True, congestion=HysteriaCongestion.BRUTAL, up="100 mbps", down="200 mbps")
        ctx = HYSTERIA_SPEC.build_context(_hub_env(users=[make_user(access=["hysteria"])], hysteria=hy))
        assert ctx is not None
        frag = HYSTERIA_SPEC.fragment(ctx, make_shared(ipv6=False))
        assert frag["listen"] == "0.0.0.0"  # noqa: S104
        assert frag["streamSettings"]["finalmask"] == {
            "quicParams": {"congestion": "brutal", "brutalUp": "100 mbps", "brutalDown": "200 mbps"},
            "udp": [{"type": "salamander", "settings": {"password": derive_hysteria_obfs_password(_PRIV, "t.ns")}}],
        }


class TestBuildHysteriaShareUrl:
    def test_pinned_self_signed_with_obfs(self):
        url = build_hysteria_share_url(
            identity_uuid=UUID(int=1),
            hostname="hub.example.com",
            port=443,
            sni="vk.com",
            pin="AA:BB",
            obfs_password="p/w",  # noqa: S106
            fragment="msk alice",
        )
        assert url == (
            "hysteria2://00000000-0000-0000-0000-000000000001@hub.example.com:443/"
            "?sni=vk.com&insecure=1&pinSHA256=AA:BB&obfs=salamander&obfs-password=p%2Fw#msk%20alice"
        )

    def test_operator_certificate_verifies_normally(self):
        url = build_hysteria_share_url(
            identity_uuid=UUID(int=1),
            hostname="h",
            port=8443,
            sni="hub.example.com",
            pin=None,
            obfs_password=None,
            fragment="f",
        )
        assert url == "hysteria2://00000000-0000-0000-0000-000000000001@h:8443/?sni=hub.example.com&insecure=0#f"


class TestBuildHubContextExitProtocol:
    def _config(self, protocol: str | None, hysteria: dict | None = None) -> ConglomerateConfig:
        exit_region: dict = {
            "id": "exit1",
            "type": "exit",
            "vless_route": 1000,
            "warp": {"vless_route": 1001},
            "nodes": [{"id": "exitN1", "hostname": "e.t.ns", "reality": {"dest": "a.com:443", "xhttp_path": "/x/"}}],
        }
        if protocol is not None:
            exit_region["protocol"] = protocol
            exit_region["hysteria"] = hysteria or {"congestion": "brutal", "up": "200 mbps", "down": "500 mbps"}
        return ConglomerateConfig.model_validate(
            {
                "global": {"namespace": "t.ns", "aphelion_domain": "ap.t.ns"},
                "defaults": {
                    "exit": {"ipv6": True, "keys": {"auth": "mlkem768", "mode": "native", "session_time": "600s"}},
                    "hub": {
                        "ipv6": True,
                        "keys": {"auth": "x25519", "mode": "native", "session_time": "600s"},
                        "exit_connections": {"method": "mlkem768x25519plus", "fingerprint": "chrome"},
                        "reality": {"dest": "vk.com:443", "xhttp_path": "/hub/"},
                    },
                },
                "groups": [{"id": "g"}],
                "users": [{"username": "alice", "group": "g", "access": ["xhttp"]}],
                "routing": {"hub_default": "exit1"},
                "regions": [
                    exit_region,
                    {"id": "hub1", "type": "hub", "nodes": [{"id": "hubN1", "hostname": "h.t.ns"}]},
                ],
            }
        )

    def test_hysteria_region_yields_pinned_mirrored_outbounds_with_warp_variant(self):
        from hexrift.inbounds.context import build_hub_context
        from hexrift.links.hysteria import HysteriaLinkContext

        cfg = self._config("hysteria")
        hub_region, hub_node = cfg.regions[1], cfg.regions[1].nodes[0]
        ctx = build_hub_context(cfg, hub_region, hub_node, _KEYS, {"exitN1": _KEYS})
        (ob,), (warp,) = ctx.outbounds, ctx.warp_outbounds
        assert isinstance(ob, HysteriaLinkContext) and isinstance(warp, HysteriaLinkContext)
        ns = Namespace("t.ns")
        uid = ns.hub_exit_uuid("hubN1", "exitN1")
        assert (ob.auth, warp.auth) == (str(uid), str(ns.warp_uuid(uid)))
        assert (ob.tag_prefix, warp.tag_prefix) == ("", "warp-")
        assert (ob.brutal_up, ob.brutal_down) == ("500 mbps", "200 mbps")
        assert ob.pin == derive_hysteria_certificate(_PRIV, "a.com", "t.ns").pin
        assert ob.address == "exitN1.ap.t.ns"
        quic = render_link(ob, ipv6=True)["streamSettings"]["finalmask"]["quicParams"]
        assert quic == {
            "congestion": "brutal",
            "brutalUp": "500 mbps",
            "brutalDown": "200 mbps",
            "keepAlivePeriod": 10,
            "maxStreamReceiveWindow": 16 * 1024 * 1024,
            "maxConnectionReceiveWindow": 64 * 1024 * 1024,
        }

    def test_operator_certificate_pin_is_pinned_by_hubs(self):
        from hexrift.inbounds.context import build_hub_context

        cert = {"cert_file": "/c.pem", "key_file": "/k.pem", "pin_sha256": "ab" * 32}
        cfg = self._config("hysteria", hysteria={"sni": "exit.example.com", "certificate": cert})
        ctx = build_hub_context(cfg, cfg.regions[1], cfg.regions[1].nodes[0], _KEYS, {"exitN1": _KEYS})
        (ob,) = ctx.outbounds
        tls = render_link(ob, ipv6=True)["streamSettings"]["tlsSettings"]
        assert (tls["serverName"], tls["pinnedPeerCertSha256"]) == ("exit.example.com", ":".join(["AB"] * 32))

    def test_vless_region_keeps_vless_outbounds(self):
        from hexrift.inbounds.context import build_hub_context
        from hexrift.links.vless import VlessLinkContext

        cfg = self._config(None)
        ctx = build_hub_context(cfg, cfg.regions[1], cfg.regions[1].nodes[0], _KEYS, {"exitN1": _KEYS})
        assert all(isinstance(ob, VlessLinkContext) for ob in ctx.outbounds + ctx.warp_outbounds)
