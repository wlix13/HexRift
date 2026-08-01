from hexrift.components.derive.identity import Namespace
from hexrift.components.schema.models.regions import Node, XdnsConfig
from hexrift.inbounds.xdns import get_hub_xdns_clients, resolve_node_xdns
from tests.unit.inbounds.helpers import make_defaults, make_user


class TestResolveNodeXdns:
    def test_node_override_wins(self):
        node = Node(id="n", hostname="h.example.com", xdns=XdnsConfig(domains=["dns.node"]))
        result = resolve_node_xdns(node, make_defaults(xdns=XdnsConfig(domains=["dns.default"])))
        assert result is not None
        assert result.domains == ["dns.node"]

    def test_falls_back_to_hub_default(self):
        node = Node(id="n", hostname="h.example.com")
        result = resolve_node_xdns(node, make_defaults(xdns=XdnsConfig(domains=["dns.default"])))
        assert result is not None
        assert result.domains == ["dns.default"]

    def test_none_when_unconfigured(self):
        node = Node(id="n", hostname="h.example.com")
        assert resolve_node_xdns(node, make_defaults()) is None


class TestGetHubXdnsClients:
    def test_xdns_user_included(self):
        ns = Namespace("t.ns")
        u = make_user("alice", access=["xhttp", "xdns"])
        clients = get_hub_xdns_clients([u], ns)
        emails = [c["email"] for c in clients]
        assert "alice@t.ns" in emails

    def test_non_xdns_user_excluded(self):
        ns = Namespace("t.ns")
        u = make_user("bob", access=["xhttp"])
        clients = get_hub_xdns_clients([u], ns)
        emails = [c["email"] for c in clients]
        assert "bob@t.ns" not in emails

    def test_xdns_user_guests_included(self):
        ns = Namespace("t.ns")
        u = make_user("alice", access=["xhttp", "xdns"], guests=["laptop"])
        clients = get_hub_xdns_clients([u], ns)
        emails = [c["email"] for c in clients]
        assert "laptop@alice" in emails

    def test_server_variant_excluded(self):
        ns = Namespace("t.ns")
        u = make_user("alice", access=["xhttp", "server", "xdns"])
        clients = get_hub_xdns_clients([u], ns)
        emails = [c["email"] for c in clients]
        assert "alice@t.ns" in emails
        assert "alice-server@alice" not in emails

    def test_clients_have_empty_flow(self):
        # xdns runs over non-TLS mKCP, where xtls-rprx-vision is invalid.
        ns = Namespace("t.ns")
        u = make_user("alice", access=["xhttp", "xdns"], guests=["laptop"])
        clients = get_hub_xdns_clients([u], ns)
        assert clients  # sanity
        assert all(c["flow"] == "" for c in clients)
