import pytest

from hexrift.constants import ExitProtocol
from hexrift.errors import RenderError
from hexrift.links.base import LinkContext
from hexrift.links.hysteria import HYSTERIA_LINK
from hexrift.links.registry import LINK_SPECS, render_link
from tests.unit.render.helpers import make_hysteria_outbound


def test_every_exit_protocol_has_a_link_spec():
    assert set(LINK_SPECS) == set(ExitProtocol)
    assert all(spec.protocol == protocol for protocol, spec in LINK_SPECS.items())


def test_render_link_dispatches_on_context_protocol():
    ctx = make_hysteria_outbound(tag_prefix="warp-")
    out = render_link(ctx, ipv6=False)
    assert (out["tag"], out["protocol"]) == ("warp-deA00", "hysteria")
    assert out["streamSettings"]["sockopt"] == {"domainStrategy": "UseIPv4"}


def test_narrow_rejects_foreign_context():
    with pytest.raises(RenderError):
        HYSTERIA_LINK.narrow(LinkContext(exit_id="x"))
