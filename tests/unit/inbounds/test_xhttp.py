from types import SimpleNamespace
from typing import cast
from uuid import UUID

from hexrift.components.derive.identity import Namespace
from hexrift.components.keys.store import NodeKeys
from hexrift.components.schema.models.defaults import DefaultsConfig
from hexrift.components.schema.models.regions import CertificateFiles, HubRegion, TlsConfig, TlsOverride
from hexrift.components.schema.models.resolve import resolve_region_tls
from hexrift.components.schema.models.root import ConglomerateConfig
from hexrift.components.schema.models.shared import RealityConfig
from hexrift.inbounds.base import InboundEnv, ShareClient
from hexrift.inbounds.xhttp import XHTTP_SPEC, TlsXhttpContext, get_hub_user_short_ids, get_hub_vless_clients
from hexrift.shared.xhttp import XHTTP_EXTRA, make_xhttp_settings
from hexrift.shared.xray_defaults import make_inbound_sockopt
from tests.unit.inbounds.helpers import make_defaults, make_hub_region, make_portal, make_user, split_xhttp_share_url
from tests.unit.render.helpers import make_shared


class TestGetHubVlessClients:
    def test_portal_client_has_reverse_field(self):
        ns = Namespace("t.ns")
        u = make_user("alice", access=["xhttp"])
        p = make_portal("home", users=["alice"], domains=["home.example.com"])
        clients = get_hub_vless_clients([u], [p], ns)
        portal_client = next((c for c in clients if c["email"] == "home@portal.t.ns"), None)
        assert portal_client is not None
        assert portal_client.get("reverse") == {"tag": "home-portal"}

    def test_one_client_per_portal(self):
        ns = Namespace("t.ns")
        u = make_user("alice", access=["xhttp"])
        portals = [
            make_portal("home", users=["alice"], domains=["home.example.com"]),
            make_portal("k2", users=["alice"], domains=["k2.example.com"]),
        ]
        clients = get_hub_vless_clients([u], portals, ns)
        emails = [c["email"] for c in clients]
        assert "home@portal.t.ns" in emails
        assert "k2@portal.t.ns" in emails

    def test_portal_client_present_without_member_access(self):
        # Portal clients are portal-owned; member users' access types are irrelevant.
        ns = Namespace("t.ns")
        u = make_user("alice", access=["wireguard"])
        p = make_portal("home", users=["alice"], domains=["home.example.com"])
        clients = get_hub_vless_clients([u], [p], ns)
        assert any(c["email"] == "home@portal.t.ns" for c in clients)

    def test_shared_portal_emits_single_client(self):
        ns = Namespace("t.ns")
        users = [make_user("alice"), make_user("bob")]
        p = make_portal("home", users=["alice", "bob"], domains=["home.example.com"])
        clients = get_hub_vless_clients(users, [p], ns)
        portal_clients = [c for c in clients if c["email"] == "home@portal.t.ns"]
        assert len(portal_clients) == 1

    def test_portal_client_reverse_tag_matches_id(self):
        ns = Namespace("t.ns")
        u = make_user("alice", access=["xhttp"])
        p = make_portal("k2", users=["alice"], domains=["k2.example.com"])
        clients = get_hub_vless_clients([u], [p], ns)
        k2_client = next(c for c in clients if c["email"] == "k2@portal.t.ns")
        assert k2_client["reverse"] == {"tag": "k2-portal"}

    def test_portal_client_uuid_is_portal_scoped(self):
        ns = Namespace("t.ns")
        u = make_user("alice", access=["xhttp"])
        p = make_portal("home", users=["alice"], domains=["home.example.com"])
        clients = get_hub_vless_clients([u], [p], ns)
        portal_client = next(c for c in clients if c["email"] == "home@portal.t.ns")
        assert portal_client["id"] == str(ns.portal_uuid("home"))
        assert portal_client["id"] != str(ns.user_uuid("alice"))

    def test_non_portal_clients_have_no_reverse_field(self):
        ns = Namespace("t.ns")
        u = make_user("alice", access=["xhttp", "server"])
        clients = get_hub_vless_clients([u], [], ns)
        assert clients
        for c in clients:
            assert "reverse" not in c


class TestGetHubUserShortIds:
    def test_user_without_guests_skipped(self):
        ns = Namespace("t.ns")
        u = make_user("alice", access=["xhttp"], guests=[])
        result = get_hub_user_short_ids([u], ns)
        assert result == []

    def test_user_with_guests_included(self):
        ns = Namespace("t.ns")
        u = make_user("bob", access=["xhttp"], guests=["laptop", "phone"])
        result = get_hub_user_short_ids([u], ns)
        assert len(result) == 1  # one short_id per user

    def test_dedup_same_user(self):
        ns = Namespace("t.ns")
        u = make_user("bob", access=["xhttp", "cdn"], guests=["laptop"])
        result = get_hub_user_short_ids([u], ns)
        assert len(result) == 1

    def test_no_xhttp_and_no_cdn_skipped(self):
        ns = Namespace("t.ns")
        u = make_user("alice", access=["proxy"], guests=["laptop"])
        result = get_hub_user_short_ids([u], ns)
        assert result == []


_CERT = CertificateFiles(cert_file="/c.pem", key_file="/k.pem")
_KEYS = NodeKeys(reality_private_key="p", reality_public_key="p", decryption="none", encryption="none")


def _hub_env(
    region: HubRegion, defaults: DefaultsConfig, users: list | None = None, portals: list | None = None
) -> InboundEnv:
    cfg = cast(
        ConglomerateConfig,
        SimpleNamespace(
            defaults=defaults,
            users=users if users is not None else [make_user("alice")],
            portals=portals or [],
            groups=[],
            global_=SimpleNamespace(namespace="t.ns"),
        ),
    )
    return InboundEnv(config=cfg, region=region, node=region.nodes[0], node_keys=_KEYS)


class TestResolveRegionTls:
    def test_default_tls_applies_unless_region_picks_reality(self):
        defaults = make_defaults(tls=TlsConfig(certificate=_CERT, xhttp_path="/t/"))
        assert resolve_region_tls(make_hub_region(), defaults) == TlsConfig(certificate=_CERT, xhttp_path="/t/")
        reality = make_hub_region(reality=RealityConfig(dest="a.com:443", xhttp_path="/x/"))
        assert resolve_region_tls(reality, defaults) is None

    def test_region_override_overlays_default(self):
        defaults = make_defaults(tls=TlsConfig(certificate=_CERT, xhttp_path="/t/"))
        region = make_hub_region(tls=TlsOverride(xhttp_path="/n/"))
        assert resolve_region_tls(region, defaults) == TlsConfig(certificate=_CERT, xhttp_path="/n/")

    def test_region_tls_under_reality_default_starts_from_its_certificate(self):
        region = make_hub_region(tls=TlsOverride(certificate=_CERT))
        assert resolve_region_tls(region, make_defaults()) == TlsConfig(certificate=_CERT, xhttp_path="/")


class TestXhttpSpecTls:
    def test_hub_serves_operator_cert_to_tls_users_and_portals(self):
        region = make_hub_region(tls=TlsOverride(certificate=_CERT, xhttp_path="/t/"))
        users = [make_user("alice", access=["tls", "server"], guests=["laptop"]), make_user("bob", access=["xhttp"])]
        portals = [make_portal("home", users=["bob"], domains=["home.example.com"])]
        ctx = XHTTP_SPEC.build_context(_hub_env(region, make_defaults(), users=users, portals=portals))
        assert isinstance(ctx, TlsXhttpContext)
        assert (ctx.xhttp_host, ctx.xhttp_path, ctx.certificate) == ("h.test.ns", "/t/", _CERT)
        assert [c["email"] for c in ctx.clients] == [
            "alice@t.ns",
            "alice-server@alice",
            "laptop@alice",
            "home@portal.t.ns",
        ]
        shared = make_shared(haproxy=False, ipv6=True)
        frag = XHTTP_SPEC.fragment(ctx, shared)
        assert (frag["tag"], frag["listen"], frag["port"]) == ("direct-xhttp", "::", 443)
        assert frag["streamSettings"] == {
            "network": "xhttp",
            "security": "tls",
            "xhttpSettings": make_xhttp_settings("h.test.ns", "/t/"),
            "tlsSettings": {
                "alpn": ["h2", "http/1.1"],
                "certificates": [{"certificateFile": "/c.pem", "keyFile": "/k.pem"}],
            },
            "sockopt": make_inbound_sockopt(True, shared.trusted_forwarded_headers),
        }


class TestXhttpShareUrl:
    _CLIENT = ShareClient(UUID(int=1), "0123456789abcdef", "chrome", "hub1-alice")

    def test_reality(self):
        env = _hub_env(make_hub_region(), make_defaults())
        url = XHTTP_SPEC.share_url(XHTTP_SPEC.build_context(env), env, self._CLIENT)
        assert split_xhttp_share_url(url) == (
            "vless://00000000-0000-0000-0000-000000000001@h.test.ns:443"
            "?encryption=none&flow=&security=reality&sni=vk.com&fp=chrome&pbk=p&sid=0123456789abcdef"
            "&type=xhttp&host=vk.com&path=%2Fhub%2F&mode=auto",
            XHTTP_EXTRA,
            "hub1-alice",
        )

    def test_tls(self):
        env = _hub_env(make_hub_region(tls=TlsOverride(certificate=_CERT, xhttp_path="/t/")), make_defaults())
        url = XHTTP_SPEC.share_url(XHTTP_SPEC.build_context(env), env, self._CLIENT)
        assert split_xhttp_share_url(url) == (
            "vless://00000000-0000-0000-0000-000000000001@h.test.ns:443"
            "?encryption=none&flow=&security=tls&sni=h.test.ns&fp=chrome&alpn=h2%2Chttp%2F1.1"
            "&type=xhttp&host=h.test.ns&path=%2Ft%2F&mode=auto",
            XHTTP_EXTRA,
            "hub1-alice",
        )
