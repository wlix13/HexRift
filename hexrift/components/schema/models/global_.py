from pydantic import BaseModel, ConfigDict


class CdnConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exit_domain: str
    hub_domain: str


class GlobalConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    namespace: str
    aphelion_domain: str
    bridge_domain: str
    cdn: CdnConfig | None = None
