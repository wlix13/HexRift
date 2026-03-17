"""Render HAProxy configs from Jinja2 templates."""

from __future__ import annotations

from jinja2 import Environment, PackageLoader

from hexrift.components.render.context import ExitContext, HubContext
from hexrift.constants import RegionType, Socket


_env = Environment(
    loader=PackageLoader("hexrift", "templates/haproxy"),
    keep_trailing_newline=True,
    trim_blocks=True,
    lstrip_blocks=True,
    autoescape=False,  # noqa: S701
)


def render_haproxy(ctx: ExitContext | HubContext, node_type: str) -> str:
    template = _env.get_template("haproxy.cfg.j2")
    cdn_enabled = ctx.cdn_cert_alias is not None
    cdn_domain = None
    if cdn_enabled and ctx.cdn_xhttp_host:
        if node_type == RegionType.EXIT:
            parts = ctx.cdn_xhttp_host.split(".", 1)
            cdn_domain = parts[1] if len(parts) > 1 else ctx.cdn_xhttp_host
        else:
            cdn_domain = ctx.cdn_xhttp_host
    # TODO: Return when added support for unix sockets
    # proxy_inbound = isinstance(ctx, HubContext) and ctx.proxy_inbound
    return template.render(
        cdn_enabled=cdn_enabled,
        cert_alias=ctx.cdn_cert_alias,
        cdn_domain=cdn_domain,
        node_type=node_type,
        ipv6=ctx.ipv6,
        proxy_inbound=False,
        socket=Socket,
    )
