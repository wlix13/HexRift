"""Jinja environment factory for bundled config templates."""

from __future__ import annotations

import functools

from jinja2 import Environment, PackageLoader


@functools.cache
def jinja_env(subdir: str) -> Environment:
    """Return cached Jinja environment for `hexrift/templates/<subdir>`."""

    return Environment(
        loader=PackageLoader("hexrift", f"templates/{subdir}"),
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
        autoescape=False,  # noqa: S701
    )
