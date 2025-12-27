from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    redis_url: str

    model_config = SettingsConfigDict(env_file=".env")


class NotionSettings(BaseSettings):
    client_id: str
    client_secret: str
    auth_url: str

    model_config = SettingsConfigDict(
        env_prefix="NOTION_",
        env_file=".env",
    )


app_settings = AppSettings()
notion_settings = NotionSettings()
