from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # ── App ──
    app_name: str = "SmartFactory-AD"
    debug: bool = False

    # ── Database ──
    database_url: str = "postgresql+asyncpg://sfadmin:sfadmin123@localhost:5432/smartfactory"

    # ── Redis ──
    redis_url: str = "redis://localhost:6379/0"

    # ── MinIO ──
    minio_endpoint: str = "localhost:9000"
    minio_root_user: str = "minioadmin"
    minio_root_password: str = "minioadmin123"
    minio_bucket: str = "smartfactory-images"
    minio_use_ssl: bool = False

    # ── Auth ──
    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    # ── VLM ──
    vlm_provider: str = "local"  # "local" | "openai"
    openai_api_key: str = ""

    # ── AD Engine ──
    ad_model: str = "patchcore"
    ad_device: str = "cpu"
    ad_checkpoint_path: str = ""  # path to trained .ckpt file

    # ── Alert ──
    alert_webhook_url: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
