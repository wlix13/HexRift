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


@pytest.mark.parametrize("chrome_parrot", [True, False])
def test_trunk_quic_params_spell_out_the_chrome_parrot(chrome_parrot: bool):
    ctx = make_hysteria_outbound(chrome_parrot=chrome_parrot)
    assert render_link(ctx, ipv6=True)["streamSettings"]["finalmask"]["quicParams"] == {
        "congestion": "bbr",
        "keepAlivePeriod": 10,
        "maxStreamReceiveWindow": 16 * 1024 * 1024,
        "maxConnectionReceiveWindow": 64 * 1024 * 1024,
        "disableChromeParrot": not chrome_parrot,
    }


def test_narrow_rejects_foreign_context():
    with pytest.raises(RenderError):
        HYSTERIA_LINK.narrow(LinkContext(exit_id="x"))
