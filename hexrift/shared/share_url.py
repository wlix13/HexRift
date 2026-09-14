from __future__ import annotations

from collections.abc import Mapping
from urllib.parse import quote, urlencode
from uuid import UUID


def vless_share_url(identity_uuid: UUID, host: str, params: Mapping[str, str], fragment: str) -> str:
    """vless:// URL from ordered query params, values percent-encoded."""

    return f"vless://{identity_uuid}@{host}:443?{urlencode(params, quote_via=quote)}#{quote(fragment, safe='')}"
