import pydantic
from pydantic import BaseModel, Field

from hexrift.components.schema.models.shared import RealityConfig
from hexrift.constants import AuthMethod, LbRole, RegionType


class NodeKeysOverride(BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")

    enabled: bool | None = None
    mode: str | None = None
    session_time: str | None = None
    auth: AuthMethod | None = None
    padding: str | None = None


class NodeExitConnectionsOverride(BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")

    method: str | None = None
    fingerprint: str | None = None


class RegionRouting(BaseModel):
    warp_extra: list[str] | None = None


class LeastLoadSettings(BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")

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
    vless_route: int


class MtprotoConfig(BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")

    domain: str = Field(min_length=1)
    port: int = Field(default=1234, ge=1, le=65535)


class NodeMtprotoOverride(BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")

    enabled: bool | None = None
    domain: str | None = Field(default=None, min_length=1)
    port: int | None = Field(default=None, ge=1, le=65535)


class Node(BaseModel):
    id: str
    hostname: str
    ipv6: bool | None = None
    lb_role: LbRole | None = None
    reality: RealityConfig | None = None
    keys: NodeKeysOverride | None = None
    exit_connections: NodeExitConnectionsOverride | None = None
    proxy_inbound: bool | None = None
    mtproto: NodeMtprotoOverride | None = None


class Region(BaseModel):
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
