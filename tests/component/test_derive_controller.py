from pathlib import Path

import pytest
import yaml

from hexrift.app import HexRiftApp
from hexrift.components.derive.identity import Namespace
from hexrift.errors import DeriveError
from tests.component.conftest import make_topology


FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
FIXTURE_TOPOLOGY = FIXTURES_DIR / "topology.yaml"
FIXTURE_KEYS_DIR = FIXTURES_DIR / "keys"
NS = "test.ns"


@pytest.fixture()
def app() -> HexRiftApp:
    return HexRiftApp(yaml_path=FIXTURE_TOPOLOGY)


class TestDeriveUsers:
    def test_returns_all_users(self, app: HexRiftApp):
        rows = app.derive.derive_users()
        usernames = [r.username for r in rows]
        assert "alice" in usernames
        assert "bob" in usernames

    def test_basic_fields_present(self, app: HexRiftApp):
        rows = app.derive.derive_users()
        alice = next(r for r in rows if r.username == "alice")
        assert alice.uuid
        assert alice.email == "alice@test.hexrift"

    def test_server_access_adds_server_fields(self, app: HexRiftApp):
        rows = app.derive.derive_users()
        alice = next(r for r in rows if r.username == "alice")
        # alice has "server" in access
        assert alice.server_uuid is not None
        assert alice.server_email == "alice-server@alice"

    def test_no_server_access_omits_server_fields(self, app: HexRiftApp):
        rows = app.derive.derive_users()
        bob = next(r for r in rows if r.username == "bob")
        assert bob.server_uuid is None
        assert bob.server_email is None

    def test_guests_included(self, app: HexRiftApp):
        rows = app.derive.derive_users()
        bob = next(r for r in rows if r.username == "bob")
        assert bob.guests
        guest_labels = [g.label for g in bob.guests]
        assert "laptop" in guest_labels
        assert "phone" in guest_labels

    def test_guest_has_required_fields(self, app: HexRiftApp):
        rows = app.derive.derive_users()
        bob = next(r for r in rows if r.username == "bob")
        laptop = next(g for g in bob.guests if g.label == "laptop")
        assert laptop.uuid
        assert laptop.short_id
        assert laptop.email == "laptop@bob"

    def test_uuid_is_deterministic(self, app: HexRiftApp):
        rows1 = app.derive.derive_users()
        rows2 = app.derive.derive_users()
        assert rows1[0].uuid == rows2[0].uuid

    def test_no_guests_key_when_no_guests(self, app: HexRiftApp):
        rows = app.derive.derive_users()
        alice = next(r for r in rows if r.username == "alice")
        assert alice.guests == []


class TestDerivePortals:
    def test_portals_included(self, app: HexRiftApp):
        rows = app.derive.derive_portals()
        assert "home" in [p.id for p in rows]

    def test_portal_has_required_fields(self, app: HexRiftApp):
        portal = next(p for p in app.derive.derive_portals() if p.id == "home")
        assert portal.tag == "home-portal"
        assert portal.uuid
        assert portal.email == "home@portal.test.hexrift"
        assert portal.users == ["alice"]

    def test_portal_has_its_own_short_id(self, app: HexRiftApp):
        portal = next(p for p in app.derive.derive_portals() if p.id == "home")
        assert portal.short_id == Namespace("test.hexrift").portal_short_id("home")

    def test_portal_uuid_is_namespace_scoped(self, app: HexRiftApp):
        ns = Namespace("test.hexrift")
        portal = next(p for p in app.derive.derive_portals() if p.id == "home")
        assert portal.uuid == str(ns.portal_uuid("home"))


class TestDeriveGroups:
    def test_returns_all_groups(self, app: HexRiftApp):
        rows = app.derive.derive_groups()
        ids = [r.id for r in rows]
        assert "main" in ids
        assert "guest" in ids

    def test_has_short_id(self, app: HexRiftApp):
        rows = app.derive.derive_groups()
        for row in rows:
            assert len(row.short_id) > 0

    def test_explicit_short_id_returned_as_is(self, app: HexRiftApp):
        rows = app.derive.derive_groups()
        main = next(r for r in rows if r.id == "main")
        # topology.yaml has short_id: "aabbccddeeff0011" for main group
        assert main.short_id == "aabbccddeeff0011"

    def test_explicit_guest_short_id(self, app: HexRiftApp):
        rows = app.derive.derive_groups()
        guest = next(r for r in rows if r.id == "guest")
        assert guest.short_id == "1122334455667788"


class TestDeriveNodes:
    def test_returns_all_nodes(self, app: HexRiftApp):
        rows = app.derive.derive_nodes()
        ids = [r.id for r in rows]
        assert "nlA00" in ids
        assert "mskA00" in ids

    def test_exit_node_has_short_id(self, app: HexRiftApp):
        rows = app.derive.derive_nodes()
        nl = next(r for r in rows if r.id == "nlA00")
        assert nl.short_id is not None
        assert len(nl.short_id) == 16

    def test_exit_node_has_hub_exit_uuids(self, app: HexRiftApp):
        rows = app.derive.derive_nodes()
        nl = next(r for r in rows if r.id == "nlA00")
        assert nl.hub_exit_uuids is not None
        assert "mskA00" in nl.hub_exit_uuids

    def test_hub_exit_uuid_is_deterministic(self, app: HexRiftApp):
        rows = app.derive.derive_nodes()
        nl = next(r for r in rows if r.id == "nlA00")
        ns = Namespace("test.hexrift")
        expected = str(ns.hub_exit_uuid("mskA00", "nlA00"))
        assert nl.hub_exit_uuids is not None
        assert nl.hub_exit_uuids["mskA00"] == expected

    def test_hub_node_has_hub_short_id(self, app: HexRiftApp):
        rows = app.derive.derive_nodes()
        msk = next(r for r in rows if r.id == "mskA00")
        assert msk.hub_short_id is not None
        assert len(msk.hub_short_id) == 16

    def test_hub_node_no_exit_fields(self, app: HexRiftApp):
        rows = app.derive.derive_nodes()
        msk = next(r for r in rows if r.id == "mskA00")
        assert msk.short_id is None
        assert msk.hub_exit_uuids is None


class TestBuildShareUrls:
    def test_reality_url_starts_with_vless(self, app: HexRiftApp):
        pairs = app.derive.build_share_urls("alice", None, FIXTURE_KEYS_DIR, "chrome")
        assert len(pairs) >= 1
        _, url = pairs[0]
        assert url.startswith("vless://")

    def test_reality_url_contains_security_reality(self, app: HexRiftApp):
        pairs = app.derive.build_share_urls("alice", None, FIXTURE_KEYS_DIR, "chrome")
        _, url = pairs[0]
        assert "security=reality" in url

    def test_reality_url_contains_public_key(self, app: HexRiftApp):
        pairs = app.derive.build_share_urls("alice", None, FIXTURE_KEYS_DIR, "chrome")
        _, url = pairs[0]
        # mskA00 reality public key
        assert "pbk=mZ0iHOiFoN3JfGgq_7D7GwvEcMwqJEbT7T5VyqK7Rnk" in url

    def test_reality_url_type_xhttp(self, app: HexRiftApp):
        pairs = app.derive.build_share_urls("alice", None, FIXTURE_KEYS_DIR, "chrome")
        _, url = pairs[0]
        assert "type=xhttp" in url

    def test_cdn_url_contains_security_tls(self, app: HexRiftApp):
        pairs = app.derive.build_share_urls("alice", None, FIXTURE_KEYS_DIR, "chrome", cdn=True)
        assert len(pairs) >= 1
        _, url = pairs[0]
        assert "security=tls" in url

    def test_cdn_url_uses_cdn_hub_domain(self, app: HexRiftApp):
        pairs = app.derive.build_share_urls("alice", None, FIXTURE_KEYS_DIR, "chrome", cdn=True)
        _, url = pairs[0]
        assert "cdn-hub.test.hexrift" in url

    def test_unknown_user_raises(self, app: HexRiftApp):
        with pytest.raises(DeriveError, match="User not found"):
            app.derive.build_share_urls("nobody", None, FIXTURE_KEYS_DIR, "chrome")

    def test_cdn_without_cdn_access_raises(self, app: HexRiftApp):
        # bob has xhttp but not cdn access — a CDN URL must be gated on CDN access,
        # mirroring the hub cdn-xhttp inbound which only admits CDN users.
        with pytest.raises(DeriveError, match="does not have CDN access"):
            app.derive.build_share_urls("bob", None, FIXTURE_KEYS_DIR, "chrome", cdn=True)

    def test_no_xhttp_access_raises(self, app: HexRiftApp, tmp_path: Path):
        # alice has no xhttp access; drop the default portal, whose members must be routable
        topo = make_topology(
            users=[
                {
                    "username": "alice",
                    "group": "grp1",
                    "access": ["proxy"],
                },
            ],
            portals=[],
        )
        p = tmp_path / "topology.yaml"
        p.write_text(yaml.dump(topo))
        restricted_app = HexRiftApp(yaml_path=p)
        with pytest.raises(DeriveError, match="does not have XHTTP access"):
            restricted_app.derive.build_share_urls("alice", None, tmp_path, "chrome")

    def test_cdn_not_configured_raises(self, app: HexRiftApp, tmp_path: Path):
        # alice has cdn access but the topology has no global.cdn (the minimal default)
        topo = make_topology(
            users=[
                {
                    "username": "alice",
                    "group": "grp1",
                    "access": ["xhttp", "cdn"],
                },
            ],
        )
        p = tmp_path / "topology.yaml"
        p.write_text(yaml.dump(topo))
        no_cdn_app = HexRiftApp(yaml_path=p)
        with pytest.raises(DeriveError, match="CDN is not configured"):
            no_cdn_app.derive.build_share_urls("alice", None, tmp_path, "chrome", cdn=True)

    def test_guest_identity_in_url(self, app: HexRiftApp):
        pairs = app.derive.build_share_urls("bob", None, FIXTURE_KEYS_DIR, "chrome", guest="laptop")
        assert len(pairs) >= 1
        _, url = pairs[0]
        ns = Namespace("test.hexrift")
        bob_base = ns.user_uuid("bob")
        expected_uuid = str(ns.guest_uuid("laptop", "bob", user_base=bob_base))
        assert expected_uuid in url

    def test_server_direct_url(self, app: HexRiftApp):
        pairs = app.derive.build_share_urls("alice", "mskA00", FIXTURE_KEYS_DIR, "chrome", server=True)
        assert len(pairs) == 1
        label, url = pairs[0]
        assert "alice-server@alice" in label
        assert "security=reality" in url
        ns = Namespace("test.hexrift")
        expected_uuid = str(ns.server_uuid("alice", user_base=ns.user_uuid("alice")))
        assert url.startswith(f"vless://{expected_uuid}@")

    def test_server_cdn_url(self, app: HexRiftApp):
        pairs = app.derive.build_share_urls("alice", "mskA00", FIXTURE_KEYS_DIR, "chrome", cdn=True, server=True)
        assert len(pairs) == 1
        label, url = pairs[0]
        assert "CDN" in label
        assert "alice-server@alice" in label
        assert "security=tls" in url

    def test_server_without_access_raises(self, app: HexRiftApp):
        with pytest.raises(DeriveError, match="does not have server access"):
            app.derive.build_share_urls("bob", None, FIXTURE_KEYS_DIR, "chrome", server=True)

    def test_server_url_does_not_require_xhttp_access(self, tmp_path: Path):
        # SERVER access alone puts the server identity on the hub xhttp inbound,
        # so a direct server URL must work for a user without XHTTP access.
        topo = make_topology(
            users=[
                {
                    "username": "carol",
                    "group": "grp1",
                    "access": [
                        "server",
                    ],
                },
            ],
            portals=[],
        )
        p = tmp_path / "topology.yaml"
        p.write_text(yaml.dump(topo))
        server_app = HexRiftApp(yaml_path=p)
        server_app.keys.gen_keys("hubN1", tmp_path)
        pairs = server_app.derive.build_share_urls("carol", None, tmp_path, "chrome", server=True)
        assert len(pairs) == 1
        ns = Namespace("test.ns")
        expected_uuid = str(ns.server_uuid("carol", user_base=ns.user_uuid("carol")))
        assert expected_uuid in pairs[0][1]

    def test_server_cdn_url_requires_cdn_access(self, tmp_path: Path):
        # The hub cdn-xhttp inbound skips users without CDN access entirely —
        # including their server identity — so the URL would be dead.
        topo = make_topology(
            users=[
                {
                    "username": "carol",
                    "group": "grp1",
                    "access": [
                        "server",
                    ],
                },
            ],
            portals=[],
        )
        p = tmp_path / "topology.yaml"
        p.write_text(yaml.dump(topo))
        server_app = HexRiftApp(yaml_path=p)
        with pytest.raises(DeriveError, match="does not have CDN access"):
            server_app.derive.build_share_urls("carol", None, tmp_path, "chrome", cdn=True, server=True)

    def test_all_guests_returns_urls_for_each_guest(self, app: HexRiftApp):
        pairs = app.derive.build_share_urls("bob", "mskA00", FIXTURE_KEYS_DIR, "chrome", all_guests=True)
        assert len(pairs) == 2, f"Expected one URL per guest, got: {[label for label, _ in pairs]}"
        ns = Namespace("test.hexrift")
        bob_base = ns.user_uuid("bob")
        urls = [url for _, url in pairs]
        for label in ("laptop", "phone"):
            expected_uuid = str(ns.guest_uuid(label, "bob", user_base=bob_base))
            assert any(expected_uuid in url for url in urls), f"missing URL for guest {label!r}"

    def test_all_guests_conflicts_with_guest(self, app: HexRiftApp):
        with pytest.raises(DeriveError, match="cannot be combined"):
            app.derive.build_share_urls("bob", None, FIXTURE_KEYS_DIR, "chrome", all_guests=True, guest="laptop")

    def test_all_guests_conflicts_with_server(self, app: HexRiftApp):
        with pytest.raises(DeriveError, match="cannot be combined"):
            app.derive.build_share_urls("alice", None, FIXTURE_KEYS_DIR, "chrome", all_guests=True, server=True)

    def test_all_guests_without_guests_raises(self, app: HexRiftApp):
        with pytest.raises(DeriveError, match="has no guests"):
            app.derive.build_share_urls("alice", None, FIXTURE_KEYS_DIR, "chrome", all_guests=True)

    def test_specific_hub_node(self, app: HexRiftApp):
        pairs_all = app.derive.build_share_urls("alice", None, FIXTURE_KEYS_DIR, "chrome")
        pairs_specific = app.derive.build_share_urls("alice", "mskA00", FIXTURE_KEYS_DIR, "chrome")
        # Specific hub should return exactly one URL
        assert len(pairs_specific) == 1
        # Both should contain the same hub node URL
        assert pairs_specific[0][1] in [u for _, u in pairs_all]

    def test_dedup_region_default_reality(self, app: HexRiftApp, tmp_path: Path):
        """Two hub nodes in same region with no node-specific reality → one URL per region."""

        topo = make_topology(
            regions=[
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
                    # Two nodes, neither with node-specific reality → share region default
                    "nodes": [
                        {"id": "hN1", "hostname": "h1.t.ns"},
                        {"id": "hN2", "hostname": "h2.t.ns"},
                    ],
                },
            ],
        )
        p = tmp_path / "topology.yaml"
        p.write_text(yaml.dump(topo))
        # Generate keys for both hub nodes
        multi_app = HexRiftApp(yaml_path=p)
        multi_app.keys.gen_keys("hN1", tmp_path)
        multi_app.keys.gen_keys("hN2", tmp_path)
        pairs = multi_app.derive.build_share_urls("alice", None, tmp_path, "chrome")
        # Only one URL per region for region-default reality
        assert len(pairs) == 1


class TestBuildWireguardConfigs:
    def test_conf_has_interface_and_peer(self, app: HexRiftApp):
        pairs = app.derive.build_wireguard_configs("alice", None, FIXTURE_KEYS_DIR)
        assert len(pairs) >= 1
        _, conf = pairs[0]
        assert conf.startswith("[Interface]")
        assert "[Peer]" in conf
        assert "PrivateKey = " in conf
        assert "PublicKey = " in conf
        assert "MTU = 1420" in conf

    def test_conf_address_matches_peer_allocation(self, app: HexRiftApp):
        # alice is the first wireguard user → .2 (server holds .1)
        _, conf = app.derive.build_wireguard_configs("alice", "mskA00", FIXTURE_KEYS_DIR)[0]
        assert "Address = 10.0.0.2/32" in conf

    def test_conf_endpoint_and_full_tunnel(self, app: HexRiftApp):
        _, conf = app.derive.build_wireguard_configs("alice", "mskA00", FIXTURE_KEYS_DIR)[0]
        assert "Endpoint = mskA00.ap.test.hexrift:443" in conf
        assert "AllowedIPs = 0.0.0.0/0" in conf
        assert "DNS = 1.1.1.1" in conf

    def test_conf_server_public_key(self, app: HexRiftApp):
        from hexrift.shared.crypto import x25519_urlsafe_to_std

        _, conf = app.derive.build_wireguard_configs("alice", "mskA00", FIXTURE_KEYS_DIR)[0]
        expected = x25519_urlsafe_to_std("mZ0iHOiFoN3JfGgq_7D7GwvEcMwqJEbT7T5VyqK7Rnk")
        assert f"PublicKey = {expected}" in conf

    def test_specific_hub_node(self, app: HexRiftApp):
        pairs = app.derive.build_wireguard_configs("alice", "mskA00", FIXTURE_KEYS_DIR)
        assert len(pairs) == 1
        assert pairs[0][0] == "mskA00  WireGuard  alice"

    def test_no_keepalive_line_when_zero(self, app: HexRiftApp):
        _, conf = app.derive.build_wireguard_configs("alice", "mskA00", FIXTURE_KEYS_DIR)[0]
        assert "PersistentKeepalive" not in conf

    def test_renderer_emits_keepalive_when_positive(self):
        from hexrift.components.derive.wireguard import render_wireguard_client_conf

        conf = render_wireguard_client_conf(
            private_key="priv",
            address="10.0.0.2/32",
            dns=["1.1.1.1"],
            mtu=1420,
            server_public_key="pub",
            endpoint="host:443",
            allowed_ips=["0.0.0.0/0"],
            keepalive=25,
        )
        assert "PersistentKeepalive = 25" in conf

    def test_conf_is_ipv4_only(self, app: HexRiftApp):
        # Hub defaults set ipv6: true, but WireGuard has no IPv6 subnet to allocate from,
        # so the client config must stay IPv4-only (no ::/0, no IPv6 DNS).
        _, conf = app.derive.build_wireguard_configs("alice", "mskA00", FIXTURE_KEYS_DIR)[0]
        assert "::/0" not in conf
        assert "AllowedIPs = 0.0.0.0/0\n" in conf
        assert "DNS = 1.1.1.1\n" in conf

    def test_guest_config_address_and_label(self, app: HexRiftApp):
        # Canonical order: alice .2, alice-server .3, bob .4, laptop@bob .5, phone@bob .6
        _, conf = app.derive.build_wireguard_configs("bob", "mskA00", FIXTURE_KEYS_DIR, guest="laptop")[0]
        assert "Address = 10.0.0.5/32" in conf
        pairs = app.derive.build_wireguard_configs("bob", "mskA00", FIXTURE_KEYS_DIR, guest="phone")
        assert pairs[0][0] == "mskA00  WireGuard  phone@bob"
        assert "Address = 10.0.0.6/32" in pairs[0][1]

    def test_guest_address_matches_inbound_peer(self, app: HexRiftApp):
        # The client guest address must equal the inbound peer allocation by construction.
        from hexrift.components.derive.identity import Namespace
        from hexrift.components.derive.wireguard import iter_hub_wireguard_allocs

        cfg = app.schema.config
        ns = Namespace(cfg.global_.namespace)
        allocs = {a.email: a for a in iter_hub_wireguard_allocs(cfg.users, ns, "10.0.0.0/24")}
        _, conf = app.derive.build_wireguard_configs("bob", "mskA00", FIXTURE_KEYS_DIR, guest="laptop")[0]
        assert f"Address = {allocs['laptop@bob'].address}" in conf

    def test_unknown_guest_raises(self, app: HexRiftApp):
        with pytest.raises(DeriveError, match="Guest 'nobody' not found"):
            app.derive.build_wireguard_configs("bob", None, FIXTURE_KEYS_DIR, guest="nobody")

    def test_server_config_address_and_label(self, app: HexRiftApp):
        # alice has server access → server identity is the second peer (.3)
        pairs = app.derive.build_wireguard_configs("alice", "mskA00", FIXTURE_KEYS_DIR, server=True)
        assert pairs[0][0] == "mskA00  WireGuard  alice-server@alice"
        assert "Address = 10.0.0.3/32" in pairs[0][1]

    def test_server_without_access_raises(self, app: HexRiftApp):
        # bob has wireguard but not server access
        with pytest.raises(DeriveError, match="does not have server access"):
            app.derive.build_wireguard_configs("bob", None, FIXTURE_KEYS_DIR, server=True)

    def test_unknown_user_raises(self, app: HexRiftApp):
        with pytest.raises(DeriveError, match="User not found"):
            app.derive.build_wireguard_configs("nobody", None, FIXTURE_KEYS_DIR)

    def test_no_wireguard_access_raises(self, app: HexRiftApp, tmp_path: Path):
        # WireGuard is enabled on the hub, but alice (minimal default) has only xhttp access.
        topo = make_topology(
            defaults={
                "hub": {
                    "wireguard": {"subnet": "10.0.0.0/24"},
                },
            },
        )
        p = tmp_path / "topology.yaml"
        p.write_text(yaml.dump(topo))
        restricted_app = HexRiftApp(yaml_path=p)
        with pytest.raises(DeriveError, match="does not have WireGuard access"):
            restricted_app.derive.build_wireguard_configs("alice", None, tmp_path)


def _collision_app(tmp_path: Path, **overrides) -> HexRiftApp:
    p = tmp_path / "topology.yaml"
    p.write_text(yaml.dump(make_topology(**overrides)))
    return HexRiftApp(yaml_path=p)


def _portal(portal_id: str = "home", uuid: str | None = None) -> dict:
    portal: dict = {"id": portal_id, "users": ["alice"], "routes": {"domains": [f"{portal_id}.example.com"]}}
    if uuid is not None:
        portal["uuid"] = uuid
    return portal


class TestIdentityCollisions:
    def test_portal_override_shadows_derived_user(self, tmp_path: Path):
        derived = str(Namespace(NS).user_uuid("alice"))
        app = _collision_app(tmp_path, portals=[_portal(uuid=derived)])
        with pytest.raises(DeriveError, match="claimed by both user 'alice' and portal 'home'"):
            app.schema.load(app.yaml_path)

    def test_portal_override_shadows_derived_guest(self, tmp_path: Path):
        derived = str(Namespace(NS).guest_uuid("laptop", "alice"))
        app = _collision_app(
            tmp_path,
            users=[{"username": "alice", "group": "grp1", "access": ["xhttp"], "guests": ["laptop"]}],
            portals=[_portal(uuid=derived)],
        )
        with pytest.raises(DeriveError, match="claimed by both guest 'laptop' of user 'alice'"):
            app.schema.load(app.yaml_path)

    def test_user_override_shadows_another_derived_user(self, tmp_path: Path):
        derived = str(Namespace(NS).user_uuid("alice"))
        app = _collision_app(
            tmp_path,
            users=[
                {"username": "alice", "group": "grp1", "access": ["xhttp"]},
                {"username": "bob", "group": "grp1", "access": ["xhttp"], "uuid": derived},
            ],
        )
        with pytest.raises(DeriveError, match="claimed by both user 'alice' and user 'bob'"):
            app.schema.load(app.yaml_path)

    def test_two_portals_share_an_override(self, tmp_path: Path):
        shared = "11111111-2222-3333-4444-555555555555"
        app = _collision_app(tmp_path, portals=[_portal(uuid=shared), _portal("office", uuid=shared)])
        with pytest.raises(DeriveError, match="claimed by both portal 'home' and portal 'office'"):
            app.schema.load(app.yaml_path)

    def test_share_surfaces_collision(self, tmp_path: Path):
        derived = str(Namespace(NS).user_uuid("alice"))
        app = _collision_app(tmp_path, portals=[_portal(uuid=derived)])
        with pytest.raises(DeriveError, match="claimed by both"):
            app.derive.derive_users()

    def test_build_surfaces_collision(self, tmp_path: Path):
        derived = str(Namespace(NS).user_uuid("alice"))
        app = _collision_app(tmp_path, portals=[_portal(uuid=derived)])
        with pytest.raises(DeriveError, match="claimed by both"):
            app.render.build("hubN1", tmp_path / "out", tmp_path / "keys", xray=True, haproxy=False)

    def test_gen_portal_surfaces_collision(self, tmp_path: Path):
        derived = str(Namespace(NS).user_uuid("alice"))
        app = _collision_app(tmp_path, portals=[_portal(uuid=derived)])
        with pytest.raises(DeriveError, match="claimed by both"):
            app.render.gen_portal("home", tmp_path / "out", tmp_path / "keys", "chrome")
