from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    notion_client_id: str
    notion_client_secret: str
    notion_auth_url: str
    redis_url: str

    class Config:
        env_file = ".env"


settings = Settings()
