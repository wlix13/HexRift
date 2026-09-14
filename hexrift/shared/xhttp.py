"""XHTTP transport defaults shared across components."""

from __future__ import annotations

import json

from hexrift.constants import UplinkHttpMethod


XHTTP_EXTRA = {
    "scStreamUpServerSecs": "30-60",
    "xPaddingBytes": "80-1400",
    "noGRPCHeader": True,
    "scMaxEachPostBytes": "500000-1000000",
    "scMinPostsIntervalMs": "10-50",
    "scMaxBufferedPosts": 45,
}

XHTTP_EXTRA_CDN = {
    "noSSEHeader": True,
    "xPaddingMethod": "tokenish",
    "xPaddingObfsMode": True,
    "xPaddingPlacement": "header",
    "xPaddingHeader": "X-Request-Id",
    **XHTTP_EXTRA,
}

XMUX = {
    "maxConcurrency": "16-32",
    "maxConnections": 0,
    "cMaxReuseTimes": "10-100",
    "hMaxRequestTimes": "600-900",
    "hMaxReusableSecs": "1800-3000",
    "hKeepAlivePeriod": 0,
}


def make_xhttp_settings(host: str, path: str, mode: str = "auto", cdn: bool = False) -> dict:
    return {
        "host": host,
        "path": path,
        "mode": mode,
        "extra": dict(XHTTP_EXTRA_CDN if cdn else XHTTP_EXTRA),
        "xmux": dict(XMUX),
    }


def make_xhttp_share_params(host: str, path: str, mode: str = "auto", cdn: bool = False) -> dict[str, str]:
    extra = XHTTP_EXTRA
    if cdn:  # client-only knob
        extra = {
            **XHTTP_EXTRA_CDN,
            "uplinkHTTPMethod": UplinkHttpMethod.PATCH,
        }
    return {
        "type": "xhttp",
        "host": host,
        "path": path,
        "mode": mode,
        "extra": json.dumps(extra, separators=(",", ":")),
    }
