from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "bodegas_atuel"
    DB_USER: str = "operador_atuel"
    DB_PASSWORD: str = "operador_pass"
    DB_SSLMODE: str = "prefer"
    DATABASE_URL: Optional[str] = None
    DB_POOL_MIN_SIZE: int = 1
    DB_POOL_MAX_SIZE: int = 10

    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_ENV: str = "development"
    CORS_ORIGINS: str = "*"

    @property
    def conninfo(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return (
            f"host={self.DB_HOST} "
            f"port={self.DB_PORT} "
            f"dbname={self.DB_NAME} "
            f"user={self.DB_USER} "
            f"password={self.DB_PASSWORD} "
            f"sslmode={self.DB_SSLMODE}"
        )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
