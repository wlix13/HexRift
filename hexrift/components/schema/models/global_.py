from pydantic import BaseModel


class CdnConfig(BaseModel):
    exit_domain: str
    hub_domain: str


class GlobalConfig(BaseModel):
    namespace: str
    aphelion_domain: str
    bridge_domain: str
    cdn: CdnConfig | None = None
