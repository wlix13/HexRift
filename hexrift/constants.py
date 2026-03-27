"""Centralized constants and enums for HexRift."""

from enum import StrEnum


class RegionType(StrEnum):
    EXIT = "exit"
    HUB = "hub"


class AccessType(StrEnum):
    """User access types (used in users[].access)."""

    XHTTP = "xhttp"
    SERVER = "server"
    CDN = "cdn"
    PROXY = "proxy"


class LbRole(StrEnum):
    """Load balancer node roles."""

    BACKUP = "backup"


class XrayProtocol(StrEnum):
    """Xray protocol identifiers."""

    VLESS = "vless"
    FREEDOM = "freedom"
    BLACKHOLE = "blackhole"
    MIXED = "mixed"


class XrayNetwork(StrEnum):
    """Xray network/transport types."""

    XHTTP = "xhttp"


class XraySecurity(StrEnum):
    """Xray security types."""

    NONE = "none"
    REALITY = "reality"
    TLS = "tls"


class SpecialDestination(StrEnum):
    """Special routing destinations (non-region, non-node)."""

    DIRECT = "direct"
    BLOCKED = "blocked"
    WARP = "warp"


SPECIAL_DESTINATIONS = {d.value for d in SpecialDestination}


class XtlsFlow(StrEnum):
    """Xray vless xtls flows."""

    RPRX_VISION = "xtls-rprx-vision"
    RPRX_VISION_UDP443 = "xtls-rprx-vision-udp443"


class TagPrefix(StrEnum):
    """Outbound tag prefixes."""

    NONE = ""
    BACKUP = "backup-"
    WARP = "warp-"
    LB = "lb-"
    LB_WARP = "lb-warp-"


class TagSuffix(StrEnum):
    """Outbound tag suffixes."""

    PORTAL = "-portal"


class UserSuffix(StrEnum):
    """User tag suffixes."""

    PORTAL = "-portal"
    SERVER = "-server"


class AuthMethod(StrEnum):
    """Encryption keys."""

    MLKEM768 = "mlkem768"
    X25519 = "x25519"


class HandshakeMethod(StrEnum):
    """Vless encryption handshake methods."""

    MLKEM768 = "mlkem768x25519plus"


class UplinkHttpMethod(StrEnum):
    PATCH = "PATCH"
    POST = "POST"


class Socket(StrEnum):
    """Unix socket paths shared between Xray and HAProxy."""

    VLESS_REALITY = "/dev/shm/xhttp_vless_reality.sock"  # noqa: S108
    VLESS_TLS = "/dev/shm/xhttp_vless_tls.sock"  # noqa: S108
    MIXED = "0.0.0.0"  # noqa: S104 mixed protocol doesn't support Unix sockets
    HAPROXY_CDN = "/dev/shm/haproxy_cdn_https_local.sock"  # noqa: S108


WARP_VLESS_ROUTE = 65535
"""Warp vless route decimal"""

WARP_UUID_SEGMENT = "ffff"
"""Warp vless route hex"""

SHORT_ID_LENGTH = 16
"""Derivation for shortId"""

VLESS_FLOW = XtlsFlow.RPRX_VISION
"""Main vless flow."""

HANDSHAKE_METHOD = HandshakeMethod.MLKEM768
"""Main handshake method"""
