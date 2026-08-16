from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    api_port: int = 8000
    build_target: str = "development"
    secret_key: str = "mysecretkey"
    postgres_user: str = "myuser"
    postgres_password: str = "mypassword"
    postgres_db: str = "mydb"
    postgres_host: str = "localhost"

settings = Settings()