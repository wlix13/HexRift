from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, cast

import rich_click as click

from hexrift.components.keys.controller import KeysController
from hexrift.core.component import BaseComponent
from hexrift.errors import KeysError
from hexrift.i18n import LazyString, _


if TYPE_CHECKING:
    from hexrift.app import HexRiftApp


class KeysComponent(BaseComponent["HexRiftApp", KeysController]):
    name = "keys"
    controller_class = KeysController
    expose_controller = True

    @classmethod
    def expose_cli(cls, base: click.Group) -> None:
        @base.command(
            "gen-keys",
            help=cast(str, LazyString("Generate x25519 Reality keypairs and decryption keys for node(s).")),
        )
        @click.argument("node_id", required=False, default="")
        @click.option(
            "--all",
            "all_nodes",
            is_flag=True,
            help=cast(str, LazyString("Generate keys for all nodes.")),
        )
        @click.option(
            "--force",
            is_flag=True,
            help=cast(str, LazyString("Overwrite existing key files.")),
        )
        @click.option(
            "--keys-dir",
            type=click.Path(path_type=Path),
            default=Path("keys"),
            show_default=True,
            help=cast(str, LazyString("Directory to store key files.")),
        )
        @click.pass_obj
        def gen_keys(app: HexRiftApp, node_id: str, all_nodes: bool, force: bool, keys_dir: Path) -> None:
            if all_nodes and node_id:
                raise click.UsageError(_("Provide either NODE_ID or --all, not both."))
            if not all_nodes and not node_id:
                raise click.UsageError(_("Provide NODE_ID or --all."))

            nodes_to_gen = app.schema.get_all_nodes() if all_nodes else [app.schema.get_node(node_id)]

            generated = skipped = errors = 0
            for _region, node in nodes_to_gen:
                try:
                    did_gen = app.keys.gen_keys(node.id, keys_dir, force=force)
                    if did_gen:
                        app.console.print(f"  [green]{_('generated')}[/green] {node.id}")
                        generated += 1
                    else:
                        app.console.print(_("  [dim]skipped[/dim]   {}  (use --force to overwrite)").format(node.id))
                        skipped += 1
                except KeysError as e:
                    app.console.print(f"  [red]{_('error')}[/red]     {node.id}: {e}")
                    errors += 1

            done_msg = _(
                "\n[bold]Done[/bold] — {generated} generated, {skipped} skipped, {errors} errors  ([dim]{keys_dir}/[/dim])"  # noqa: E501
            ).format(generated=generated, skipped=skipped, errors=errors, keys_dir=keys_dir)
            app.console.print(done_msg)
