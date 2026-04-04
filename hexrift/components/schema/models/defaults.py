import pydantic
from pydantic import BaseModel, Field

from hexrift.components.schema.models.regions import MtprotoConfig
from hexrift.components.schema.models.shared import RealityConfig
from hexrift.constants import AuthMethod


class ObservatoryConfig(BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")

    sampling: int = Field(default=8, ge=1, le=24)
    interval: str = Field(default="15s", pattern=r"^\d+(ms|s|m|h)$")
    timeout: str = Field(default="5s", pattern=r"^\d+(ms|s|m|h)$")
    concurrency: bool = True


class KeysConfig(BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")

    enabled: bool = True
    mode: str
    session_time: str
    auth: AuthMethod = AuthMethod.MLKEM768
    padding: str | None = None


class ExitConnectionsConfig(BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")

    method: str
    fingerprint: str = "edge"


class ExitDefaults(BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")

    ipv6: bool
    keys: KeysConfig


class HubDefaults(BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")

    proxy_inbound: bool = False
    ipv6: bool
    keys: KeysConfig
    exit_connections: ExitConnectionsConfig
    reality: RealityConfig
    mtproto: MtprotoConfig | None = None
    observatory: ObservatoryConfig = Field(default_factory=ObservatoryConfig)


class DefaultsConfig(BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")

    exit: ExitDefaults
    hub: HubDefaults
