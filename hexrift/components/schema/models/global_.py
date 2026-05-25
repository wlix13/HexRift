from pydantic import BaseModel, ConfigDict, Field

from hexrift.constants import DEFAULT_TRUSTED_HEADER


class CdnConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exit_domain: str
    hub_domain: str
    trusted_forwarded_headers: list[str] = Field(default_factory=lambda: [DEFAULT_TRUSTED_HEADER])


class DnsServerConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    address: str = "127.0.0.1"
    port: int = 53


class GlobalConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    namespace: str
    aphelion_domain: str
    cdn: CdnConfig | None = None
    dns: DnsServerConfig = Field(default_factory=DnsServerConfig)
