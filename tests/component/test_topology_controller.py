import shutil
import stat
import sys
from pathlib import Path

import pytest

from hexrift.app import HexRiftApp
from hexrift.components.schema.models.fields import validate_masquerade_url
from hexrift.components.topology.controller import VLESS_ROUTE_RANGE, masquerade_url, pick_vless_route, region_prefix
from hexrift.components.topology.edit import RealitySpec
from hexrift.constants import RegionType
from hexrift.errors import TopologyError


FIXTURE_TOPOLOGY = Path(__file__).parent.parent / "fixtures" / "topology.yaml"

DE_A00_BLOCK = """\
      - id: deA00
        hostname: deA00.ap.test.hexrift
        reality:
          dest: www.microsoft.com:443
          xhttp_path: /update/
"""

DE_EMPTY_BLOCK = """\
  - id: de
    type: exit
    vless_route: 2000
    protocol: hysteria
    hysteria:
      obfs: true
      congestion: brutal
      up: "200 mbps"
      down: "500 mbps"
    nodes:
  - id: msk
"""

NL_A20_BLOCK = """\
      - id: nlA20
        hostname: nlA20.ap.test.hexrift
        reality:
          dest: www.samsung.com:443
          server_names: [www.samsung.com, samsung.com]
          xhttp_path: /login/
        hysteria:
          obfs: true
          sni: nlA20.ap.test.hexrift
          masquerade_url: https://www.samsung.com
  - id: de
"""


@pytest.fixture()
def topo(tmp_path: Path) -> Path:
    return Path(shutil.copy(FIXTURE_TOPOLOGY, tmp_path / "topology.yaml"))


@pytest.fixture()
def fixture_app(topo: Path) -> HexRiftApp:
    return HexRiftApp(yaml_path=topo)


class TestRegionPrefix:
    @pytest.mark.parametrize(("node_id", "prefix"), [("nlA20", "nl"), ("mskX00", "msk"), ("us1", "us")])
    def test_leading_lowercase_letters(self, node_id, prefix):
        assert region_prefix(node_id) == prefix

    def test_rejects_id_without_prefix(self):
        with pytest.raises(TopologyError, match="pass --region"):
            region_prefix("A20")


class TestPickVlessRoute:
    def test_exhausted_range_is_rejected(self):
        low, high = VLESS_ROUTE_RANGE
        with pytest.raises(TopologyError, match="No unused vless_route"):
            pick_vless_route(set(range(low, high + 1)))


class TestMasqueradeUrl:
    @pytest.mark.parametrize(
        ("dest", "url"),
        [
            ("www.samsung.com:443", "https://www.samsung.com"),
            ("a.com:8443", "https://a.com:8443"),
            ("[2001:db8::1]:443", "https://[2001:db8::1]"),
        ],
    )
    def test_https_with_port_kept_unless_443(self, dest, url):
        assert masquerade_url(dest) == url
        assert validate_masquerade_url(url) == url


class TestAddNode:
    def test_exit_node_joins_its_region_with_derived_hostname(self, fixture_app: HexRiftApp, topo: Path):
        result = fixture_app.topology.add_node(
            "nlA20",
            reality=RealitySpec(
                dest="www.samsung.com:443",
                server_names=("www.samsung.com", "samsung.com"),
                xhttp_path="/login/",
            ),
        )
        assert result is not None and not result.created
        assert result.region.id == "nl"
        assert result.region.type == RegionType.EXIT
        assert result.node.hostname == "nlA20.ap.test.hexrift"
        assert result.validation_error is None
        assert NL_A20_BLOCK in topo.read_text()
        region, node = fixture_app.schema.get_node("nlA20")
        assert region.id == "nl"
        assert node.reality is not None and node.reality.dest == "www.samsung.com:443"
        assert node.hysteria is not None and node.hysteria.obfs is True
        assert node.hysteria.sni == "nlA20.ap.test.hexrift"
        assert node.hysteria.masquerade_url == "https://www.samsung.com"

    def test_hub_node_follows_sibling_hostname_domain(self, fixture_app: HexRiftApp, topo: Path):
        result = fixture_app.topology.add_node("mskA20")
        assert result is not None and not result.created
        assert result.region.type == RegionType.HUB
        assert result.node.hostname == "mskA20.ap.test.hexrift"
        assert result.validation_error is None
        assert [n.id for n in fixture_app.schema.get_region("msk").nodes] == ["mskA00", "mskA20"]
        assert "      - id: mskA20\n        hostname: mskA20.ap.test.hexrift\n  - id: jp\n" in topo.read_text()

    def test_new_exit_region_gets_unused_vless_route(self, fixture_app: HexRiftApp):
        result = fixture_app.topology.add_node(
            "usA00",
            node_type=RegionType.EXIT,
            reality=RealitySpec(dest="www.samsung.com:443", xhttp_path="/login/"),
        )
        assert result is not None and result.created
        route = result.region.vless_route
        assert route is not None and VLESS_ROUTE_RANGE[0] <= route <= VLESS_ROUTE_RANGE[1]
        assert route not in {1000, 2000, 3000, 3001}
        assert result.validation_error is None
        region = fixture_app.schema.get_region("us")
        assert region.vless_route == route
        assert [n.id for n in region.nodes] == ["usA00"]

    def test_new_region_requires_type(self, fixture_app: HexRiftApp, topo: Path):
        before = topo.read_text()
        with pytest.raises(TopologyError, match="pass --type"):
            fixture_app.topology.add_node("usA00")
        assert topo.read_text() == before

    def test_missing_aphelion_domain_requires_hostname(self, tmp_path: Path):
        topo = tmp_path / "topology.yaml"
        topo.write_text("regions:\n  - id: nl\n    type: exit\n    nodes:\n      - id: nlA00\n        hostname: h.x\n")
        app = HexRiftApp(yaml_path=topo)
        with pytest.raises(TopologyError, match="pass --hostname"):
            app.topology.add_node("nlA10")

    def test_type_mismatch_is_reported_before_hostname_derivation(self, tmp_path: Path):
        topo = tmp_path / "topology.yaml"
        topo.write_text("regions:\n  - id: nl\n    type: exit\n    nodes:\n      - id: nlA00\n        hostname: h.x\n")
        with pytest.raises(TopologyError, match="has type 'exit'"):
            HexRiftApp(yaml_path=topo).topology.add_node("nlA20", node_type=RegionType.HUB)

    def test_exit_without_reality_is_written_with_validation_error(self, fixture_app: HexRiftApp, topo: Path):
        result = fixture_app.topology.add_node("nlA20")
        assert result is not None and not result.created
        assert result.validation_error is not None
        assert "Exit node 'nlA20' in region 'nl' must have reality config" in result.validation_error
        assert (
            "      - id: nlA20\n        hostname: nlA20.ap.test.hexrift\n"
            "        hysteria:\n          obfs: true\n          sni: nlA20.ap.test.hexrift\n  - id: de\n"
        ) in topo.read_text()

    def test_edits_keep_working_while_file_is_invalid(self, fixture_app: HexRiftApp):
        fixture_app.topology.add_node("nlA20")
        result = fixture_app.topology.add_node("nlA30", reality=RealitySpec(dest="a.com:443", xhttp_path="/x/"))
        assert result is not None and not result.created
        assert result.validation_error is not None

    def test_existing_node_is_skipped_without_writing(self, fixture_app: HexRiftApp, topo: Path):
        before = topo.read_text()
        assert fixture_app.topology.add_node("nlA00", node_type=RegionType.HUB) is None
        assert topo.read_text() == before


class TestFileHandling:
    def test_keeps_crlf_line_endings(self, topo: Path):
        crlf = topo.read_bytes().replace(b"\n", b"\r\n")
        topo.write_bytes(crlf)
        HexRiftApp(yaml_path=topo).topology.remove_node("deA00")
        assert topo.read_bytes() == crlf.replace(DE_A00_BLOCK.encode().replace(b"\n", b"\r\n"), b"")

    def test_edits_symlink_target_in_place(self, tmp_path: Path):
        real = tmp_path / "real.yaml"
        shutil.copy(FIXTURE_TOPOLOGY, real)
        link = tmp_path / "topology.yaml"
        link.symlink_to(real)
        HexRiftApp(yaml_path=link).topology.remove_node("deA00")
        assert link.is_symlink()
        assert DE_EMPTY_BLOCK in real.read_text()

    @pytest.mark.skipif(sys.platform == "win32", reason="chmod not enforced on Windows")
    def test_keeps_file_mode(self, topo: Path):
        topo.chmod(0o600)
        HexRiftApp(yaml_path=topo).topology.remove_node("deA00")
        assert stat.S_IMODE(topo.stat().st_mode) == 0o600

    def test_failed_replace_leaves_no_tmp_file(self, topo: Path, monkeypatch: pytest.MonkeyPatch):
        def refuse(self: Path, target: Path) -> Path:
            raise OSError("locked")

        monkeypatch.setattr(Path, "replace", refuse)
        with pytest.raises(TopologyError, match="locked"):
            HexRiftApp(yaml_path=topo).topology.remove_node("deA00")
        assert [p.name for p in topo.parent.iterdir()] == ["topology.yaml"]


class TestRemoveNode:
    def test_removing_only_node_keeps_region(self, fixture_app: HexRiftApp, topo: Path):
        result = fixture_app.topology.remove_node("deA00")
        assert result is not None and result.emptied
        assert result.region_id == "de"
        assert result.validation_error is None
        assert DE_EMPTY_BLOCK in topo.read_text()
        assert fixture_app.schema.get_region("de").nodes == []

    def test_emptying_default_region_warns_about_hub_default(self, fixture_app: HexRiftApp):
        result = fixture_app.topology.remove_node("nlA00")
        assert result is not None and result.emptied
        assert result.validation_error is not None
        assert "hub_default 'nl' is a region with no nodes" in result.validation_error

    def test_missing_node_leaves_file_untouched(self, fixture_app: HexRiftApp, topo: Path):
        before = topo.read_text()
        assert fixture_app.topology.remove_node("ghost") is None
        assert topo.read_text() == before

    def test_readding_node_reuses_kept_region(self, fixture_app: HexRiftApp):
        reality = RealitySpec(dest="a.com:443", xhttp_path="/x/")
        created = fixture_app.topology.add_node("usA00", node_type=RegionType.EXIT, reality=reality)
        fixture_app.topology.remove_node("usA00")
        readded = fixture_app.topology.add_node("usA00", reality=reality)
        assert readded is not None and not readded.created
        assert readded.validation_error is None
        assert created is not None
        assert fixture_app.schema.get_region("us").vless_route == created.region.vless_route
