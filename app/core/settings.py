from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App
    api_port: int = 8000
    build_target: str = "development"

    # Auth
    secret_key: str = "mysecretkey"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # PostgreSQL
    postgres_user: str = "myuser"
    postgres_password: str = "mypassword"
    postgres_db: str = "mydb"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    # MinIO
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "files"
    minio_secure: bool = False

    qdrant_url: str = "http://qdrant:6333"
    qdrant_service_api_key: str = "secret-key"

    embedding_model: str = "intfloat/multilingual-e5-large"

    redis_host: str = "redis"
    redis_port: int = 6379

    # Ollama
    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str = "gemma4:31b-cloud"
    ollama_temperature: float = 0.2


settings = Settings()