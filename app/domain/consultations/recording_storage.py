import hashlib
import logging
import os
from pathlib import Path
from typing import Any, BinaryIO, Protocol
from uuid import UUID

from app.core.config import settings
from app.core.exceptions import ConfigurationError, ResourceNotFoundError, ValidationError

logger = logging.getLogger(__name__)


class RecordingStorageProvider(Protocol):
    def save_recording(
        self,
        consultation_id: UUID,
        recording_id: UUID,
        file_source: BinaryIO | bytes,
        extension: str = "webm",
    ) -> tuple[str, int, str]:
        """Save a recording binary stream/bytes to storage.
        Returns: (storage_path, file_size_bytes, checksum_sha256)
        """
        ...

    def get_recording_path(self, storage_path: str) -> Path:
        """Resolve full filesystem path safely."""
        ...

    def recording_exists(self, storage_path: str) -> bool:
        """Check whether recording file exists in storage."""
        ...

    def delete_recording(self, storage_path: str) -> bool:
        """Delete recording file from storage."""
        ...

    def get_file_size(self, storage_path: str) -> int:
        """Get file size in bytes."""
        ...


class LocalRecordingStorageProvider:
    """Local filesystem storage provider for in-app WebRTC video recordings.
    
    Structure:
        {LOCAL_RECORDING_STORAGE_PATH}/consultations/{consultation_id}/{recording_id}.{extension}
    """

    def __init__(self, base_dir: str | Path | None = None):
        self.base_dir = Path(base_dir or settings.LOCAL_RECORDING_STORAGE_PATH).resolve()
        # Automatically create base storage directory
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _sanitize_extension(self, extension: str) -> str:
        ext = extension.lower().strip().lstrip(".")
        allowed = {"webm", "mp4", "mkv", "mov"}
        if ext not in allowed:
            logger.warning(f"Unusual extension '{extension}' provided, defaulting to webm")
            return "webm"
        return ext

    def _resolve_safe_path(self, relative_path: str) -> Path:
        """Prevent directory traversal attacks by validating resolved path stays within base_dir."""
        if not relative_path or not isinstance(relative_path, str):
            raise ValidationError("Invalid storage path: must be a non-empty string")
        if any(c in relative_path for c in ("\x00", "?", "#")):
            raise ValidationError("Invalid storage path: contains illegal characters")
        clean_rel = os.path.normpath(relative_path).lstrip("/\\")
        target_path = (self.base_dir / clean_rel).resolve()
        try:
            target_path.relative_to(self.base_dir)
        except ValueError as err:
            logger.error(f"Path traversal attempt detected: {relative_path}")
            raise ValidationError("Invalid storage path: directory traversal attempt") from err
        return target_path

    def save_recording(
        self,
        consultation_id: UUID,
        recording_id: UUID,
        file_source: BinaryIO | bytes,
        extension: str = "webm",
    ) -> tuple[str, int, str]:
        clean_ext = self._sanitize_extension(extension)
        rel_dir = Path("consultations") / str(consultation_id)
        filename = f"{recording_id}.{clean_ext}"
        rel_storage_path = str(rel_dir / filename).replace("\\", "/")

        full_dir = self.base_dir / rel_dir
        full_dir.mkdir(parents=True, exist_ok=True)
        target_path = full_dir / filename

        sha256 = hashlib.sha256()
        bytes_written = 0

        if isinstance(file_source, (bytes, bytearray)):
            sha256.update(file_source)
            bytes_written = len(file_source)
            with open(target_path, "wb") as f:
                f.write(file_source)
        elif hasattr(file_source, "read"):
            # Stream from file-like object using 64KB chunks
            with open(target_path, "wb") as f:
                while True:
                    chunk = file_source.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    sha256.update(chunk)
                    bytes_written += len(chunk)
        else:
            # Iterable of bytes chunks
            with open(target_path, "wb") as f:
                for chunk in file_source:
                    if chunk:
                        f.write(chunk)
                        sha256.update(chunk)
                        bytes_written += len(chunk)

        checksum = sha256.hexdigest()
        logger.info(
            f"Successfully saved recording {recording_id} for consultation {consultation_id}: "
            f"{bytes_written} bytes, checksum={checksum[:12]}..."
        )
        return rel_storage_path, bytes_written, checksum

    def get_recording_path(self, storage_path: str) -> Path:
        target_path = self._resolve_safe_path(storage_path)
        if not target_path.is_file():
            raise ResourceNotFoundError("Recording file not found on disk")
        return target_path

    def recording_exists(self, storage_path: str) -> bool:
        try:
            target = self._resolve_safe_path(storage_path)
            return target.is_file()
        except (OSError, ValidationError):
            return False

    def delete_recording(self, storage_path: str) -> bool:
        try:
            target = self._resolve_safe_path(storage_path)
            if target.is_file():
                target.unlink()
                logger.info(f"Deleted recording at {storage_path}")
                return True
            return False
        except (OSError, ValidationError) as e:
            logger.error(f"Error deleting recording at {storage_path}: {e}")
            return False

    def get_file_size(self, storage_path: str) -> int:
        target = self.get_recording_path(storage_path)
        return target.stat().st_size


class S3RecordingStorageProvider:
    """Production private S3 storage provider for consultation video recordings."""

    def __init__(self, s3_client: Any = None, bucket_name: str | None = None):
        self.bucket_name = bucket_name or getattr(settings, "AWS_S3_BUCKET_NAME", "lcc-recordings-private")
        if s3_client:
            self.client = s3_client
        else:
            import boto3
            from botocore.config import Config

            client_kwargs: dict[str, Any] = {"region_name": getattr(settings, "AWS_REGION", "ap-south-1")}
            if getattr(settings, "AWS_ACCESS_KEY_ID", None) and getattr(settings, "AWS_SECRET_ACCESS_KEY", None):
                client_kwargs["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID
                client_kwargs["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY

            boto_config = Config(
                connect_timeout=5, read_timeout=30, retries={"max_attempts": 3}
            )
            self.client = boto3.client("s3", config=boto_config, **client_kwargs)

    def _sanitize_extension(self, extension: str) -> str:
        ext = extension.lower().strip().lstrip(".")
        allowed = {"webm", "mp4", "mkv", "mov"}
        return ext if ext in allowed else "webm"

    def _validate_safe_object_key(self, object_key: str) -> str:
        clean = os.path.normpath(object_key).replace("\\", "/").lstrip("/")
        if clean.startswith("..") or "/../" in clean:
            raise ValidationError("Invalid storage path: directory traversal attempt")
        if not clean.startswith("consultations/"):
            raise ValidationError("Invalid recording storage path namespace")
        return clean

    def save_recording(
        self,
        consultation_id: UUID,
        recording_id: UUID,
        file_source: BinaryIO | bytes,
        extension: str = "webm",
    ) -> tuple[str, int, str]:
        clean_ext = self._sanitize_extension(extension)
        object_key = f"consultations/{consultation_id}/{recording_id}.{clean_ext}"
        self._validate_safe_object_key(object_key)

        sha256 = hashlib.sha256()
        bytes_written = 0

        if isinstance(file_source, (bytes, bytearray)):
            sha256.update(file_source)
            bytes_written = len(file_source)
            body = bytes(file_source)
        elif hasattr(file_source, "read"):
            chunks = []
            while True:
                chunk = file_source.read(65536)
                if not chunk:
                    break
                sha256.update(chunk)
                bytes_written += len(chunk)
                chunks.append(chunk)
            body = b"".join(chunks)
        else:
            chunks = []
            for chunk in file_source:
                if chunk:
                    sha256.update(chunk)
                    bytes_written += len(chunk)
                    chunks.append(chunk)
            body = b"".join(chunks)

        mime = f"video/{clean_ext}"
        self.client.put_object(
            Bucket=self.bucket_name,
            Key=object_key,
            Body=body,
            ContentType=mime,
            ServerSideEncryption="AES256",
        )
        checksum = sha256.hexdigest()
        logger.info(
            f"Successfully saved S3 recording {recording_id}: "
            f"{bytes_written} bytes, checksum={checksum[:12]}..."
        )
        return object_key, bytes_written, checksum

    def get_recording_path(self, storage_path: str) -> Path:
        raise NotImplementedError("Direct filesystem path not available in S3 storage provider. Use streaming or presigned playback ticket.")

    def recording_exists(self, storage_path: str) -> bool:
        safe_key = self._validate_safe_object_key(storage_path)
        try:
            self.client.head_object(Bucket=self.bucket_name, Key=safe_key)
            return True
        except Exception:
            return False

    def delete_recording(self, storage_path: str) -> bool:
        safe_key = self._validate_safe_object_key(storage_path)
        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=safe_key)
            return True
        except Exception as e:
            logger.error(f"Error deleting S3 recording at {storage_path}: {e}")
            return False

    def get_file_size(self, storage_path: str) -> int:
        safe_key = self._validate_safe_object_key(storage_path)
        resp = self.client.head_object(Bucket=self.bucket_name, Key=safe_key)
        return int(resp.get("ContentLength", 0))

    def generate_presigned_playback_url(self, storage_path: str, expires_in: int = 60) -> str:
        safe_key = self._validate_safe_object_key(storage_path)
        return self.client.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": self.bucket_name, "Key": safe_key},
            ExpiresIn=expires_in,
        )


_storage_provider_instance: RecordingStorageProvider | None = None


def reset_recording_storage_provider() -> None:
    """Resets the cached recording storage provider (primarily for tests)."""
    global _storage_provider_instance
    _storage_provider_instance = None


def get_recording_storage_provider() -> RecordingStorageProvider:
    global _storage_provider_instance
    if _storage_provider_instance is None:
        env = getattr(settings, "ENVIRONMENT", "development").lower()
        has_s3 = bool(getattr(settings, "AWS_S3_BUCKET_NAME", None) and getattr(settings, "AWS_ACCESS_KEY_ID", None))
        if env in ("production", "staging"):
            if not has_s3:
                raise ConfigurationError(
                    f"{env.capitalize()} environment requires AWS S3 bucket configuration (AWS_S3_BUCKET_NAME, AWS_ACCESS_KEY_ID). "
                    f"Silent fallback to local recording storage is strictly forbidden in {env}."
                )
            _storage_provider_instance = S3RecordingStorageProvider()
        else:
            _storage_provider_instance = LocalRecordingStorageProvider()
    return _storage_provider_instance

