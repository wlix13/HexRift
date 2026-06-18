from pydantic import BaseModel, ConfigDict, Field

from hexrift.components.schema.models.fields import Duration
from hexrift.components.schema.models.regions import WireguardConfig, XdnsConfig
from hexrift.components.schema.models.shared import RealityConfig
from hexrift.constants import AuthMethod, HandshakeMethod, TlsFingerprint


class ObservatoryConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sampling: int = Field(default=8, ge=1, le=24)
    interval: Duration = "15s"
    timeout: Duration = "5s"
    concurrency: bool = True


class KeysConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    mode: str
    session_time: Duration
    auth: AuthMethod = AuthMethod.MLKEM768
    padding: str | None = None


class ExitConnectionsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: HandshakeMethod
    fingerprint: TlsFingerprint = TlsFingerprint.EDGE


class ExitDefaults(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ipv6: bool
    haproxy: bool = True
    keys: KeysConfig


class HubDefaults(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proxy_inbound: bool = False
    ipv6: bool
    haproxy: bool = True
    keys: KeysConfig
    exit_connections: ExitConnectionsConfig
    reality: RealityConfig
    xdns: XdnsConfig | None = None
    wireguard: WireguardConfig | None = None
    observatory: ObservatoryConfig = Field(default_factory=ObservatoryConfig)


class DefaultsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exit: ExitDefaults
    hub: HubDefaults
