from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import rich_click as click
from rich.rule import Rule
from rich.table import Table
from rich.tree import Tree

from hexrift.components.derive.controller import DeriveController
from hexrift.constants import AccessType, RegionType
from hexrift.core.component import BaseComponent


if TYPE_CHECKING:
    from hexrift.app import HexRiftApp
    from hexrift.components.schema.models.users import User

_ACCESS_STYLE = {
    AccessType.XHTTP: "cyan",
    AccessType.CDN: "blue",
    AccessType.PROXY: "dim white",
    AccessType.SERVER: "yellow",
    AccessType.WIREGUARD: "green",
    AccessType.XDNS: "magenta",
}


class DeriveComponent(BaseComponent["HexRiftApp", DeriveController]):
    name = "derive"
    controller_class = DeriveController
    expose_controller = True

    def on_register(self) -> None:
        self.app.schema.add_validator(self.controller.check_identity_collisions)

    @classmethod
    def expose_cli(cls, base: click.Group) -> None:
        @base.command()
        @click.argument("entity", type=click.Choice(["users", "groups", "portals", "nodes", "all"]))
        @click.pass_obj
        def derive(app: HexRiftApp, entity: str) -> None:
            """Show derived identifiers (UUIDs, shortIds, emails)."""

            if entity in ("users", "all"):
                _print_users(app)
            if entity in ("groups", "all"):
                _print_groups(app)
            if entity in ("portals", "all"):
                _print_portals(app)
            if entity in ("nodes", "all"):
                _print_nodes(app)

        @base.command()
        @click.argument("username")
        @click.option(
            "--hub",
            "hub_id",
            default=None,
            help="Hub node ID (default: all hub nodes).",
        )
        @click.option(
            "--fp",
            default=None,
            help="Client TLS fingerprint (default: from config).",
        )
        @click.option(
            "--cdn",
            is_flag=True,
            default=False,
            help="Generate CDN URL instead of direct Reality URL.",
        )
        @click.option(
            "--guest",
            "guest",
            default=None,
            help="Generate URL for a specific guest identity (label).",
        )
        @click.option(
            "--all-guests",
            "all_guests",
            is_flag=True,
            default=False,
            help="Generate URLs for all guests of the user.",
        )
        @click.option(
            "--wg",
            "--wireguard",
            "wireguard",
            is_flag=True,
            default=False,
            help="Generate WireGuard client config instead of a VLESS URL.",
        )
        @click.option(
            "--server",
            "server",
            is_flag=True,
            default=False,
            help="Generate config for the user's server identity.",
        )
        @click.option(
            "--bare",
            is_flag=True,
            default=False,
            help="Output raw URLs only (no formatting). Useful for piping: | clip",
        )
        @click.option(
            "--keys-dir",
            type=click.Path(path_type=Path),
            default=Path("keys"),
            show_default=True,
        )
        @click.pass_obj
        def share(
            app: HexRiftApp,
            username: str,
            hub_id: str | None,
            fp: str | None,
            cdn: bool,
            guest: str | None,
            all_guests: bool,
            wireguard: bool,
            server: bool,
            bare: bool,
            keys_dir: Path,
        ) -> None:
            """Generate VLESS share URL (or WireGuard config) for user on hub node."""

            if guest and all_guests:
                raise click.UsageError("--guest and --all-guests are mutually exclusive.")
            if server and (guest or all_guests):
                raise click.UsageError("--server cannot be combined with --guest or --all-guests.")
            if wireguard and cdn:
                raise click.UsageError("--wg cannot be combined with --cdn.")

            fingerprint = fp or app.schema.config.defaults.hub.exit_connections.fingerprint

            if wireguard:
                pairs = app.derive.build_wireguard_configs(
                    username,
                    hub_id,
                    keys_dir,
                    guest=guest,
                    server=server,
                    all_guests=all_guests,
                )
            else:
                pairs = app.derive.build_share_urls(
                    username,
                    hub_id,
                    keys_dir,
                    fingerprint,
                    cdn=cdn,
                    guest=guest,
                    server=server,
                    all_guests=all_guests,
                )
            _print_share_urls(app, pairs, bare=bare)

        @base.command("nodes")
        @click.option("--names", "output", flag_value="names", help="Output node IDs only.")
        @click.option("--domains", "output", flag_value="domains", help="Output hostnames only.")
        @click.option(
            "--type",
            "region_type",
            type=click.Choice(["exit", "hub"]),
            default=None,
            help="Filter by region type.",
        )
        @click.pass_obj
        def nodes(app: HexRiftApp, output: str | None, region_type: str | None) -> None:
            """List all nodes with their hostnames (can be used in automation scripts)."""

            pairs = app.schema.get_all_nodes()
            if region_type:
                pairs = [(r, n) for r, n in pairs if r.type.value.lower() == region_type]

            for _, node in pairs:
                if output == "names":
                    click.echo(node.id)
                elif output == "domains":
                    click.echo(node.hostname)
                else:
                    click.echo(f"{node.id}\t{node.hostname}")

        @base.command()
        @click.pass_obj
        def show(app: HexRiftApp) -> None:
            """Visualize network topology."""

            _print_topology(app)


def _print_topology(app: HexRiftApp) -> None:
    cfg = app.schema.config
    g = cfg.global_
    kv = [
        ("Namespace", g.namespace),
        ("Aphelion", g.aphelion_domain),
    ]
    if g.cdn:
        kv.extend(
            [
                ("CDN exit", g.cdn.exit_domain),
                ("CDN hub", g.cdn.hub_domain),
            ]
        )
    for key, val in kv:
        app.console.print(f"[bold dim]{key:<10}[/bold dim] [white]{val}[/white]")
    app.console.print()

    tree = Tree("[bold cyan]Regions[/bold cyan]")
    for region in cfg.regions:
        if region.type == RegionType.EXIT:
            extras = []
            if region.vless_route is not None:
                hex_route = format(region.vless_route, "04x")
                extras.append(f"[dim]route={region.vless_route} [cyan]{hex_route}[/cyan][/dim]")
            if region.warp is not None:
                hex_warp = format(region.warp.vless_route, "04x")
                extras.append(f"[magenta]warp={region.warp.vless_route} {hex_warp}[/magenta]")
            extra_str = "  " + "  ".join(extras) if extras else ""
            r_branch = tree.add(f"[green]{region.id}[/green] [dim]exit[/dim]{extra_str}")
        else:
            r_branch = tree.add(f"[yellow]{region.id}[/yellow] [dim]hub[/dim]")
        for node in region.nodes:
            tags = []
            if node.lb_role:
                tags.append(f"LB: [dim]{node.lb_role}[/dim]")
            tag_str = "  " + " ".join(tags) if tags else ""
            r_branch.add(f"[bold]{node.id}[/bold]  [dim]{node.hostname}[/dim]{tag_str}")
    app.console.print(tree)
    app.console.print()

    # Group users by group
    groups_order: list[str] = []
    groups_map: dict[str, list[User]] = {}
    for user in cfg.users:
        if user.group not in groups_map:
            groups_order.append(user.group)
            groups_map[user.group] = []
        groups_map[user.group].append(user)

    user_tree = Tree("[bold cyan]Users[/bold cyan]")
    for group_id in groups_order:
        g_branch = user_tree.add(f"[bold magenta]{group_id}[/bold magenta]")
        for user in groups_map[group_id]:
            badges = " ".join(f"[{_ACCESS_STYLE.get(a, 'white')}]{a}[/]" for a in user.access)
            u_node = g_branch.add(f"[bold]{user.username}[/bold]  {badges}")
            if user.guests:
                labels = ", ".join(user.guests)
                u_node.add(f"[bold green]guests[/bold green] {labels}")
    app.console.print(user_tree)

    if cfg.portals:
        app.console.print()
        portal_tree = Tree("[bold cyan]Portals[/bold cyan]")
        for portal in cfg.portals:
            members = ", ".join(portal.users)
            portal_tree.add(f"[bold yellow]{portal.id}[/bold yellow]  [dim]users:[/dim] {members}")
        app.console.print(portal_tree)


def _print_share_urls(
    app: HexRiftApp,
    pairs: list[tuple[str, str]],
    bare: bool = False,
) -> None:
    if bare:
        for _label, url in pairs:
            click.echo(url)
        return
    for label, url in pairs:
        app.console.print(Rule(f"[bold cyan]{label}[/bold cyan]", style="dim"))
        app.console.print(url, soft_wrap=True)
    if pairs:
        app.console.print(Rule(style="dim"))


def _print_users(app: HexRiftApp) -> None:
    rows = app.derive.derive_users()
    table = Table(title="Users", show_header=True, header_style="bold cyan")
    table.add_column("Username", style="bold")
    table.add_column("UUID")
    table.add_column("Email")
    table.add_column("Server UUID")
    table.add_column("ShortId")
    for row in rows:
        table.add_row(
            row.username,
            row.uuid,
            row.email,
            row.server_uuid or "—",
            "—",
        )
        for guest in row.guests:
            table.add_row(
                f"[dim]  {guest.label}[/dim]",
                f"[dim]{guest.uuid}[/dim]",
                f"[dim]{guest.email}[/dim]",
                "—",
                f"[dim]{guest.short_id}[/dim]",
            )
    app.console.print(table)


def _print_groups(app: HexRiftApp) -> None:
    rows = app.derive.derive_groups()
    table = Table(title="Groups", show_header=True, header_style="bold cyan")
    table.add_column("ID", style="bold")
    table.add_column("ShortId")
    for row in rows:
        table.add_row(row.id, row.short_id)
    app.console.print(table)


def _print_portals(app: HexRiftApp) -> None:
    rows = app.derive.derive_portals()
    table = Table(title="Portals", show_header=True, header_style="bold cyan")
    table.add_column("ID", style="bold")
    table.add_column("Tag")
    table.add_column("UUID")
    table.add_column("Email")
    table.add_column("ShortId")
    table.add_column("Users")
    for row in rows:
        table.add_row(row.id, row.tag, row.uuid, row.email, row.short_id, ", ".join(row.users))
    app.console.print(table)


def _print_nodes(app: HexRiftApp) -> None:
    rows = app.derive.derive_nodes()
    table = Table(title="Nodes", show_header=True, header_style="bold cyan")
    table.add_column("ID", style="bold")
    table.add_column("Region")
    table.add_column("Type")
    table.add_column("ShortId / Hub-Exit UUIDs")
    for row in rows:
        if row.type == RegionType.EXIT:
            uuid_lines = [f"{hub_id}: {uuid}" for hub_id, uuid in (row.hub_exit_uuids or {}).items()]
            detail = "\n".join([f"shortId: {row.short_id}", *uuid_lines])
        else:
            detail = f"hubShortId: {row.hub_short_id}"
        table.add_row(row.id, row.region, row.type, detail)
    app.console.print(table)
