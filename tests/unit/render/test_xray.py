from hexrift.components.render.xray import build_exit_config, build_hub_config
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
