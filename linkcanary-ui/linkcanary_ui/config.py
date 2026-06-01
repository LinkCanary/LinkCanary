"""Application configuration."""

import os
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""
    
    app_name: str = "LinkCanary UI"
    debug: bool = False
    
    host: str = "127.0.0.1"
    port: int = 3000
    
    data_dir: Path = Path.home() / ".linkcanary"
    database_url: Optional[str] = None
    
    use_celery: bool = False
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"

    # Report storage: "local" (filesystem) or "s3" (S3 / Cloudflare R2)
    storage_backend: str = "local"
    s3_bucket: Optional[str] = None
    s3_endpoint_url: Optional[str] = None
    s3_region: str = "auto"
    s3_access_key_id: Optional[str] = None
    s3_secret_access_key: Optional[str] = None
    s3_prefix: str = "crawls/"
    
    report_retention_days: int = 90
    max_storage_mb: int = 1000
    
    default_delay: float = 0.5
    default_timeout: int = 10
    default_skip_ok: bool = True
    default_internal_only: bool = False

    webhook_enabled: bool = True
    webhook_timeout: int = 10
    webhook_retry_count: int = 3
    
    class Config:
        env_prefix = "LINKCANARY_"
        env_file = ".env"
    
    @property
    def db_url(self) -> str:
        if self.database_url:
            return self.database_url
        db_path = self.data_dir / "linkcanary.db"
        return f"sqlite+aiosqlite:///{db_path}"

    @property
    def sync_db_url(self) -> str:
        """Synchronous driver URL for the Celery worker / Alembic."""
        url = self.db_url
        if "+aiosqlite" in url:
            return url.replace("+aiosqlite", "")
        if "+asyncpg" in url:
            return url.replace("+asyncpg", "+psycopg")
        return url
    
    @property
    def crawls_dir(self) -> Path:
        return self.data_dir / "crawls"
    
    def ensure_dirs(self) -> None:
        """Ensure data directories exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.crawls_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
