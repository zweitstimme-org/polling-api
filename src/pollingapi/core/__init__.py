"""Core configuration module."""

from pathlib import Path

from pydantic_settings import BaseSettings

# Project root directory (src-layout: src/pollingapi/core -> project root)
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_ROOT / "data"
API_VERSION_FILE = PROJECT_ROOT / ".apiversion"


def _load_api_version() -> str:
    """Load API version from .apiversion file."""
    if API_VERSION_FILE.exists():
        version = API_VERSION_FILE.read_text(encoding="utf-8").strip()
        if version:
            return version
    return "1.0.0"


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

    # S3 Archive Configuration
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_s3_bucket_name: str | None = None
    aws_s3_region: str = "eu-central-1"
    aws_s3_endpoint_url: str | None = None  # For S3-compatible services (Hetzner, MinIO, etc.)

    # Notifications
    # Set NTFY_URL to enable push notifications, e.g. https://ntfy.sh/your-private-topic
    ntfy_url: str | None = None
    ntfy_topic_title: str = "pollingAPI"
    # Set SLACK_WEBHOOK_URL to enable Slack notifications
    slack_webhook_url: str | None = None
    # Set RSS_FEED_PATH to override the pipeline notification RSS file
    rss_feed_path: Path = DATA_DIR / "export" / "pipeline-notifications.rss"

    # Data Paths
    data_dir: Path = DATA_DIR
    export_dir: Path = DATA_DIR / "export"
    report_dir: Path = DATA_DIR / "reports"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()
settings.api_version = _load_api_version()

# Ensure export directory exists
settings.export_dir.mkdir(exist_ok=True)
settings.report_dir.mkdir(exist_ok=True)


__all__ = ["settings", "PROJECT_ROOT", "DATA_DIR"]
