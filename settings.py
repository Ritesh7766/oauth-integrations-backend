import base64

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    client_id: str
    client_secret: str
    auth_url: str
    redirect_uri: str

    @property
    def encoded_client_id_secret(self) -> str:
        return base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()


class AppSettings(BaseSettings):
    redis_url: str

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class NotionSettings(Settings):
    model_config = SettingsConfigDict(
        env_prefix="NOTION_",
        env_file=".env",
        extra="ignore",
    )


class AirtableSettings(Settings):
    model_config = SettingsConfigDict(
        env_prefix="AIRTABLE_",
        env_file=".env",
        extra="ignore",
    )


app_settings = AppSettings()
notion_settings = NotionSettings()
airtable_settings = AirtableSettings()
