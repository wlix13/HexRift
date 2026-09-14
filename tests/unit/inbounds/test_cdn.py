from types import SimpleNamespace
from typing import cast
from uuid import UUID

from hexrift.components.derive.identity import Namespace
from hexrift.components.keys.store import NodeKeys
from hexrift.components.schema.models.root import ConglomerateConfig
from hexrift.inbounds.base import InboundEnv, ShareClient
from hexrift.inbounds.cdn import CDN_SPEC, CdnContext, get_hub_cdn_clients
from hexrift.shared.xhttp import XHTTP_EXTRA_CDN
from tests.unit.inbounds.helpers import make_hub_region, make_user, split_xhttp_share_url


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


class TestCdnShareUrl:
    def test_url(self):
        ctx = CdnContext(
            xhttp_host="cdn.example.com", xhttp_path="/c/", cert_alias="cdn", domain="cdn.example.com", clients=[]
        )
        region = make_hub_region()
        keys = NodeKeys(reality_private_key="p", reality_public_key="p", decryption="none", encryption="none")
        env = InboundEnv(cast(ConglomerateConfig, SimpleNamespace()), region, region.nodes[0], keys)
        url = CDN_SPEC.share_url(ctx, env, ShareClient(UUID(int=1), "0123456789abcdef", "chrome", "hub1(CDN)-alice"))
        assert split_xhttp_share_url(url) == (
            "vless://00000000-0000-0000-0000-000000000001@cdn.example.com:443"
            "?encryption=none&flow=&security=tls&sni=cdn.example.com&fp=chrome&sid=0123456789abcdef&spx=%2F"
            "&alpn=h3%2Ch2%2Chttp%2F1.1&insecure=0&allowInsecure=0&type=xhttp&host=cdn.example.com&path=%2Fc%2F&mode=auto",
            {**XHTTP_EXTRA_CDN, "uplinkHTTPMethod": "PATCH"},
            "hub1%28CDN%29-alice",
        )
