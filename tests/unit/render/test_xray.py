from hexrift.components.render.xray import build_exit_config, build_hub_config
from hexrift.components.schema.models.regions import WireguardConfig, XdnsConfig
from tests.unit.render.helpers import exit_ctx as _exit_ctx
from tests.unit.render.helpers import hub_ctx as _hub_ctx


class TestDnsPropagation:
    def test_exit_dns_default(self):
        config = build_exit_config(_exit_ctx())
        assert config["dns"]["servers"] == [{"address": "127.0.0.1", "port": 53}]

    def test_exit_dns_custom(self):
        config = build_exit_config(_exit_ctx(dns_address="169.254.0.53", dns_port=5353))
        assert config["dns"]["servers"] == [{"address": "169.254.0.53", "port": 5353}]

    def test_hub_dns_default(self):
        config = build_hub_config(_hub_ctx())
        assert config["dns"]["servers"] == [{"address": "127.0.0.1", "port": 53}]

    def test_hub_dns_custom(self):
        config = build_hub_config(_hub_ctx(dns_address="169.254.0.53", dns_port=5353))
        assert config["dns"]["servers"] == [{"address": "169.254.0.53", "port": 5353}]

    def test_exit_dns_extra_options_always_present(self):
        config = build_exit_config(_exit_ctx())
        assert config["dns"]["enableParallelQuery"] is True
        assert config["dns"]["useSystemHosts"] is True

    def test_hub_dns_extra_options_always_present(self):
        config = build_hub_config(_hub_ctx())
        assert config["dns"]["enableParallelQuery"] is True
        assert config["dns"]["useSystemHosts"] is True


class TestXdnsWireguardInbounds:
    def test_xdns_inbound_absent_when_no_clients(self):
        config = build_hub_config(_hub_ctx(xdns=XdnsConfig(domains=["dns.google"]), xdns_clients=[]))
        tags = [ib["tag"] for ib in config["inbounds"]]
        assert "xdns" not in tags

    def test_xdns_inbound_present_when_clients_exist(self):
        client = {"id": "aaaaaaaa-0000-0000-0000-000000000000", "email": "u@ns", "flow": "xtls-rprx-vision"}
        config = build_hub_config(_hub_ctx(xdns=XdnsConfig(domains=["dns.google"]), xdns_clients=[client]))
        tags = [ib["tag"] for ib in config["inbounds"]]
        assert "xdns" in tags

    def test_wireguard_inbound_absent_when_no_peers(self):
        config = build_hub_config(_hub_ctx(wireguard=WireguardConfig(subnet="10.0.0.0/24"), wireguard_peers=[]))
        tags = [ib["tag"] for ib in config["inbounds"]]
        assert "wireguard-in" not in tags

    def test_wireguard_inbound_present_when_peers_exist(self):
        # x25519_urlsafe_to_std requires a valid 32-byte URL-safe base64 key
        valid_key = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
        peer = {"email": "u@ns", "publicKey": "FAKE_PUB", "allowedIPs": ["10.0.0.2/32"], "keepAlive": 0}
        config = build_hub_config(
            _hub_ctx(
                reality_private_key=valid_key,
                wireguard=WireguardConfig(subnet="10.0.0.0/24"),
                wireguard_peers=[peer],
            )
        )
        tags = [ib["tag"] for ib in config["inbounds"]]
        assert "wireguard-in" in tags
