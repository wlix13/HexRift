import ipaddress

from pydantic import BaseModel, ConfigDict, Field, field_validator

from hexrift.constants import DEFAULT_TRUSTED_HEADER, HTTP_HEADER_TOKEN_RE


class CdnConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exit_domain: str
    hub_domain: str
    trusted_forwarded_headers: list[str] = Field(default_factory=lambda: [DEFAULT_TRUSTED_HEADER])

    @field_validator("trusted_forwarded_headers")
    @classmethod
    def validate_trusted_forwarded_headers(cls, v: list[str]) -> list[str]:
        for header in v:
            if not HTTP_HEADER_TOKEN_RE.fullmatch(header):
                raise ValueError(
                    f"trusted_forwarded_headers entry must be an RFC-compliant HTTP header field-name, got: {header!r}"
                )
        return v


class DnsServerConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    address: str = "127.0.0.1"
    port: int = 53

    @field_validator("address")
    @classmethod
    def validate_ip_address(cls, v: str) -> str:
        try:
            ipaddress.ip_address(v)
        except ValueError as e:
            raise ValueError(f"dns address must be a valid IP address, got: {v!r}") from e
        return v


class GlobalConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    namespace: str
    aphelion_domain: str
    cdn: CdnConfig | None = None
    dns: DnsServerConfig = Field(default_factory=DnsServerConfig)
