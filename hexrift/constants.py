"""Centralized constants and enums for HexRift."""

import re
from enum import StrEnum


HTTP_HEADER_TOKEN_RE = re.compile(r"[!#$%&'*+\-.^_`|~0-9A-Za-z]+")
"""RFC 9110 token (field-name) syntax: tchar+."""

DURATION_PATTERN = r"^\d+(ms|s|m|h)$"
"""Duration string: integer + ms/s/m/h unit (e.g. `15s`, `600s`)."""

RTT_PATTERN = r"^\d+(ms|s)$"
"""Round-trip-time string: integer + ms/s unit (e.g. `750ms`)."""

IDENTIFIER_PATTERN = r"^[A-Za-z0-9_-]+$"
"""Safe identifier charset for ids, usernames, labels, guests."""

DNS_NAME_PATTERN = r"^[A-Za-z0-9_.-]+$"
"""DNS-name charset for namespace, hostnames, and domains."""

HOST_PORT_PATTERN = r"^(\[[0-9A-Fa-f:.]+\]|[A-Za-z0-9_.-]+):\d{1,5}$"
"""`host:port` shape: DNS name or IPv4 literal, or a bracketed IPv6 literal."""

SHORT_ID_PATTERN = r"^[0-9a-fA-F]*$"
"""Reality shortId: hex digits only."""


class RegionType(StrEnum):
    EXIT = "exit"
    HUB = "hub"


class AccessType(StrEnum):
    """User access types (used in users[].access)."""

    XHTTP = "xhttp"
    SERVER = "server"
    CDN = "cdn"
    PROXY = "proxy"
    WIREGUARD = "wireguard"
    XDNS = "xdns"


ROUTABLE_ACCESS = frozenset(
    {
        AccessType.XHTTP,
        AccessType.CDN,
        AccessType.XDNS,
        AccessType.WIREGUARD,
    }
)
"""Access types whose inbound identity carries `user_email` for routing rules to match on."""


class LbRole(StrEnum):
    """Load balancer node roles."""

    BACKUP = "backup"


class LbStrategy(StrEnum):
    """Load balancer selection strategies."""

    RANDOM = "random"
    ROUND_ROBIN = "roundRobin"
    LEAST_PING = "leastPing"
    LEAST_LOAD = "leastLoad"


class TlsFingerprint(StrEnum):
    """uTLS client fingerprints."""

    CHROME = "chrome"
    FIREFOX = "firefox"
    SAFARI = "safari"
    IOS = "ios"
    ANDROID = "android"
    EDGE = "edge"
    FP_360 = "360"
    QQ = "qq"
    RANDOM = "random"
    RANDOMIZED = "randomized"


class XrayProtocol(StrEnum):
    """Xray protocol identifiers."""

    VLESS = "vless"
    FREEDOM = "freedom"
    BLACKHOLE = "blackhole"
    MIXED = "mixed"
    WIREGUARD = "wireguard"
    DOKODEMO = "dokodemo-door"


class XrayNetwork(StrEnum):
    """Xray network/transport types."""

    XHTTP = "xhttp"
    MKCP = "mkcp"


class Transport(StrEnum):
    """Layer-4 transport a listener occupies."""

    TCP = "tcp"
    UDP = "udp"


class PublishNetwork(StrEnum):
    """Transports a published portal port forwards."""

    TCP = "tcp"
    UDP = "udp"
    TCP_UDP = "tcp,udp"

    @property
    def transports(self) -> frozenset[Transport]:
        """Individual transports this network occupies."""

        return frozenset(Transport(part) for part in self.split(","))


class XraySecurity(StrEnum):
    """Xray security types."""

    NONE = "none"
    REALITY = "reality"
    TLS = "tls"


class DomainStrategy(StrEnum):
    """Routing domainStrategy: when router resolves domain destination to match `ip` rules."""

    AS_IS = "AsIs"
    IP_IF_NON_MATCH = "IPIfNonMatch"
    IP_ON_DEMAND = "IPOnDemand"


class LogLevel(StrEnum):
    """Xray log verbosity levels."""

    NONE = "none"
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


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
    PUBLISH = "-publish"


class UserSuffix(StrEnum):
    """User tag suffixes."""

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


REALITY_INBOUND_PORT = 443
"""Port the Reality inbound binds, directly or behind HAProxy."""

PROXY_INBOUND_PORT = 80
"""Port the mixed proxy inbound binds."""

WARP_VLESS_ROUTE = 65535
"""Warp vless route decimal"""

WARP_UUID_SEGMENT = "ffff"
"""Warp vless route hex"""

SHORT_ID_LENGTH = 16
"""Derivation for shortId"""

VLESS_FLOW = XtlsFlow.RPRX_VISION
"""Inbound client flow."""

VLESS_CLIENT_FLOW = XtlsFlow.RPRX_VISION_UDP443
"""Outbound client flow."""

HANDSHAKE_METHOD = HandshakeMethod.MLKEM768
"""Main handshake method"""

DEFAULT_TRUSTED_HEADER = "X-Real-IP"
"""Default header name used by HAProxy to forward the real client IP."""

WIREGUARD_CLIENT_DNS = "1.1.1.1"
"""IPv4 DNS resolver placed in generated WireGuard client configs."""
