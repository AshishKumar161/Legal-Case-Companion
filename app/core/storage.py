import logging
import os
import re
from typing import Any, ClassVar, Protocol
from urllib.parse import quote, unquote

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.core.config import settings
from app.core.exceptions import ConfigurationError, ValidationError

logger = logging.getLogger(__name__)

# Control characters regex (\x00-\x1f, \x7f)
_CONTROL_CHAR_REGEX = re.compile(r"[\x00-\x1f\x7f]")
_WINDOWS_DRIVE_REGEX = re.compile(r"^[a-zA-Z]:")


def validate_storage_object_key(object_key: str) -> str:
    """Validates and sanitizes an object key for object storage operations.

    Guards against:
    - Path traversal (.., ../, ..\\, /../, \\..\\)
    - URL-encoded directory traversal (%2e%2e, %2f, %5c)
    - Absolute paths (leading / or \\, Windows drive letters)
    - Query string and URL fragment characters (?, #)
    - Control characters (ASCII 0-31, 127)
    - Empty, whitespace-only, or excessively long keys (>1024 chars)

    Returns the cleaned, validated object key.
    Raises ValidationError if the key fails validation.
    """
    if not object_key or not isinstance(object_key, str):
        raise ValidationError("Storage object key must be a non-empty string")

    clean_key = object_key.strip()
    if not clean_key:
        raise ValidationError("Storage object key cannot be empty or whitespace only")

    if len(clean_key) > 1024:
        raise ValidationError("Storage object key exceeds maximum allowed length of 1024 characters")

    # Check for control characters
    if _CONTROL_CHAR_REGEX.search(clean_key):
        raise ValidationError("Storage object key contains illegal control characters")

    # Check for query parameters or fragments
    if "?" in clean_key or "#" in clean_key:
        raise ValidationError("Storage object key cannot contain query ('?') or fragment ('#') characters")

    # Check for absolute path prefixes or Windows drive letters
    if clean_key.startswith(("/", "\\")):
        raise ValidationError("Storage object key cannot be an absolute path")

    if _WINDOWS_DRIVE_REGEX.match(clean_key):
        raise ValidationError("Storage object key cannot contain Windows drive specifiers")

    # Check for URL-encoded traversal patterns
    decoded = unquote(clean_key)
    if decoded != clean_key:
        # Check if the decoded form introduces traversal
        if ".." in decoded or decoded.startswith(("/", "\\")):
            raise ValidationError("Storage object key contains encoded path traversal sequences")

    # Normalized path traversal check
    normalized = os.path.normpath(clean_key).replace("\\", "/")
    if (
        normalized == ".."
        or normalized.startswith("../")
        or "/../" in f"/{normalized}/"
        or ".." in clean_key.split("/")
        or ".." in clean_key.split("\\")
    ):
        raise ValidationError("Storage object key contains path traversal sequences")

    return clean_key


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

    Configuration is read from the centralized ``Settings`` class,
    not from ``os.getenv`` directly.
    """

    def __init__(self):
        if not settings.AWS_S3_BUCKET_NAME:
            raise ConfigurationError("AWS_S3_BUCKET_NAME is required for S3StorageProvider")
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
        safe_key = validate_storage_object_key(object_key)
        try:
            url = self.client.generate_presigned_url(
                ClientMethod="put_object",
                Params={
                    "Bucket": self.bucket_name,
                    "Key": safe_key,
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
        safe_key = validate_storage_object_key(object_key)
        try:
            params: dict[str, Any] = {"Bucket": self.bucket_name, "Key": safe_key}
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
        safe_key = validate_storage_object_key(object_key)
        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=safe_key)
            return True
        except ClientError as e:
            logger.error(f"Error deleting object from S3: {e}")
            return False

    def get_object_bytes(self, object_key: str) -> bytes | None:
        safe_key = validate_storage_object_key(object_key)
        try:
            response = self.client.get_object(Bucket=self.bucket_name, Key=safe_key)
            return response["Body"].read()
        except ClientError as e:
            logger.error(f"Error reading object bytes from S3: {e}")
            return None

    def put_object_bytes(
        self, object_key: str, data: bytes, mime_type: str = "application/octet-stream"
    ) -> bool:
        safe_key = validate_storage_object_key(object_key)
        try:
            self.client.put_object(
                Bucket=self.bucket_name,
                Key=safe_key,
                Body=data,
                ContentType=mime_type,
                ServerSideEncryption="AES256",
            )
            return True
        except ClientError as e:
            logger.error(f"Error writing object bytes to S3: {e}")
            return False

    def object_exists(self, object_key: str) -> bool:
        safe_key = validate_storage_object_key(object_key)
        try:
            self.client.head_object(Bucket=self.bucket_name, Key=safe_key)
            return True
        except ClientError as e:
            logger.warning(f"S3 object existence check failed for {safe_key}: {e}")
            return False


class LocalMockStorageProvider:
    """DEVELOPMENT ONLY stub for local storage emulation without AWS credentials"""

    _storage_data: ClassVar[dict[str, bytes]] = {}
    _presigned_keys: ClassVar[set[str]] = set()

    def __init__(self):
        self.base_url = "http://localhost:8000/mock-storage"

    @property
    def _mock_storage(self) -> dict[str, bytes]:
        return self._storage_data

    def generate_presigned_upload_url(
        self, object_key: str, mime_type: str, expires_in: int = 3600
    ) -> str:
        safe_key = validate_storage_object_key(object_key)
        self._presigned_keys.add(safe_key)
        # Returns a mock URL that the frontend can pretend to PUT to with properly encoded key
        return f"{self.base_url}/upload?key={quote(safe_key, safe='')}"

    def generate_presigned_download_url(
        self,
        object_key: str,
        expires_in: int = 3600,
        response_content_disposition: str | None = None,
        response_content_type: str | None = None,
    ) -> str:
        safe_key = validate_storage_object_key(object_key)
        url = f"{self.base_url}/download?key={quote(safe_key, safe='')}"
        if response_content_disposition:
            url += f"&disposition={quote(response_content_disposition)}"
        if response_content_type:
            url += f"&content_type={quote(response_content_type)}"
        return url

    def delete_object(self, object_key: str) -> bool:
        safe_key = validate_storage_object_key(object_key)
        self._storage_data.pop(safe_key, None)
        self._presigned_keys.discard(safe_key)
        logger.info(f"LocalMockStorageProvider: Simulated deletion of {safe_key}")
        return True

    def get_object_bytes(self, object_key: str) -> bytes | None:
        safe_key = validate_storage_object_key(object_key)
        return self._storage_data.get(safe_key)

    def set_mock_bytes(self, object_key: str, data: bytes) -> None:
        safe_key = validate_storage_object_key(object_key)
        self._storage_data[safe_key] = data
        self._presigned_keys.add(safe_key)

    def put_object_bytes(
        self, object_key: str, data: bytes, mime_type: str = "application/octet-stream"
    ) -> bool:
        safe_key = validate_storage_object_key(object_key)
        self._storage_data[safe_key] = data
        self._presigned_keys.add(safe_key)
        return True

    def object_exists(self, object_key: str) -> bool:
        safe_key = validate_storage_object_key(object_key)
        return safe_key in self._storage_data or safe_key in self._presigned_keys

    @classmethod
    def clear(cls) -> None:
        cls._storage_data.clear()
        cls._presigned_keys.clear()


_mock_provider_instance = LocalMockStorageProvider()


def get_storage_provider() -> StorageProvider:
    if settings.ENVIRONMENT in ("production", "staging"):
        if not settings.AWS_S3_BUCKET_NAME:
            raise ConfigurationError(
                "Production and staging environments require AWS_S3_BUCKET_NAME configuration. "
                "Local mock storage is strictly forbidden in production/staging."
            )
        return S3StorageProvider()
    return _mock_provider_instance

