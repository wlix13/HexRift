import pytest
import yaml

from hexrift.app import HexRiftApp
from hexrift.components.keys.store import NodeKeys, node_keys_exist
from hexrift.errors import KeysError


class TestGenKeys:
    def test_creates_key_file(self, app: HexRiftApp, tmp_path):
        result = app.keys.gen_keys("exitN1", tmp_path)
        assert result is True
        assert node_keys_exist(tmp_path, "exitN1")

    def test_returns_true_on_creation(self, app: HexRiftApp, tmp_path):
        assert app.keys.gen_keys("exitN1", tmp_path) is True

    def test_returns_false_when_already_exists(self, app: HexRiftApp, tmp_path):
        app.keys.gen_keys("exitN1", tmp_path)
        assert app.keys.gen_keys("exitN1", tmp_path) is False

    def test_force_overwrites_and_returns_true(self, app: HexRiftApp, tmp_path):
        app.keys.gen_keys("exitN1", tmp_path)
        first = app.keys.load_node_keys("exitN1", tmp_path)
        result = app.keys.gen_keys("exitN1", tmp_path, force=True)
        assert result is True
        # Key material changes on force re-gen
        second = app.keys.load_node_keys("exitN1", tmp_path)
        # Reality keys are random — they should differ
        assert first.reality_private_key != second.reality_private_key

    def test_disabled_keys_generates_none_strings(self, topology_yaml, tmp_path):
        """A node with keys.enabled=False should produce decryption='none'."""

        data = yaml.safe_load(topology_yaml.read_text())
        # Disable keys for exitN1
        data["regions"][0]["nodes"][0]["keys"] = {"enabled": False, "mode": "native", "session_time": "600s"}
        disabled_yaml = tmp_path / "disabled.yaml"
        disabled_yaml.write_text(yaml.dump(data))

        instance = HexRiftApp(yaml_path=disabled_yaml)
        instance.keys.gen_keys("exitN1", tmp_path / "keys")
        loaded = instance.keys.load_node_keys("exitN1", tmp_path / "keys")
        assert loaded.decryption == "none"
        assert loaded.encryption == "none"


class TestLoadNodeKeys:
    def test_load_after_generation(self, app: HexRiftApp, tmp_path):
        app.keys.gen_keys("exitN1", tmp_path)
        loaded = app.keys.load_node_keys("exitN1", tmp_path)
        assert isinstance(loaded, NodeKeys)
        assert loaded.reality_private_key
        assert loaded.reality_public_key
        assert loaded.decryption.startswith("mlkem768x25519plus")

    def test_load_missing_raises_keys_error(self, app: HexRiftApp, tmp_path):
        with pytest.raises(KeysError):
            app.keys.load_node_keys("exitN1", tmp_path)


class TestHubKeyReuse:
    def test_hub_siblings_share_keys(self, tmp_path):
        """Two hub nodes with identical key configs should reuse the same keys."""

        topology = {
            "global": {"namespace": "test.ns", "aphelion_domain": "ap.test.ns"},
            "defaults": {
                "exit": {"ipv6": True, "keys": {"auth": "mlkem768", "mode": "native", "session_time": "600s"}},
                "hub": {
                    "ipv6": True,
                    "keys": {"auth": "x25519", "mode": "native", "session_time": "600s"},
                    "exit_connections": {"method": "mlkem768x25519plus", "fingerprint": "chrome"},
                    "reality": {"dest": "vk.com:443", "xhttp_path": "/idx/"},
                },
            },
            "groups": [{"id": "grp1"}],
            "users": [{"username": "alice", "group": "grp1", "access": ["xhttp"]}],
            "routing": {"hub_default": "hub1"},
            "regions": [
                {
                    "id": "exit1",
                    "type": "exit",
                    "vless_route": 1000,
                    "nodes": [
                        {"id": "exitN1", "hostname": "e.test.ns", "reality": {"dest": "a.com:443", "xhttp_path": "/x/"}}
                    ],
                },
                {
                    "id": "hub1",
                    "type": "hub",
                    "nodes": [
                        {"id": "hubN1", "hostname": "h1.test.ns"},
                        {"id": "hubN2", "hostname": "h2.test.ns"},
                    ],
                },
            ],
        }
        topo_file = tmp_path / "topo.yaml"
        topo_file.write_text(yaml.dump(topology))
        keys_dir = tmp_path / "keys"

        app = HexRiftApp(yaml_path=topo_file)
        app.keys.gen_keys("hubN1", keys_dir)
        app.keys.gen_keys("hubN2", keys_dir)

        k1 = app.keys.load_node_keys("hubN1", keys_dir)
        k2 = app.keys.load_node_keys("hubN2", keys_dir)
        # Reality keys should be shared
        assert k1.reality_private_key == k2.reality_private_key
        assert k1.decryption == k2.decryption
