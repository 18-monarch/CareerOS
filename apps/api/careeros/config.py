from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./careeros.db"
    environment: str = "development"
    frontend_origin: str = "http://localhost:3000"
    cookie_secure: bool = False
    registration_enabled: bool = True
    allowed_feed_hosts: str = ""
    resend_api_key: str = ""
    email_from: str = ""
    ai_base_url: str = "https://api.openai.com/v1"
    ai_api_key: str = ""
    ai_model: str = ""
    auto_discovery_enabled: bool = True
    external_discovery_enabled: bool = False
    discovery_worker_interval_minutes: int = Field(default=60, ge=1, le=1440)
    auto_migrate_local: bool = True
    brave_search_api_key: str = ""
    research_query_limit: int = Field(default=4, ge=1, le=12)
    research_result_limit: int = Field(default=12, ge=1, le=50)
    discovery_interval_hours: int = Field(default=6, ge=1, le=168)

    @model_validator(mode="after")
    def production_safety(self):
        if self.environment == "production":
            if not self.cookie_secure or not self.frontend_origin.startswith("https://"):
                raise ValueError(
                    "Production requires COOKIE_SECURE=true and an HTTPS frontend origin"
                )
            if not self.database_url.startswith(("postgresql", "postgres://")):
                raise ValueError("Production requires PostgreSQL")
        return self


@lru_cache
def get_settings():
    return Settings()
