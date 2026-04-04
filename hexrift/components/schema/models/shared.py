import pydantic
from pydantic import BaseModel, Field


class RealityFallbackLimits(BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")

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


class RealityConfig(BaseModel):
    dest: str
    server_names: list[str] | None = None
    xhttp_host: str | None = None
    xhttp_path: str
    fallback_limits: RealityFallbackLimits = Field(default_factory=RealityFallbackLimits)
