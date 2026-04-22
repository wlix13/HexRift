"""Internationalization helpers for HexRift.

NOTE: Run `poe i18n` after changing any translatable string in this file
or any component file, then update the .po files accordingly.

Usage:
    from hexrift.i18n import _                    # runtime strings
    from hexrift.i18n import _, LazyString        # + Click decorator help strings
"""

from __future__ import annotations

import gettext
import locale
import os
from importlib.resources import files
from typing import TYPE_CHECKING, Any


_DOMAIN = "hexrift"
_current: gettext.NullTranslations = gettext.NullTranslations()


def setup_i18n() -> None:
    """Detect system locale and load the best available translation.

    Priority: HEXRIFT_LANG env var → system locale → English passthrough.
    Silently falls back to English if no .mo file is found for the locale.
    """
    global _current  # noqa: PLW0603

    lang = os.environ.get("HEXRIFT_LANG")
    if lang is None:
        try:
            lang, _ = locale.getlocale()
        except Exception:
            lang = None

    if not lang:
        return

    lang = lang.split(".")[0]

    try:
        locales_path = files("hexrift") / "locales"
        _current = gettext.translation(_DOMAIN, localedir=str(locales_path), languages=[lang])
        _patch_click(_current)
    except FileNotFoundError:
        pass


if TYPE_CHECKING:
    _LazyStringBase = str
else:
    _LazyStringBase = object


class LazyString(_LazyStringBase):
    """Deferred translation for strings evaluated at import time (Click decorators).

    Click reads help= arguments at decoration time, before i18n is set up.
    LazyString stores the source string and defers _() lookup until Click
    renders the help text at --help time.

        @click.option("--foo", help=LazyString("Some help text"))
    """

    __slots__ = ("_s",)

    def __init__(self, s: str) -> None:
        self._s = s

    def __str__(self) -> str:
        return _current.gettext(self._s)

    def __repr__(self) -> str:
        return f"LazyString({self._s!r})"

    def __eq__(self, other: Any) -> bool:
        return str(self) == other

    def __hash__(self) -> int:
        return hash(str(self))

    def __mod__(self, args: Any, /) -> str:  # type: ignore[override]  # ty: ignore[invalid-method-override]
        return str(self) % args

    def __format__(self, format_spec: str) -> str:
        return format(str(self), format_spec)

    def __getattr__(self, name: str) -> Any:
        # Delegate any unknown attribute (e.g. expandtabs, split, strip) to the
        # resolved string so LazyString is transparent to code that inspects it
        # as a regular str (e.g. rich_click calling inspect.cleandoc).
        return getattr(str(self), name)


def _(message: str) -> str:
    """Translate message using the current locale."""
    return _current.gettext(message)


def ngettext(singular: str, plural: str, n: int) -> str:
    """Translate with plural forms."""
    return _current.ngettext(singular, plural, n)


def _patch_click(t: gettext.NullTranslations) -> None:
    """Inject our catalog into Click's module-level gettext bindings."""

    import click.core
    import click.exceptions
    import click.types
    import rich_click.rich_click as rclick
    import rich_click.rich_help_rendering as rhr

    for mod in (click.core, click.exceptions, click.types):
        setattr(mod, "_", t.gettext)
    setattr(click.core, "ngettext", t.ngettext)
    setattr(click.exceptions, "ngettext", t.ngettext)

    try:
        rclick.ERRORS_PANEL_TITLE = t.gettext("Error")
        rclick.OPTIONS_PANEL_TITLE = t.gettext("Options")
        rclick.COMMANDS_PANEL_TITLE = t.gettext("Commands")
        rclick.ARGUMENTS_PANEL_TITLE = t.gettext("Arguments")

        # Intercept the call and pre-set errors_suggestion with the translated string.
        _orig_rich_format_error = rhr.rich_format_error

        def _patched_format_error(  # type: ignore[invalid-assignment]
            self: Any,
            formatter: Any,
            export_console_as: Any = None,
        ) -> None:
            config = formatter.config
            if config.errors_suggestion is None and getattr(self, "ctx", None) is not None:
                ctx = self.ctx
                if ctx.command.get_help_option(ctx) is not None:
                    config.errors_suggestion = t.gettext("Try '{command} {option}' for help.").format(
                        command=ctx.command_path, option=ctx.help_option_names[0]
                    )
            _orig_rich_format_error(self, formatter, export_console_as)

        setattr(rhr, "rich_format_error", _patched_format_error)
    except ImportError:
        pass


# Initialize at import time so LazyString instances resolve to the correct
# translation even though decorators evaluated before main() runs.
setup_i18n()

# ---------------------------------------------------------------------------
# Catalog stubs —  parsed by pybabel for extraction.
# Keeps Click's and rich_click's built-in user-facing strings in our .pot so
# they survive `poe i18n-update` and receive translations in the .po files.
# ---------------------------------------------------------------------------
if False:  # pragma: no cover
    # Click core
    _("No such command {name!r}.")
    _("Missing command.")
    _("Aborted!")
    _("Error: {message}")
    # Click exceptions
    _("Try '{command} {option}' for help.")
    _("Invalid value: {message}")
    _("Invalid value for {param_hint}: {message}")
    _("Missing argument")
    _("Missing option")
    _("Missing parameter")
    _("Missing {param_type}")
    _("Missing parameter: {param_name}")
    _("No such option: {name}")
    _("unknown error")
    _("Could not open file {filename!r}: {message}")
    ngettext("Did you mean {possibility}?", "(Possible options: {possibilities})", 2)
    ngettext(
        "Got unexpected extra argument ({args})",
        "Got unexpected extra arguments ({args})",
        2,
    )
    ngettext(
        "Takes {nargs} values but 1 was given.",
        "Takes {nargs} values but {len} were given.",
        2,
    )
    # rich_click panel titles
    _("Error")
    _("Options")
    _("Commands")
    _("Arguments")
