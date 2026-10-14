from functools import lru_cache

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str | None = None
    secret_key: SecretStr | None = None
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    @field_validator("database_url", mode="before")
    @classmethod
    def use_asyncpg_for_postgres(cls, value: str | None) -> str | None:
        if isinstance(value, str):
            if value.startswith("postgres://"):
                return "postgresql+asyncpg://" + value.removeprefix("postgres://")
            if value.startswith("postgresql://"):
                return "postgresql+asyncpg://" + value.removeprefix("postgresql://")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
