import sys

import pytest
import yaml

from hexrift.components.keys.store import NodeKeys, load_node_keys, node_keys_exist, save_node_keys
from hexrift.errors import KeysError


@pytest.fixture
def sample_keys() -> NodeKeys:
    return NodeKeys(
        reality_private_key="test-reality-private-key",
        reality_public_key="test-reality-public-key",
        decryption="mlkem768x25519plus.native.600s.AAABBBCCC",
        encryption="mlkem768x25519plus.native.0rtt.DDDEEEFFF",
    )


class TestNodeKeysExist:
    def test_false_when_missing(self, tmp_path):
        assert node_keys_exist("nlA00", tmp_path) is False

    def test_true_after_save(self, tmp_path, sample_keys):
        save_node_keys("nlA00", tmp_path, sample_keys)
        assert node_keys_exist("nlA00", tmp_path) is True


class TestSaveAndLoad:
    def test_roundtrip(self, tmp_path, sample_keys):
        save_node_keys("nlA00", tmp_path, sample_keys)
        loaded = load_node_keys("nlA00", tmp_path)
        assert loaded == sample_keys

    def test_saved_file_has_correct_name(self, tmp_path, sample_keys):
        save_node_keys("nlA00", tmp_path, sample_keys)
        assert (tmp_path / "nlA00.yaml").exists()

    def test_creates_directory(self, tmp_path, sample_keys):
        keys_dir = tmp_path / "nested" / "keys"
        save_node_keys("nlA00", keys_dir, sample_keys)
        assert (keys_dir / "nlA00.yaml").exists()

    @pytest.mark.skipif(sys.platform == "win32", reason="chmod not enforced on Windows")
    def test_file_mode_is_600(self, tmp_path, sample_keys):
        save_node_keys("nlA00", tmp_path, sample_keys)
        path = tmp_path / "nlA00.yaml"
        assert oct(path.stat().st_mode)[-3:] == "600"

    def test_no_temp_files_left_behind(self, tmp_path, sample_keys):
        save_node_keys("nlA00", tmp_path, sample_keys)
        leftovers = [p.name for p in tmp_path.iterdir() if p.name != "nlA00.yaml"]
        assert leftovers == []


class TestLoadErrors:
    def test_load_missing_raises_keys_error(self, tmp_path):
        with pytest.raises(KeysError):
            load_node_keys("ghost", tmp_path)

    def test_load_corrupt_yaml_raises_keys_error(self, tmp_path):
        path = tmp_path / "bad.yaml"
        path.write_text(": invalid: yaml: {{{")
        with pytest.raises(KeysError):
            load_node_keys("bad", tmp_path)

    def test_load_missing_fields_raises_keys_error(self, tmp_path):
        path = tmp_path / "partial.yaml"
        path.write_text(yaml.dump({"reality_private_key": "abc"}))
        with pytest.raises(KeysError):
            load_node_keys("partial", tmp_path)

    def test_load_unreadable_path_raises_keys_error(self, tmp_path):
        (tmp_path / "dirnode.yaml").mkdir()
        with pytest.raises(KeysError):
            load_node_keys("dirnode", tmp_path)


class TestPathValidation:
    @pytest.mark.parametrize("node_id", ["../evil", "a\\b", "a/b", "."])
    def test_invalid_node_id_rejected(self, tmp_path, node_id):
        with pytest.raises(ValueError, match="Invalid node ID"):
            node_keys_exist(node_id, tmp_path)
