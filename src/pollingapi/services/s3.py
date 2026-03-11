"""S3 service for archive management."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from pollingapi.core import settings
from pollingapi.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class ArchiveMetadata:
    """Metadata for an archive file."""

    filename: str
    key: str
    size: int
    created_at: datetime
    public_url: str


class S3Service:
    """Service for managing data archives in S3."""

    def __init__(self) -> None:
        """Initialize S3 service with configuration."""
        self.bucket_name = settings.aws_s3_bucket_name
        self.region = settings.aws_s3_region
        self.endpoint_url = settings.aws_s3_endpoint_url
        self._client = None

    @property
    def client(self):
        """Get or create S3 client."""
        if self._client is None:
            config = Config(signature_version="s3v4")
            self._client = boto3.client(
                "s3",
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
                endpoint_url=self.endpoint_url,
                region_name=self.region,
                config=config,
            )
        return self._client

    def is_configured(self) -> bool:
        """Check if S3 is properly configured."""
        return (
            settings.aws_access_key_id is not None
            and settings.aws_secret_access_key is not None
            and settings.aws_s3_bucket_name is not None
        )

    def _get_public_url(self, key: str) -> str:
        """Generate public URL for an object."""
        if self.endpoint_url:
            base_url = self.endpoint_url.rstrip("/")
            return f"{base_url}/{self.bucket_name}/{key}"
        return f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{key}"

    def list_archives(self, prefix: str = "archives/") -> list[ArchiveMetadata]:
        """List all archive files in the bucket."""
        if not self.is_configured():
            logger.warning("S3 not configured, returning empty archive list")
            return []

        try:
            response = self.client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix,
            )

            archives = []
            for obj in response.get("Contents", []):
                key = obj["Key"]
                if key.endswith(".zip"):
                    archives.append(
                        ArchiveMetadata(
                            filename=key.split("/")[-1],
                            key=key,
                            size=obj["Size"],
                            created_at=obj["LastModified"],
                            public_url=self._get_public_url(key),
                        )
                    )

            archives.sort(key=lambda x: x.created_at, reverse=True)
            return archives
        except ClientError as e:
            logger.error(f"Failed to list archives: {e}")
            return []

    def upload_archive(
        self,
        file_path: Path,
        key: str | None = None,
    ) -> bool:
        """Upload an archive file to S3."""
        if not self.is_configured():
            logger.error("S3 not configured")
            return False

        if key is None:
            key = f"archives/{file_path.name}"

        try:
            self.client.upload_file(
                str(file_path),
                self.bucket_name,
                key,
                ExtraArgs={"ACL": "public-read"},
            )
            logger.info(f"Uploaded {file_path.name} to s3://{self.bucket_name}/{key}")
            return True
        except ClientError as e:
            logger.error(f"Failed to upload archive: {e}")
            return False

    def upload_index(self, archives: list[ArchiveMetadata]) -> bool:
        """Upload archive index JSON to bucket."""
        import json

        if not self.is_configured():
            logger.error("S3 not configured")
            return False

        index_data = {
            "archives": [
                {
                    "filename": a.filename,
                    "size": a.size,
                    "created_at": a.created_at.isoformat(),
                    "download_url": a.public_url,
                }
                for a in archives
            ],
            "updated_at": datetime.utcnow().isoformat(),
        }

        try:
            self.client.put_object(
                Bucket=self.bucket_name,
                Key="archive-index.json",
                Body=json.dumps(index_data, indent=2),
                ContentType="application/json",
                ACL="public-read",
            )
            logger.info("Uploaded archive index to s3")
            return True
        except ClientError as e:
            logger.error(f"Failed to upload index: {e}")
            return False

    def get_archive(self, filename: str) -> ArchiveMetadata | None:
        """Get a specific archive by filename."""
        archives = self.list_archives()
        for archive in archives:
            if archive.filename == filename:
                return archive
        return None
