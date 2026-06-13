from hexrift.components.derive.identity import Namespace
from hexrift.components.schema.models.users import Portal, PortalRoutes
from hexrift.inbounds.xhttp import get_hub_user_short_ids, get_hub_vless_clients
from tests.unit.inbounds.helpers import make_user


class TestGetHubVlessClients:
    def test_portal_client_has_reverse_field(self):
        ns = Namespace("t.ns")
        u = make_user("alice", access=["xhttp"], portals=[Portal(label="home", routes=PortalRoutes())])
        clients = get_hub_vless_clients([u], ns)
        portal_client = next((c for c in clients if c["email"] == "home-portal@alice"), None)
        assert portal_client is not None
        assert portal_client.get("reverse") == {"tag": "home-portal"}

    def test_portal_client_present_per_portal(self):
        ns = Namespace("t.ns")
        u = make_user(
            "alice",
            access=["xhttp"],
            portals=[
                Portal(label="home", routes=PortalRoutes()),
                Portal(label="k2", routes=PortalRoutes()),
            ],
        )
        clients = get_hub_vless_clients([u], ns)
        emails = [c["email"] for c in clients]
        assert "home-portal@alice" in emails
        assert "k2-portal@alice" in emails

    def test_portal_client_reverse_tag_matches_label(self):
        ns = Namespace("t.ns")
        u = make_user("alice", access=["xhttp"], portals=[Portal(label="k2", routes=PortalRoutes())])
        clients = get_hub_vless_clients([u], ns)
        k2_client = next(c for c in clients if c["email"] == "k2-portal@alice")
        assert k2_client["reverse"] == {"tag": "k2-portal"}

    def test_non_portal_clients_have_no_reverse_field(self):
        ns = Namespace("t.ns")
        u = make_user("alice", access=["xhttp", "server"])
        clients = get_hub_vless_clients([u], ns)
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
