from __future__ import annotations

from typing import TYPE_CHECKING

import rich_click as click
from rich.markup import escape

from hexrift.components.topology.controller import TopologyController
from hexrift.components.topology.edit import RealitySpec
from hexrift.constants import RegionType
from hexrift.core.component import BaseComponent


if TYPE_CHECKING:
    from hexrift.app import HexRiftApp


class TopologyComponent(BaseComponent["HexRiftApp", TopologyController]):
    name = "topology"
    controller_class = TopologyController
    expose_controller = True

    @classmethod
    def expose_cli(cls, base: click.Group) -> None:
        nodes = cls.subgroup(base, "nodes")

        @nodes.command("add")
        @click.argument("node_id")
        @click.option(
            "--type",
            "node_type",
            type=click.Choice([t.value for t in RegionType]),
            help="Region type, required when region does not exist yet.",
        )
        @click.option(
            "--region",
            "region_id",
            help="Region id (default: leading lowercase letters of NODE_ID).",
        )
        @click.option(
            "--hostname",
            help="Node hostname (default: derived from aphelion_domain for exits, from sibling hubs for hubs).",
        )
        @click.option(
            "--no-ipv6",
            is_flag=True,
            help="Set `ipv6: false` on node.",
        )
        @click.option(
            "--reality-dest",
            help="Reality dest, e.g. www.samsung.com:443, also the Hysteria masquerade target.",
        )
        @click.option(
            "--reality-xhttp-path",
            help="Reality xhttp_path, e.g. /login/.",
        )
        @click.option(
            "--reality-server-names",
            help="Comma-separated Reality SNI list.",
        )
        @click.pass_obj
        def add_node(
            app: HexRiftApp,
            node_id: str,
            node_type: str | None,
            region_id: str | None,
            hostname: str | None,
            no_ipv6: bool,
            reality_dest: str | None,
            reality_xhttp_path: str | None,
            reality_server_names: str | None,
        ) -> None:
            """Add NODE_ID to its region, creating region when missing."""

            if reality_dest is None and (reality_server_names or reality_xhttp_path):
                raise click.UsageError("--reality-server-names and --reality-xhttp-path require --reality-dest.")
            reality = None
            if reality_dest is not None:
                if reality_xhttp_path is None:
                    raise click.UsageError("--reality-dest requires --reality-xhttp-path.")
                names = tuple(s.strip() for s in (reality_server_names or "").split(",") if s.strip())
                reality = RealitySpec(
                    dest=reality_dest,
                    xhttp_path=reality_xhttp_path,
                    server_names=names,
                )

            result = app.topology.add_node(
                node_id,
                region_id=region_id,
                node_type=RegionType(node_type) if node_type else None,
                hostname=hostname,
                ipv6=not no_ipv6,
                reality=reality,
            )
            if result is None:
                app.console.print(f"  [yellow]skipped[/yellow]  {node_id} is already in the topology")
                return
            region, node = result.region, result.node
            if result.created:
                route = f", vless_route {region.vless_route}" if region.vless_route is not None else ""
                app.console.print(
                    f"  [green]created[/green]  region {region.id} ({region.type}{route})"
                    f" with {node_id}  [dim]{node.hostname}[/dim]"
                )
            else:
                fb = (
                    f"  [dim](set lb_fallback: {escape(result.set_lb_fallback)})[/dim]"
                    if result.set_lb_fallback
                    else ""
                )
                app.console.print(
                    f"  [green]added[/green]    {node_id} to region {region.id} ({region.type})"
                    f"  [dim]{node.hostname}[/dim]{fb}"
                )
            _warn_invalid(app, result.validation_error)

        @nodes.command("remove")
        @click.argument("node_id")
        @click.pass_obj
        def remove_node(app: HexRiftApp, node_id: str) -> None:
            """Remove NODE_ID from its region."""

            result = app.topology.remove_node(node_id)
            shown = escape(node_id)
            if result is None:
                app.console.print(f"  [yellow]skipped[/yellow]  {shown} is not in the topology")
                return
            dropped = []
            if result.dropped_routes:
                plural = "s" if len(result.dropped_routes) > 1 else ""
                dropped.append(f"hub route{plural} {', '.join(escape(d) for d in result.dropped_routes)}")
            if result.dropped_lb_fallback:
                dropped.append("lb_fallback")
            suffix = f"  [dim](dropped {' and '.join(dropped)})[/dim]" if dropped else ""
            if result.emptied:
                suffix += "  [yellow](region now empty)[/yellow]"
            app.console.print(f"  [green]removed[/green]  {shown} from region {escape(str(result.region_id))}{suffix}")
            _warn_invalid(app, result.validation_error)


def _warn_invalid(app: HexRiftApp, error: str | None) -> None:
    if error is not None:
        app.console.print(
            f"\n[bold yellow]Warning:[/bold yellow] topology was written but no longer validates:\n{error}"
        )
