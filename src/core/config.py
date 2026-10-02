import secrets
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    telegram_token: str = Field(default="", validation_alias="BOT_TOKEN")
    google_token: str = Field(default="", validation_alias="GOOGLE_API_KEY")
    database_url: str = Field(
        default="postgresql+asyncpg://bujet_user:secure_db_pass@localhost/smart_bujet",
        validation_alias="DATABASE_URL"
    )
    domain: str = Field(default="localhost", validation_alias="WEBHOOK_DOMAIN")
    webhook_secret: str = Field(default_factory=lambda: secrets.token_urlsafe(32), validation_alias="WEBHOOK_SECRET")
    gemini_model: str = Field(default="gemini-3.8-flash", validation_alias="GEMINI_MODEL")
    bot_username: str = Field(default="smartbujetbot", validation_alias="BOT_USERNAME")

    @property
    def bot_token(self) -> str:
        return self.telegram_token

    @property
    def google_api_key(self) -> str:
        return self.google_token

    @property
    def BOT_TOKEN(self) -> str:
        return self.telegram_token

    @property
    def GOOGLE_API_KEY(self) -> str:
        return self.google_token

    @property
    def DATABASE_URL(self) -> str:
        return self.database_url

    @property
    def WEBHOOK_DOMAIN(self) -> str:
        return self.domain

    @property
    def WEBHOOK_SECRET(self) -> str:
        return self.webhook_secret

    @property
    def webhook_url(self) -> str:
        return f"https://{self.domain}/api/v1/webhook"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )


settings = Settings()

