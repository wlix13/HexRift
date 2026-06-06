import ipaddress

from pydantic import BaseModel, ConfigDict, Field, field_validator

from hexrift.components.schema.models.routing import ExitRoute
from hexrift.components.schema.models.shared import RealityConfig
from hexrift.constants import AuthMethod, LbRole, RegionType


def normalize_cidr_subnet(value: str) -> str:
    """Validate CIDR subnet and normalize to network base (``10.0.0.5/24`` -> ``10.0.0.0/24``)."""

    try:
        return str(ipaddress.ip_network(value, strict=False))
    except ValueError as exc:
        raise ValueError(f"invalid CIDR subnet {value!r}: {exc}") from exc


class NodeKeysOverride(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool | None = None
    mode: str | None = None
    session_time: str | None = None
    auth: AuthMethod | None = None
    padding: str | None = None


class NodeExitConnectionsOverride(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: str | None = None
    fingerprint: str | None = None


class RegionRouting(BaseModel):
    model_config = ConfigDict(extra="forbid")

    warp_extra: list[str] | None = None
    routes: list[ExitRoute] | None = None


class LeastLoadSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    baselines: list[str] = ["30ms", "100ms", "250ms"]
    expected: int = Field(default=1, ge=1)
    max_rtt: str = Field(default="750ms", pattern=r"^\d+(ms|s)$")
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

    vless_route: int


class MtprotoConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    domain: str = Field(min_length=1)
    port: int = Field(default=1234, ge=1, le=65535)


class XdnsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    domains: list[str]
    port: int = Field(default=53, ge=1, le=65535)


class NodeMtprotoOverride(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool | None = None
    domain: str | None = Field(default=None, min_length=1)
    port: int | None = Field(default=None, ge=1, le=65535)


class WireguardConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    port: int = Field(default=443, ge=1, le=65535)
    mtu: int = Field(default=1420, ge=576, le=65535)
    subnet: str  # peer address pool, e.g. "10.0.0.0/24"; server holds .1, peers from .2
    keepalive: int = Field(default=0, ge=0)
    kernel_mode: bool = False

    @field_validator("subnet")
    @classmethod
    def _validate_subnet(cls, v: str) -> str:
        return normalize_cidr_subnet(v)


class NodeWireguardOverride(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    mtu: int | None = Field(default=None, ge=576, le=65535)
    subnet: str | None = None
    keepalive: int | None = Field(default=None, ge=0)
    kernel_mode: bool | None = None

    @field_validator("subnet")
    @classmethod
    def _validate_subnet(cls, v: str | None) -> str | None:
        return normalize_cidr_subnet(v) if v is not None else None


class Node(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    hostname: str
    ipv6: bool | None = None
    lb_role: LbRole | None = None
    reality: RealityConfig | None = None
    keys: NodeKeysOverride | None = None
    exit_connections: NodeExitConnectionsOverride | None = None
    proxy_inbound: bool | None = None
    mtproto: NodeMtprotoOverride | None = None
    xdns: XdnsConfig | None = None
    wireguard: NodeWireguardOverride | None = None


class Region(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: RegionType
    vless_route: int | None = None
    cdn_xhttp_path: str | None = None
    lb_strategy: str | None = None
    lb_fallback: str | None = None
    lb_least_load: LeastLoadSettings | None = None
    routing: RegionRouting | None = None
    warp: WarpConfig | None = None
    nodes: list[Node]
