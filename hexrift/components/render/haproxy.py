"""Render HAProxy configs from Jinja2 templates."""

from __future__ import annotations

from hexrift.constants import DEFAULT_TRUSTED_HEADER, HTTP_HEADER_TOKEN_RE, RegionType, Socket
from hexrift.errors import RenderError
from hexrift.inbounds.cdn import CDN_SPEC
from hexrift.inbounds.context import ExitContext, HubContext
from hexrift.shared.templates import render_template


def _safe_header(headers: list[str]) -> str:
    """Return first configured trusted header, or default when none are set."""

    if not headers:
        return DEFAULT_TRUSTED_HEADER
    if not HTTP_HEADER_TOKEN_RE.fullmatch(headers[0]):
        raise RenderError(f"Invalid trusted forwarded header name: {headers[0]!r}")
    return headers[0]


def render_haproxy(ctx: ExitContext | HubContext) -> str:
    if not ctx.shared.haproxy:
        return render_template("haproxy", "haproxy_disabled.cfg.j2")

    node_type = RegionType.HUB if isinstance(ctx, HubContext) else RegionType.EXIT
    cdn = CDN_SPEC.narrow(ctx.slots)

    return render_template(
        "haproxy",
        "haproxy.cfg.j2",
        cdn_enabled=cdn is not None,
        cert_alias=cdn.cert_alias if cdn else None,
        cdn_domain=cdn.domain if cdn else None,
        node_type=node_type,
        ipv6=ctx.shared.ipv6,
        socket=Socket,
        trusted_forwarded_header=_safe_header(ctx.shared.trusted_forwarded_headers),
    )
