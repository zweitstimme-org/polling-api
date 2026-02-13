"""Core configuration module."""

from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings

# Project root directory (src-layout: src/pollingapi/core -> project root)
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_ROOT / "data"

# Ensure data directory exists
DATA_DIR.mkdir(exist_ok=True)


class Settings(BaseSettings):
    """Application settings."""

    # API Configuration
    api_title: str = "Zweitstimme Polling API"
    api_version: str = "1.0.0"
    api_description: str = "German election polling data API"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = False

    # Database Configuration
    database_url: str = f"sqlite:///{DATA_DIR}/polling.db"
    async_database_url: str = f"sqlite+aiosqlite:///{DATA_DIR}/polling.db"

    # Security
    api_secret: str = "your-secret-key-change-in-production"
    github_token: str | None = None
    github_repo: str = "zweitstimme/data"

    # Scraping Configuration
    scraper_delay: float = 1.0  # Seconds between requests
    scraper_timeout: int = 30  # Request timeout

    # Data Paths
    data_dir: Path = DATA_DIR
    export_dir: Path = DATA_DIR / "export"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()

# Ensure export directory exists
settings.export_dir.mkdir(exist_ok=True)


__all__ = ["settings", "PROJECT_ROOT", "DATA_DIR"]
