from pydantic import BaseModel, ConfigDict, Field

from hexrift.components.schema.models.fields import (
    CidrSubnet,
    DnsName,
    Duration,
    Identifier,
    NonBlankList,
    Port,
    Rtt,
    XrayPath,
)
from hexrift.components.schema.models.observability import ObservabilityOverride
from hexrift.components.schema.models.routing import ExitRoute
from hexrift.components.schema.models.shared import RealityConfig
from hexrift.constants import AuthMethod, HandshakeMethod, LbRole, LbStrategy, RegionType, TlsFingerprint


class NodeKeysOverride(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool | None = None
    mode: str | None = None
    session_time: Duration | None = None
    auth: AuthMethod | None = None
    padding: str | None = None


class NodeExitConnectionsOverride(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: HandshakeMethod | None = None
    fingerprint: TlsFingerprint | None = None


class RegionRouting(BaseModel):
    model_config = ConfigDict(extra="forbid")

    warp_extra: list[str] | None = None
    routes: list[ExitRoute] | None = None


class LeastLoadSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    baselines: list[Rtt] = ["30ms", "100ms", "250ms"]
    expected: int = Field(default=1, ge=1)
    max_rtt: Rtt = "750ms"
    tolerance: float = Field(default=0.5, ge=0.0, le=1.0)

    @property
    def xray_settings(self) -> dict:
        return {
            "baselines": self.baselines,
            "expected": self.expected,
            "maxRTT": self.max_rtt,
            "tolerance": self.tolerance,
        }


class WarpConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vless_route: int = Field(ge=0, le=65535)


class XdnsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    domains: NonBlankList
    port: Port = 53


class WireguardConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    port: Port = 443
    mtu: int = Field(default=1420, ge=576, le=65535)
    subnet: CidrSubnet  # peer address pool, e.g. "10.0.0.0/24"; server holds .1, peers from .2
    keepalive: int = Field(default=0, ge=0)
    kernel_mode: bool = False


class NodeWireguardOverride(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool | None = None
    port: Port | None = None
    mtu: int | None = Field(default=None, ge=576, le=65535)
    subnet: CidrSubnet | None = None
    keepalive: int | None = Field(default=None, ge=0)
    kernel_mode: bool | None = None


class Node(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: Identifier
    hostname: DnsName
    ipv6: bool | None = None
    haproxy: bool | None = None
    lb_role: LbRole | None = None
    reality: RealityConfig | None = None
    keys: NodeKeysOverride | None = None
    exit_connections: NodeExitConnectionsOverride | None = None
    proxy_inbound: bool | None = None
    xdns: XdnsConfig | None = None
    wireguard: NodeWireguardOverride | None = None
    observability: ObservabilityOverride | None = None


class Region(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: Identifier
    type: RegionType
    vless_route: int | None = Field(default=None, ge=0, le=65535)
    cdn_xhttp_path: XrayPath | None = None
    lb_strategy: LbStrategy | None = None
    lb_fallback: str | None = None
    lb_least_load: LeastLoadSettings | None = None
    routing: RegionRouting | None = None
    warp: WarpConfig | None = None
    nodes: list[Node]
