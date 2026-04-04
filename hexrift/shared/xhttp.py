"""XHTTP transport defaults shared across components."""

from __future__ import annotations


XHTTP_EXTRA = {
    "scStreamUpServerSecs": "30-60",
    "xPaddingBytes": "80-1400",
    "noGRPCHeader": True,
    "scMaxEachPostBytes": "500000-1000000",
    "scMinPostsIntervalMs": "10-50",
    "scMaxBufferedPosts": 45,
}

XMUX = {
    "maxConcurrency": "16-32",
    "maxConnections": 0,
    "cMaxReuseTimes": "10-100",
    "hMaxRequestTimes": "600-900",
    "hMaxReusableSecs": "1800-3000",
    "hKeepAlivePeriod": 0,
}
