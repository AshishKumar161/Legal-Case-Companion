import logging
from typing import Any, ClassVar, Protocol

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.core.config import settings

logger = logging.getLogger(__name__)


class StorageProvider(Protocol):
    def generate_presigned_upload_url(
        self, object_key: str, mime_type: str, expires_in: int = 3600
    ) -> str: ...

    def generate_presigned_download_url(
        self,
        object_key: str,
        expires_in: int = 3600,
        response_content_disposition: str | None = None,
        response_content_type: str | None = None,
    ) -> str: ...

    def delete_object(self, object_key: str) -> bool: ...

    def get_object_bytes(self, object_key: str) -> bytes | None: ...

    def put_object_bytes(
        self, object_key: str, data: bytes, mime_type: str = "application/octet-stream"
    ) -> bool: ...

    def object_exists(self, object_key: str) -> bool: ...


class S3StorageProvider:
    """Production S3 storage provider.

    Configuration is read from the centralized ``Settings`` class (Phase 16),
    not from ``os.getenv`` directly.
    """

    def __init__(self):
        self.bucket_name = settings.AWS_S3_BUCKET_NAME

        # Use explicit credentials if provided, otherwise fall back to
        # boto3 default credential chain (IAM role, env vars, etc.)
        client_kwargs = {"region_name": settings.AWS_REGION}
        if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
            client_kwargs["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID
            client_kwargs["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY

        boto_config = Config(
            connect_timeout=5, read_timeout=15, retries={"max_attempts": 3}
        )
        self.client = boto3.client("s3", config=boto_config, **client_kwargs)

    def generate_presigned_upload_url(
        self, object_key: str, mime_type: str, expires_in: int = 3600
    ) -> str:
        try:
            url = self.client.generate_presigned_url(
                ClientMethod="put_object",
                Params={
                    "Bucket": self.bucket_name,
                    "Key": object_key,
                    "ContentType": mime_type,
                    "ServerSideEncryption": "AES256",
                },
                ExpiresIn=expires_in,
            )
            return url
        except ClientError as e:
            logger.error(f"Error generating presigned upload URL: {e}")
            raise RuntimeError("Could not generate upload URL") from e

    def generate_presigned_download_url(
        self,
        object_key: str,
        expires_in: int = 3600,
        response_content_disposition: str | None = None,
        response_content_type: str | None = None,
    ) -> str:
        try:
            params: dict[str, Any] = {"Bucket": self.bucket_name, "Key": object_key}
            if response_content_disposition:
                params["ResponseContentDisposition"] = response_content_disposition
            if response_content_type:
                params["ResponseContentType"] = response_content_type

            url = self.client.generate_presigned_url(
                ClientMethod="get_object",
                Params=params,
                ExpiresIn=expires_in,
            )
            return url
        except ClientError as e:
            logger.error(f"Error generating presigned download URL: {e}")
            raise RuntimeError("Could not generate download URL") from e

    def delete_object(self, object_key: str) -> bool:
        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=object_key)
            return True
        except ClientError as e:
            logger.error(f"Error deleting object from S3: {e}")
            return False

    def get_object_bytes(self, object_key: str) -> bytes | None:
        try:
            response = self.client.get_object(Bucket=self.bucket_name, Key=object_key)
            return response["Body"].read()
        except ClientError as e:
            logger.error(f"Error reading object bytes from S3: {e}")
            return None

    def put_object_bytes(
        self, object_key: str, data: bytes, mime_type: str = "application/octet-stream"
    ) -> bool:
        try:
            self.client.put_object(
                Bucket=self.bucket_name,
                Key=object_key,
                Body=data,
                ContentType=mime_type,
                ServerSideEncryption="AES256",
            )
            return True
        except ClientError as e:
            logger.error(f"Error writing object bytes to S3: {e}")
            return False

    def object_exists(self, object_key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket_name, Key=object_key)
            return True
        except ClientError as e:
            logger.warning(f"S3 object existence check failed for {object_key}: {e}")
            return False


class LocalMockStorageProvider:
    """DEVELOPMENT ONLY stub for local storage emulation without AWS credentials"""

    _storage_data: ClassVar[dict[str, bytes]] = {}

    def __init__(self):
        self.base_url = "http://localhost:8000/mock-storage"

    @property
    def _mock_storage(self) -> dict[str, bytes]:
        return self._storage_data

    def generate_presigned_upload_url(
        self, object_key: str, mime_type: str, expires_in: int = 3600
    ) -> str:
        # Returns a mock URL that the frontend can pretend to PUT to
        return f"{self.base_url}/upload?key={object_key}"

    def generate_presigned_download_url(
        self,
        object_key: str,
        expires_in: int = 3600,
        response_content_disposition: str | None = None,
        response_content_type: str | None = None,
    ) -> str:
        url = f"{self.base_url}/download?key={object_key}"
        if response_content_disposition:
            from urllib.parse import quote
            url += f"&disposition={quote(response_content_disposition)}"
        if response_content_type:
            from urllib.parse import quote
            url += f"&content_type={quote(response_content_type)}"
        return url

    def delete_object(self, object_key: str) -> bool:
        self._storage_data.pop(object_key, None)
        logger.info(f"LocalMockStorageProvider: Simulated deletion of {object_key}")
        return True

    def get_object_bytes(self, object_key: str) -> bytes | None:
        return self._storage_data.get(object_key)

    def set_mock_bytes(self, object_key: str, data: bytes) -> None:
        self._storage_data[object_key] = data

    def put_object_bytes(
        self, object_key: str, data: bytes, mime_type: str = "application/octet-stream"
    ) -> bool:
        self._storage_data[object_key] = data
        return True

    def object_exists(self, object_key: str) -> bool:
        return True

    @classmethod
    def clear(cls) -> None:
        cls._storage_data.clear()


_mock_provider_instance = LocalMockStorageProvider()


def get_storage_provider() -> StorageProvider:
    if settings.ENVIRONMENT == "production":
        return S3StorageProvider()
    return _mock_provider_instance
