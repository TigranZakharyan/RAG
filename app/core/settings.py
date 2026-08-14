from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    api_port: int = 8000
    build_target: str = "development"

settings = Settings()