from hexrift.components.derive.identity import Namespace
from hexrift.inbounds.cdn import get_hub_cdn_clients
from tests.unit.inbounds.helpers import make_user


class TestGetHubCdnClients:
    def test_cdn_user_included(self):
        ns = Namespace("t.ns")
        u = make_user("alice", access=["xhttp", "cdn"])
        clients = get_hub_cdn_clients([u], ns)
        emails = [c["email"] for c in clients]
        assert "alice@t.ns" in emails

    def test_non_cdn_user_excluded(self):
        ns = Namespace("t.ns")
        u = make_user("bob", access=["xhttp"])
        clients = get_hub_cdn_clients([u], ns)
        emails = [c["email"] for c in clients]
        assert "bob@t.ns" not in emails

    def test_cdn_user_guests_included(self):
        ns = Namespace("t.ns")
        u = make_user("alice", access=["xhttp", "cdn"], guests=["laptop"])
        clients = get_hub_cdn_clients([u], ns)
        emails = [c["email"] for c in clients]
        assert "laptop@alice" in emails

    def test_cdn_server_included(self):
        ns = Namespace("t.ns")
        u = make_user("alice", access=["xhttp", "cdn", "server"])
        clients = get_hub_cdn_clients([u], ns)
        emails = [c["email"] for c in clients]
        assert "alice-server@alice" in emails
