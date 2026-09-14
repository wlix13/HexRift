from pydantic import BaseModel, ConfigDict, Field

from hexrift.components.schema.models.fields import DnsName, HostPort, NonBlankList, XrayPath


class RealityFallbackLimits(BaseModel):
    model_config = ConfigDict(extra="forbid")

    after_bytes: int = 16_384
    bytes_per_sec: int = 50_000
    burst_bytes_per_sec: int = 100_000

    @property
    def xray_settings(self) -> dict[str, int]:
        return {
            "afterBytes": self.after_bytes,
            "bytesPerSec": self.bytes_per_sec,
            "burstBytesPerSec": self.burst_bytes_per_sec,
        }


class XhttpConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: XrayPath
    host: DnsName | None = None  # Host header, defaults to reality dest host or node hostname under TLS


class XhttpOverride(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: XrayPath | None = None
    host: DnsName | None = None


class RealityConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dest: HostPort
    server_names: NonBlankList | None = Field(default=None, min_length=1)
    fallback_limits: RealityFallbackLimits = Field(default_factory=RealityFallbackLimits)
