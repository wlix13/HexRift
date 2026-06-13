import pytest
import yaml

from hexrift.app import HexRiftApp
from hexrift.components.schema.models.root import ConglomerateConfig
from hexrift.constants import RegionType
from hexrift.errors import Error, NodeError, RegionError, SchemaValidationError


class TestLoad:
    def test_load_valid_topology(self, app: HexRiftApp):
        assert isinstance(app.schema.config, ConglomerateConfig)

    def test_namespace_matches_topology(self, app: HexRiftApp):
        assert app.schema.config.global_.namespace == "test.ns"

    def test_load_missing_file_raises_error(self, tmp_path):
        instance = HexRiftApp(yaml_path=tmp_path / "nonexistent.yaml")
        with pytest.raises(Error):
            _ = instance.schema.config

    def test_load_invalid_yaml_raises_error(self, tmp_path):
        bad = tmp_path / "bad.yaml"
        bad.write_text(": invalid: {{{")

        instance = HexRiftApp(yaml_path=bad)
        with pytest.raises(Error):
            _ = instance.schema.config

    def test_load_invalid_schema_raises_schema_validation_error(self, tmp_path):
        wrong = tmp_path / "wrong.yaml"
        wrong.write_text(yaml.dump({"global": {"namespace": "x"}}))  # missing required fields

        instance = HexRiftApp(yaml_path=wrong)
        with pytest.raises(SchemaValidationError):
            _ = instance.schema.config


class TestRegionAndNodeHelpers:
    def test_get_exit_regions(self, app: HexRiftApp):
        exits = app.schema.get_exit_regions()
        assert all(r.type == RegionType.EXIT for r in exits)
        assert len(exits) == 1

    def test_get_hub_regions(self, app: HexRiftApp):
        hubs = app.schema.get_hub_regions()
        assert all(r.type == RegionType.HUB for r in hubs)
        assert len(hubs) == 1

    def test_get_all_nodes_count(self, app: HexRiftApp):
        pairs = app.schema.get_all_nodes()
        assert len(pairs) == 2  # exitN1 + hubN1

    def test_get_node_found(self, app: HexRiftApp):
        region, node = app.schema.get_node("exitN1")
        assert node.id == "exitN1"
        assert region.id == "exit1"

    def test_get_node_not_found(self, app: HexRiftApp):
        with pytest.raises(NodeError):
            app.schema.get_node("ghost")

    def test_get_region_found(self, app: HexRiftApp):
        region = app.schema.get_region("exit1")
        assert region.id == "exit1"

    def test_get_region_not_found(self, app: HexRiftApp):
        with pytest.raises(RegionError):
            app.schema.get_region("ghost")

    def test_config_lazy_loads(self, topology_yaml):
        """Accessing .config before explicit .load() still works."""

        instance = HexRiftApp(yaml_path=topology_yaml)
        cfg = instance.schema.config
        assert isinstance(cfg, ConglomerateConfig)
