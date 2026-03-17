"""HexRift error classes."""

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError as PydanticValidationError
from rich.markup import escape


class Error(Exception):
    """Base error for HexRift. Uses rich markup for terminal display."""

    def __init__(self, message: str) -> None:
        super().__init__(f"[red]{message}[/red]")


class SchemaValidationError(Error):
    """YAML schema failed pydantic validation."""

    def __init__(self, path: Path, exc: PydanticValidationError) -> None:
        lines = [f"[bold]Schema validation failed[/bold] ({escape(str(path))}):"]
        for err in exc.errors():
            loc = ".".join(str(p) for p in err["loc"])
            lines.append(f"  [yellow]{escape(loc)}[/yellow]: {escape(err['msg'])}")
        super().__init__("\n".join(lines))


class KeysError(Error):
    """Missing or corrupt key material."""


class DeriveError(Error):
    """Derivation or lookup failed (unknown user, guest, node, etc.)."""


class NodeError(Error):
    """"""


class RegionError(Error):
    """"""


class RenderError(Error):
    """Config rendering failed."""
