import pytest
from pydantic import TypeAdapter, ValidationError

from hexrift.components.schema.models.regions import (
    ExitNode,
    ExitRegion,
    HubNode,
    HubRegion,
    LeastLoadSettings,
    Region,
)
from hexrift.constants import LbStrategy, RegionType


class TestLeastLoadSettings:
    def test_defaults(self):
        s = LeastLoadSettings()
        assert s.tolerance == 0.5
        assert s.max_rtt == "750ms"
        assert s.expected == 1

    def test_tolerance_lower_bound(self):
        s = LeastLoadSettings(tolerance=0.0)
        assert s.tolerance == 0.0

    def test_tolerance_upper_bound(self):
        s = LeastLoadSettings(tolerance=1.0)
        assert s.tolerance == 1.0

    def test_tolerance_below_zero_raises(self):
        with pytest.raises(ValidationError):
            LeastLoadSettings(tolerance=-0.1)

    def test_tolerance_above_one_raises(self):
        with pytest.raises(ValidationError):
            LeastLoadSettings(tolerance=1.01)

    def test_max_rtt_ms_valid(self):
        assert LeastLoadSettings(max_rtt="750ms").max_rtt == "750ms"

    def test_max_rtt_s_valid(self):
        assert LeastLoadSettings(max_rtt="10s").max_rtt == "10s"

    def test_max_rtt_invalid_unit_raises(self):
        with pytest.raises(ValidationError):
            LeastLoadSettings(max_rtt="10m")

    def test_max_rtt_no_unit_raises(self):
        with pytest.raises(ValidationError):
            LeastLoadSettings(max_rtt="750")

    def test_baselines_invalid_entry_rejected(self):
        with pytest.raises(ValidationError):
            LeastLoadSettings(baselines=["30ms", "bad"])

    def test_expected_minimum_one(self):
        with pytest.raises(ValidationError):
            LeastLoadSettings(expected=0)

    def test_xray_settings_has_expected_keys(self):
        s = LeastLoadSettings()
        xs = s.xray_settings
        assert "baselines" in xs and "expected" in xs and "maxRTT" in xs and "tolerance" in xs


class TestNodes:
    def test_hub_minimal_valid(self):
        n = HubNode(id="n1", hostname="n1.example.com")
        assert n.id == "n1"
        assert n.reality is None
        assert n.ipv6 is None

    @pytest.mark.parametrize("model", [ExitNode, HubNode])
    def test_extra_field_forbidden(self, model):
        with pytest.raises(ValidationError):
            model.model_validate(
                {
                    "id": "n1",
                    "hostname": "n1.example.com",
                    "unknown_field": "x",
                },
            )

    @pytest.mark.parametrize(
        "bad_id",
        [
            "bad id",
            "weird!",
            "dotted.id",
            "",
        ],
    )
    def test_invalid_id_rejected(self, bad_id: str):
        with pytest.raises(ValidationError):
            HubNode.model_validate(
                {
                    "id": bad_id,
                    "hostname": "n1.example.com",
                },
            )

    @pytest.mark.parametrize(
        "bad_host",
        [
            "bad host",
            "host!",
            "",
        ],
    )
    def test_invalid_hostname_rejected(self, bad_host: str):
        with pytest.raises(ValidationError):
            HubNode.model_validate(
                {
                    "id": "n1",
                    "hostname": bad_host,
                },
            )


class TestRegionDispatch:
    def test_type_selects_region_and_node_models(self):
        regions = TypeAdapter(list[Region]).validate_python(
            [
                {"id": "e", "type": "exit", "nodes": [{"id": "e1", "hostname": "e1.x", "lb_role": "backup"}]},
                {"id": "h", "type": "hub", "nodes": [{"id": "h1", "hostname": "h1.x", "proxy_inbound": True}]},
            ]
        )
        assert isinstance(regions[0], ExitRegion) and isinstance(regions[0].nodes[0], ExitNode)
        assert isinstance(regions[1], HubRegion) and isinstance(regions[1].nodes[0], HubNode)

    @pytest.mark.parametrize(
        ("region", "field"),
        [
            (
                {"id": "e", "type": "exit", "nodes": [{"id": "e1", "hostname": "e1.x", "xdns": {"domains": ["d"]}}]},
                "xdns",
            ),
            ({"id": "h", "type": "hub", "nodes": [{"id": "h1", "hostname": "h1.x", "lb_role": "backup"}]}, "lb_role"),
            ({"id": "h", "type": "hub", "vless_route": 1, "nodes": []}, "vless_route"),
        ],
    )
    def test_other_kind_fields_rejected(self, region: dict, field: str):
        with pytest.raises(ValidationError, match=f"{field}\\n  Extra inputs are not permitted"):
            TypeAdapter(list[Region]).validate_python([region])


class TestRegionValidation:
    def test_lb_strategy_enum_accepted(self):
        r = ExitRegion(
            id="r1",
            type=RegionType.EXIT,
            lb_strategy=LbStrategy.LEAST_LOAD,
            nodes=[
                ExitNode(
                    id="n1",
                    hostname="n1.example.com",
                ),
            ],
        )
        assert r.lb_strategy is LbStrategy.LEAST_LOAD

    def test_lb_strategy_string_coerced(self):
        r = ExitRegion.model_validate(
            {
                "id": "r1",
                "type": "exit",
                "lb_strategy": "roundRobin",
                "nodes": [
                    {
                        "id": "n1",
                        "hostname": "h.example.com",
                    },
                ],
            }
        )
        assert r.lb_strategy is LbStrategy.ROUND_ROBIN

    def test_lb_strategy_invalid_rejected(self):
        with pytest.raises(ValidationError):
            ExitRegion.model_validate(
                {
                    "id": "r1",
                    "type": "exit",
                    "lb_strategy": "bogus",
                    "nodes": [
                        {
                            "id": "n1",
                            "hostname": "h.example.com",
                        },
                    ],
                }
            )

    @pytest.mark.parametrize("bad", [-1, 65536])
    def test_vless_route_out_of_range_rejected(self, bad: int):
        with pytest.raises(ValidationError):
            ExitRegion(
                id="r1",
                type=RegionType.EXIT,
                vless_route=bad,
                nodes=[
                    ExitNode(
                        id="n1",
                        hostname="n1.example.com",
                    ),
                ],
            )

    def test_cdn_xhttp_path_must_start_with_slash(self):
        with pytest.raises(ValidationError, match="must start with"):
            ExitRegion(
                id="r1",
                type=RegionType.EXIT,
                cdn_xhttp_path="cdn/",
                nodes=[
                    ExitNode(
                        id="n1",
                        hostname="n1.example.com",
                    ),
                ],
            )

    @pytest.mark.parametrize("bad_id", ["bad id", "weird!", ""])
    def test_invalid_region_id_rejected(self, bad_id: str):
        with pytest.raises(ValidationError):
            ExitRegion.model_validate(
                {
                    "id": bad_id,
                    "type": "exit",
                    "nodes": [
                        {
                            "id": "n1",
                            "hostname": "h.example.com",
                        },
                    ],
                },
            )
