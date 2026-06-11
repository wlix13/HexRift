from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class RealityConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dest: str
    server_names: list[str] | None = Field(default=None, min_length=1)
    xhttp_host: str | None = None
    xhttp_path: str
    fallback_limits: RealityFallbackLimits = Field(default_factory=RealityFallbackLimits)

    @field_validator("server_names")
    @classmethod
    def validate_server_names(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        stripped = [name.strip() for name in v]
        if any(not name for name in stripped):
            raise ValueError("server_names entries must be non-empty")
        return stripped
