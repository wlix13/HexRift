from hexrift.components.schema.models.regions import Node
from hexrift.inbounds.proxy import PROXY_SPEC, ProxyContext, resolve_node_proxy_inbound
from tests.unit.inbounds.helpers import make_defaults
from tests.unit.render.helpers import make_shared


class TestResolveNodeProxyInbound:
    def test_node_override_wins(self):
        node = Node(id="n", hostname="h.example.com", proxy_inbound=True)
        assert resolve_node_proxy_inbound(node, make_defaults(proxy_inbound=False)) is True

    def test_node_override_disables(self):
        node = Node(id="n", hostname="h.example.com", proxy_inbound=False)
        assert resolve_node_proxy_inbound(node, make_defaults(proxy_inbound=True)) is False

    def test_falls_back_to_hub_default(self):
        node = Node(id="n", hostname="h.example.com")
        assert resolve_node_proxy_inbound(node, make_defaults(proxy_inbound=True)) is True


class TestProxyFragment:
    def test_fragment_emitted_with_empty_accounts(self):
        # mixed-inbound is emitted whenever proxy_inbound is enabled, even without proxy users
        fragment = PROXY_SPEC.fragment(ProxyContext(accounts=[]), make_shared())
        assert fragment["tag"] == "mixed-inbound"
        assert fragment["port"] == 80
        assert fragment["settings"]["accounts"] == []

    def test_fragment_accounts_passthrough(self):
        accounts = [{"user": "alice", "pass": "uuid-here"}]
        fragment = PROXY_SPEC.fragment(ProxyContext(accounts=accounts), make_shared())
        assert fragment["settings"]["accounts"] == accounts
        assert fragment["settings"]["auth"] == "password"
