from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, IPvAnyAddress

from hexrift.components.schema.models.fields import Port
from hexrift.constants import LogLevel


class MetricsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", use_attribute_docstrings=True)

    enabled: bool = False
    listen: IPvAnyAddress = Field(default="127.0.0.1", validate_default=True)
    """Address Xray's API listener binds to.

    Parsed to an IPv4Address/IPv6Address so code always holds a typed value;
    YAML supplies a plain string, which pydantic coerces.
    """
    port: Port = 10085
    user_stats: bool = True
    """Per-user traffic counters."""
    online: bool = True
    """Per-user online tracking (statsUserOnline)."""

    if TYPE_CHECKING:
        # Widen the generated __init__ so callers may pass a str for `listen`
        # (pydantic coerces it). Keep in sync with the fields above.
        def __init__(
            self,
            *,
            enabled: bool = False,
            listen: IPvAnyAddress | str = "127.0.0.1",
            port: int = 10085,
            user_stats: bool = True,
            online: bool = True,
        ) -> None: ...


class LoggingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    loglevel: LogLevel = LogLevel.NONE
    access: str = "none"
    error: str = "none"
    dns_log: bool = False


class ObservabilityConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metrics: MetricsConfig = Field(default_factory=MetricsConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


class MetricsOverride(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool | None = None
    listen: IPvAnyAddress | None = None
    port: Port | None = None
    user_stats: bool | None = None
    online: bool | None = None

    if TYPE_CHECKING:
        # Widen the generated __init__ so callers may pass a str for `listen`.
        def __init__(
            self,
            *,
            enabled: bool | None = None,
            listen: IPvAnyAddress | str | None = None,
            port: int | None = None,
            user_stats: bool | None = None,
            online: bool | None = None,
        ) -> None: ...


class LoggingOverride(BaseModel):
    model_config = ConfigDict(extra="forbid")

    loglevel: LogLevel | None = None
    access: str | None = None
    error: str | None = None
    dns_log: bool | None = None


class ObservabilityOverride(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metrics: MetricsOverride | None = None
    logging: LoggingOverride | None = None
