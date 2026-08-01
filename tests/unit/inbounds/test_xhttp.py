from hexrift.components.derive.identity import Namespace
from hexrift.inbounds.xhttp import get_hub_user_short_ids, get_hub_vless_clients
from tests.unit.inbounds.helpers import make_portal, make_user


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
