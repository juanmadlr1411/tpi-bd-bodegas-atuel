from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Configuración global de la aplicación cargada desde variables de entorno o archivo .env.
    """
    # Conexión a Base de Datos (Rol de operador sin privilegios de propietario)
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "bodegas_atuel"
    DB_USER: str = "operador_atuel"
    DB_PASSWORD: str = "operador_pass"
    DB_POOL_MIN_SIZE: int = 2
    DB_POOL_MAX_SIZE: int = 10

    # Configuración de servidor API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_ENV: str = "development"

    @property
    def conninfo(self) -> str:
        return (
            f"host={self.DB_HOST} "
            f"port={self.DB_PORT} "
            f"dbname={self.DB_NAME} "
            f"user={self.DB_USER} "
            f"password={self.DB_PASSWORD}"
        )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()

