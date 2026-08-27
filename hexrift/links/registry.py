"""Link spec registry keyed by exit protocol."""

from __future__ import annotations

from typing import Any, Final

from hexrift.components.schema.models.resolve import resolve_link_protocol
from hexrift.constants import ExitProtocol
from hexrift.links.base import LinkContext, LinkEnv, LinkSpec
from hexrift.links.hysteria import HYSTERIA_LINK
from hexrift.links.vless import VLESS_LINK


LINK_SPECS: Final[dict[ExitProtocol, LinkSpec[Any]]] = {spec.protocol: spec for spec in (VLESS_LINK, HYSTERIA_LINK)}


def link_spec_for(protocol: ExitProtocol) -> LinkSpec[Any]:
    return LINK_SPECS[protocol]


def build_link(env: LinkEnv, identity: str, tag_prefix: str) -> LinkContext:
    """Dial context for one hub→exit pair using the exit region's protocol."""

    return link_spec_for(resolve_link_protocol(env.exit_region)).build_context(env, identity, tag_prefix)


def render_link(ctx: LinkContext, ipv6: bool) -> dict:
    spec = link_spec_for(ctx.protocol)
    return spec.fragment(spec.narrow(ctx), ipv6)
