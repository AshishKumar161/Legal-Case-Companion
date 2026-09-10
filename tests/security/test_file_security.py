import io
import zipfile

import pytest

from app.core.exceptions import ValidationError
from app.core.file_validation import (
    validate_archive_safety,
    validate_file_magic_bytes,
    validate_filename_security,
)


def test_reject_executable_binary_headers():
    """Verify that executable binary headers (DOS PE, ELF, Java bytecode) are strictly rejected."""
    # Windows PE executable
    with pytest.raises(ValidationError, match="Executable binary header detected"):
        validate_file_magic_bytes(b"MZ\x90\x00\x03\x00\x00\x00", "application/pdf")

    # Linux ELF binary
    with pytest.raises(ValidationError, match="Executable binary header detected"):
        validate_file_magic_bytes(b"\x7fELF\x02\x01\x01\x00", "application/pdf")


def test_archive_path_traversal_defense():
    """Verify that archives containing path traversal filenames are rejected."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../../etc/passwd", "root:x:0:0:root")

    archive_bytes = buf.getvalue()
    with pytest.raises(ValidationError, match="dangerous path traversal pattern"):
        validate_archive_safety(archive_bytes)


def test_archive_nested_archive_defense():
    """Verify that archives containing nested archives are rejected."""
    nested_buf = io.BytesIO()
    with zipfile.ZipFile(nested_buf, "w") as nzf:
        nzf.writestr("inner.txt", "inner content")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("malicious_nested.zip", nested_buf.getvalue())

    archive_bytes = buf.getvalue()
    with pytest.raises(ValidationError, match="Nested archive detected"):
        validate_archive_safety(archive_bytes)


def test_archive_zip_bomb_compression_ratio_defense():
    """Verify that decompression bombs with extreme compression ratios are rejected."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # 1MB of zeroes compresses to < 1KB (ratio > 1000:1)
        zf.writestr("zeroes.bin", b"\x00" * (1024 * 1024))

    archive_bytes = buf.getvalue()
    with pytest.raises(ValidationError, match="Potential decompression bomb detected"):
        validate_archive_safety(archive_bytes, max_compression_ratio=50.0)


def test_filename_traversal_and_extension_security():
    """Verify filename sanitization against path traversal, null bytes, and dangerous extensions."""
    # Path traversal
    with pytest.raises(ValidationError, match="illegal characters or path traversal"):
        validate_filename_security("../../../etc/shadow")

    # Null byte
    with pytest.raises(ValidationError, match="illegal characters or path traversal"):
        validate_filename_security("document.pdf\x00.exe")

    # Dangerous extension
    with pytest.raises(ValidationError, match="is prohibited for security reasons"):
        validate_filename_security("malware.exe")

    # Double extension trick
    with pytest.raises(ValidationError, match="is prohibited"):
        validate_filename_security("contract.exe.pdf")
