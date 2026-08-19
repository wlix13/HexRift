"""Hysteria fragment helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from hexrift.constants import (
    HYSTERIA_TRUNK_CONN_RECEIVE_WINDOW,
    HYSTERIA_TRUNK_KEEPALIVE_SECS,
    HYSTERIA_TRUNK_MAX_INCOMING_STREAMS,
    HYSTERIA_TRUNK_STREAM_RECEIVE_WINDOW,
    HysteriaCongestion,
)


HYSTERIA_TRUNK_LISTENER_QUIC: Final[Mapping[str, int]] = {
    "maxIncomingStreams": HYSTERIA_TRUNK_MAX_INCOMING_STREAMS,
    "maxStreamReceiveWindow": HYSTERIA_TRUNK_STREAM_RECEIVE_WINDOW,
    "maxConnectionReceiveWindow": HYSTERIA_TRUNK_CONN_RECEIVE_WINDOW,
}

HYSTERIA_TRUNK_DIALER_QUIC: Final[Mapping[str, int]] = {
    "keepAlivePeriod": HYSTERIA_TRUNK_KEEPALIVE_SECS,
    "maxStreamReceiveWindow": HYSTERIA_TRUNK_STREAM_RECEIVE_WINDOW,
    "maxConnectionReceiveWindow": HYSTERIA_TRUNK_CONN_RECEIVE_WINDOW,
}


def make_hysteria_finalmask(
    congestion: HysteriaCongestion,
    brutal_up: str | None,
    brutal_down: str | None,
    obfs_password: str | None,
    quic_tuning: Mapping[str, int] | None = None,
) -> dict:
    quic: dict = {"congestion": congestion}
    if brutal_up is not None:
        quic["brutalUp"] = brutal_up
    if brutal_down is not None:
        quic["brutalDown"] = brutal_down
    if quic_tuning:
        quic.update(quic_tuning)
    finalmask: dict = {"quicParams": quic}
    if obfs_password is not None:
        finalmask["udp"] = [{"type": "salamander", "settings": {"password": obfs_password}}]
    return finalmask


def pem_lines(pem: str) -> list[str]:
    """Split a PEM blob into Xray's inline line array."""

    return pem.strip().splitlines()
