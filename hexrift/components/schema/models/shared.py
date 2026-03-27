from pydantic import BaseModel


class RealityConfig(BaseModel):
    dest: str
    server_names: list[str] | None = None
    xhttp_host: str | None = None
    xhttp_path: str
