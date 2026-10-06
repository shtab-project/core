from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SHTAB_", extra="ignore")

    database_url: str = "postgresql+asyncpg://shtab:shtab@localhost:5432/shtab"
    redis_url: str = "redis://localhost:6379/0"

    # Адрес Shtab, как его видит браузер (без завершающего /)
    public_url: str = "http://shtab.localhost"

    # OIDC-приложение «Shtab» в Authentik (создаётся blueprint'ом)
    auth_url: str = "http://auth.shtab.localhost"
    oidc_client_id: str = "shtab"
    oidc_client_secret: str = ""

    # Подпись служебной cookie входа (state/nonce OIDC)
    secret_key: str
    session_ttl_seconds: int = 7 * 24 * 3600

    @property
    def oidc_issuer(self) -> str:
        return f"{self.auth_url}/application/o/{self.oidc_client_id}/"

    @property
    def secure_cookies(self) -> bool:
        return self.public_url.startswith("https://")


settings = Settings()
