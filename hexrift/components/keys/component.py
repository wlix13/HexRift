from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import rich_click as click

from hexrift.components.keys.controller import KeysController
from hexrift.core.component import BaseComponent
from hexrift.errors import KeysError


if TYPE_CHECKING:
    from hexrift.app import HexRiftApp


class KeysComponent(BaseComponent["HexRiftApp", KeysController]):
    name = "keys"
    controller_class = KeysController
    expose_controller = True

    @classmethod
    def expose_cli(cls, base: click.Group) -> None:
        @base.command("gen-keys")
        @click.argument("node_id", required=False, default="")
        @click.option(
            "--all",
            "all_nodes",
            is_flag=True,
            help="Generate keys for all nodes.",
        )
        @click.option(
            "--force",
            is_flag=True,
            help="Overwrite existing key files.",
        )
        @click.option(
            "--keys-dir",
            type=click.Path(path_type=Path),
            default=Path("keys"),
            show_default=True,
            help="Directory to store key files.",
        )
        @click.pass_obj
        def gen_keys(app: HexRiftApp, node_id: str, all_nodes: bool, force: bool, keys_dir: Path) -> None:
            """Generate x25519 Reality keypairs and decryption keys for node(s)."""

            if all_nodes and node_id:
                raise click.UsageError("Provide either NODE_ID or --all, not both.")
            if not all_nodes and not node_id:
                raise click.UsageError("Provide NODE_ID or --all.")

            nodes_to_gen = app.schema.get_all_nodes() if all_nodes else [app.schema.get_node(node_id)]

            generated = skipped = errors = 0
            for _region, node in nodes_to_gen:
                try:
                    did_gen = app.keys.gen_keys(node.id, keys_dir, force=force)
                    if did_gen:
                        app.console.print(f"  [green]generated[/green] {node.id}")
                        generated += 1
                    else:
                        app.console.print(f"  [dim]skipped[/dim]   {node.id}  (use --force to overwrite)")
                        skipped += 1
                except KeysError as e:
                    app.console.print(f"  [red]error[/red]     {node.id}: {e}")
                    errors += 1

            app.console.print(
                f"\n[bold]Done[/bold] — {generated} generated, {skipped} skipped, {errors} errors"
                f"  ([dim]{keys_dir}/[/dim])"
            )
