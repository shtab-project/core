from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SHTAB_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://shtab:shtab@localhost:5432/shtab"
    redis_url: str = "redis://localhost:6379/0"

    # Корень заметок: shared/ — общее пространство, users/<username>/ — личные.
    notes_root: Path = Path("../data/notes")

    # Пока нет Authentik: запросы без заголовка X-Authentik-Username идут от этого пользователя.
    # В проде обязательно dev_mode=false.
    dev_mode: bool = True
    dev_user: str = "admin"

    # Хосты, с которых разрешено обращаться к MCP (защита от DNS rebinding).
    # "host:*" в MCP SDK требует явный порт, поэтому голый хост указываем отдельно.
    mcp_allowed_hosts: list[str] = [
        "localhost",
        "localhost:*",
        "127.0.0.1:*",
        "api.shtab.localhost",
        "api.shtab.localhost:*",
    ]


settings = Settings()
