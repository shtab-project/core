from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SHTAB_", extra="ignore")

    database_url: str = "postgresql+asyncpg://shtab:shtab@localhost:5432/shtab"
    redis_url: str = "redis://localhost:6379/0"

    # Shtab URL as the browser sees it (no trailing /)
    public_url: str = "http://shtab.localhost"
    github_url: str = "https://github.com/shtab-project/"

    # Extra origins allowed to call MCP, besides public_url (which is always allowed).
    # From env as JSON: SHTAB_MCP_ALLOWED_URLS='["https://app.example.com"]'
    mcp_allowed_urls: list[str] = []

    # The "Shtab" OIDC app in Authentik (created by a blueprint)
    auth_url: str = "http://auth.shtab.localhost"
    auth_internal_url: str | None = None
    oidc_client_id: str = "shtab"
    oidc_client_secret: str = ""

    # Signs the OIDC login cookie (state/nonce)
    secret_key: str = "my-secret-key"
    session_ttl_seconds: int = 7 * 24 * 3600

    @property
    def oidc_issuer(self) -> str:
        return f"{self.auth_url}/application/o/{self.oidc_client_id}/"

    @property
    def secure_cookies(self) -> bool:
        return self.public_url.startswith("https://")

    @property
    def mcp_origins(self) -> list[str]:
        """Origins MCP accepts: public_url first, then the extra ones, no duplicates."""
        urls = (self.public_url, *self.mcp_allowed_urls)
        return list(dict.fromkeys(url.rstrip("/") for url in urls))

    @property
    def mcp_hosts(self) -> list[str]:
        """Host[:port] of every MCP origin, for the Host header check."""
        return [urlsplit(url).netloc for url in self.mcp_origins]


settings = Settings()  # type: ignore


@dataclass(frozen=True)
class Paths:
    """Core paths that don't depend on the working directory."""

    workspace: Path = Path(__file__).resolve().parents[3]

    @property
    def plugins(self) -> Path:
        return self.workspace / "core" / "plugins"


paths = Paths()
