from pydantic_settings import BaseSettings, SettingsConfigDict
import base64


class AppSettings(BaseSettings):
    redis_url: str

    model_config = SettingsConfigDict(env_file=".env")


class NotionSettings(BaseSettings):
    client_id: str
    client_secret: str
    auth_url: str
    redirect_uri: str

    model_config = SettingsConfigDict(
        env_prefix="NOTION_",
        env_file=".env",
    )

    @property
    def encoded_client_id_secret(self) -> str:
        return base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()


app_settings = AppSettings()
notion_settings = NotionSettings()
