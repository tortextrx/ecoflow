from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    app_name: str = "ecoFlow"
    app_version: str = "0.1.0"
    debug: bool = False
    host: str = "127.0.0.1"
    port: int = 18080
    database_url: str = "postgresql+asyncpg://ecoflow_user:password@localhost/ecoflow_db"
    ecosoft_base_url: str = "https://www.ecosoftapi.net"
    ecosoft_token_auth: str = ""
    ecosoft_token_usuario: str = ""
    ecosoft_default_sucursal: int = 1
    ecosoft_default_gasto_articulo_ref: str = "GASTO_GENERICO"
    openrouter_api_key: str = ""
    openai_api_key: str = ""
    media_base_path: str = "/var/ecoflow/media"
    log_path: str = "/var/log/ecoflow/app.jsonl"
    job_max_attempts: int = 3
    job_stale_minutes: int = 5
    auto_approve_max_amount: float = 0.0
    model_config: dict = {"env_file": ".env", "env_file_encoding": "utf-8"}

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
