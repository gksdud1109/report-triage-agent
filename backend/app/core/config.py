from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_host: str = "0.0.0.0"
    app_port: int = 8000

    database_url: str = "postgresql+asyncpg://triage:triage@localhost:5432/triage"

    temporal_host: str = "localhost:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "report-triage"

    nats_url: str = "nats://localhost:4222"
    nats_stream: str = "report-triage"


@lru_cache
def get_settings() -> Settings:
    return Settings()
