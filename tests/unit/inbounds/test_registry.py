from types import SimpleNamespace
from typing import cast

import pytest

import hexrift.inbounds.registry as registry
from hexrift.constants import AccessType, RegionType
from hexrift.errors import RenderError
from hexrift.inbounds.base import InboundEnv
from hexrift.inbounds.cdn import CDN_SPEC, CdnContext
from hexrift.inbounds.registry import INBOUND_SPECS, specs_for
from hexrift.inbounds.xhttp import XHTTP_SPEC
from tests.unit.render.helpers import make_cdn, make_xhttp


class TestRegistryOrder:
    def test_order_is_load_bearing(self):
        # Registry order reproduces inbound emission order in generated configs —
        # changing it changes deployed config bytes.
        assert [s.access_type for s in INBOUND_SPECS] == [
            AccessType.XHTTP,
            AccessType.CDN,
            AccessType.PROXY,
            AccessType.XDNS,
            AccessType.WIREGUARD,
            AccessType.HYSTERIA,
        ]


class TestSpecsFor:
    def test_exit_role_gets_xhttp_cdn_hysteria(self):
        assert [s.access_type for s in specs_for(RegionType.EXIT)] == [
            AccessType.XHTTP,
            AccessType.CDN,
            AccessType.HYSTERIA,
        ]

    def test_hub_role_gets_all_specs(self):
        assert len(specs_for(RegionType.HUB)) == len(INBOUND_SPECS)


class TestBuildSlots:
    def test_duplicate_access_type_fails_fast(self, monkeypatch):
        class FakeSpec:
            access_type = AccessType.XHTTP
            roles = frozenset({RegionType.HUB})

            def build_context(self, env):
                return make_xhttp()

        monkeypatch.setattr(registry, "INBOUND_SPECS", (FakeSpec(), FakeSpec()))
        env = cast(InboundEnv, SimpleNamespace(role=RegionType.HUB))
        with pytest.raises(ValueError, match="Duplicate inbound spec"):
            registry.build_slots(env)


class TestNarrow:
    def test_returns_none_when_slot_missing(self):
        assert CDN_SPEC.narrow({}) is None

    def test_returns_typed_context(self):
        cdn = make_cdn()
        result = CDN_SPEC.narrow({AccessType.CDN: cdn})
        assert isinstance(result, CdnContext)
        assert result is cdn

    def test_raises_domain_error_on_type_mismatch(self):
        # xhttp context stored under CDN key — wiring bug must surface as domain error
        with pytest.raises(RenderError):
            CDN_SPEC.narrow({AccessType.CDN: make_xhttp()})

    def test_xhttp_narrow_ignores_other_slots(self):
        xhttp = make_xhttp()
        slots = {AccessType.XHTTP: xhttp, AccessType.CDN: make_cdn()}
        assert XHTTP_SPEC.narrow(slots) is xhttp
