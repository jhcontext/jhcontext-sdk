"""Client configuration."""

from pydantic import BaseModel


class ClientConfig(BaseModel):
    base_url: str = "http://localhost:8400"
    api_key: str | None = None
    tls_cert: str | None = None
    tls_key: str | None = None
    timeout: float = 30.0
