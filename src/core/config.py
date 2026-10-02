import secrets
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    telegram_token: str
    google_token: str
    database_url: str
    domain: str
    webhook_secret: str = secrets.token_urlsafe(32)

    @property
    def webhook_url(self) -> str:
        return f"https://{self.domain}/webhook"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
