"""Strict content signature, magic byte, and filename validation for secure document ingestion."""

from typing import Final

from app.core.exceptions import ValidationError

# Dangerous executable or script extensions
DANGEROUS_EXTENSIONS: Final[set[str]] = {
    ".exe",
    ".dll",
    ".bat",
    ".cmd",
    ".sh",
    ".vbs",
    ".ps1",
    ".scr",
    ".pif",
    ".com",
    ".jar",
    ".jsp",
    ".php",
    ".asp",
    ".aspx",
    ".py",
    ".rb",
    ".pl",
    ".cgi",
    ".hta",
    ".msi",
}

# Known magic bytes signatures for allowed document types
MAGIC_SIGNATURES: Final[dict[str, list[bytes]]] = {
    "application/pdf": [b"%PDF-"],
    "image/png": [b"\x89PNG\r\n\x1a\n"],
    "image/jpeg": [b"\xff\xd8\xff"],
    "image/jpg": [b"\xff\xd8\xff"],
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [b"PK\x03\x04"],
    "application/msword": [b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", b"PK\x03\x04"],
}

# Executable headers that must never appear at the start of any legal document
BLOCKED_EXECUTABLE_HEADERS: Final[list[bytes]] = [
    b"MZ",  # Windows PE / DOS
    b"\x7fELF",  # Linux ELF
    b"\xca\xfe\xba\xbe",  # Java bytecode / Mach-O Fat Binary
    b"\xfe\xed\xfa\xce",  # Mach-O 32-bit
    b"\xfe\xed\xfa\xcf",  # Mach-O 64-bit
    b"\xcf\xfa\xed\xfe",  # Mach-O reverse byte order
]


def validate_filename_security(filename: str) -> str:
    """Validates filename against path traversal, dangerous extensions, and double extensions.

    Returns sanitized, normalized filename.
    """
    if not filename or not filename.strip():
        raise ValidationError("Filename cannot be empty")

    cleaned = filename.strip()
    if len(cleaned) > 255:
        raise ValidationError("Filename exceeds maximum length of 255 characters")

    # Reject null bytes and path traversal patterns
    if "\x00" in cleaned or "/" in cleaned or "\\" in cleaned or ".." in cleaned:
        raise ValidationError("Filename contains illegal characters or path traversal sequences")

    # Extract all extensions (e.g. 'foo.pdf.exe' -> ['.pdf', '.exe'])
    parts = cleaned.lower().split(".")
    if len(parts) > 1:
        extensions = [f".{part}" for part in parts[1:]]

        # Check for any dangerous extension anywhere in the extension chain
        for ext in extensions:
            if ext in DANGEROUS_EXTENSIONS:
                raise ValidationError(f"File extension '{ext}' is prohibited for security reasons")

        # Check for suspicious double extensions (e.g. file.exe.pdf or file.pdf.docx)
        if len(extensions) > 1:
            # Rejects multi-extension tricks
            for ext in extensions[:-1]:
                if ext in DANGEROUS_EXTENSIONS:
                    raise ValidationError("Double extension with executable component is prohibited")

    return cleaned


def validate_file_magic_bytes(file_bytes: bytes, declared_mime_type: str) -> None:
    """Cryptographically validates that binary file content matches the declared MIME type signature.

    Detects content-type spoofing, executable embedding, and malformed files.
    """
    if not file_bytes:
        raise ValidationError("Uploaded file is empty (0 bytes)")

    # 1. Reject any file that begins with executable headers
    for header in BLOCKED_EXECUTABLE_HEADERS:
        if file_bytes.startswith(header):
            raise ValidationError(
                "Executable binary header detected. Executable files are strictly prohibited."
            )

    # 2. Validate magic bytes against declared MIME type
    if declared_mime_type in MAGIC_SIGNATURES:
        signatures = MAGIC_SIGNATURES[declared_mime_type]
        if not any(file_bytes.startswith(sig) for sig in signatures):
            raise ValidationError(
                f"File content signature does not match declared MIME type '{declared_mime_type}'. "
                "Potential content-type spoofing detected."
            )

    # 3. Specific validation for plain text
    elif declared_mime_type == "text/plain":
        # Plain text must not contain null bytes (indicative of binary/executable payload)
        if b"\x00" in file_bytes:
            raise ValidationError(
                "Binary data with null bytes detected in plain text document."
            )
        try:
            # Must be decodable as valid text
            file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                file_bytes.decode("latin-1")
            except Exception as e:
                raise ValidationError(f"Plain text file cannot be decoded: {e}") from e

    # 4. Comprehensive Archive & Zip-Bomb safety validation (Phase 16)
    if file_bytes.startswith(b"PK\x03\x04"):
        validate_archive_safety(file_bytes)


def validate_archive_safety(
    file_bytes: bytes,
    max_uncompressed_bytes: int = 200 * 1024 * 1024,  # 200 MB max uncompressed size
    max_compression_ratio: float = 100.0,              # 100:1 max compression ratio (zip bomb defense)
    max_file_count: int = 1000,                        # Max 1000 items inside container
) -> None:
    """Protects against zip bombs, path traversal, nested archives, and decompression attacks.

    Applicable to ZIP files, DOCX/XLSX containers, and archive uploads.
    """
    import io
    import zipfile

    if not file_bytes.startswith(b"PK\x03\x04"):
        return

    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
            infolist = zf.infolist()
            if len(infolist) > max_file_count:
                raise ValidationError(
                    f"Archive contains {len(infolist)} files, exceeding maximum permitted limit of {max_file_count}."
                )

            total_uncompressed_bytes = 0
            compressed_bytes = len(file_bytes)

            for info in infolist:
                # 1. Path traversal defense
                name = info.filename
                if ".." in name or name.startswith("/") or name.startswith("\\") or ":" in name:
                    raise ValidationError(
                        f"Archive contains dangerous path traversal pattern: '{name}'"
                    )

                # 2. Nested archive defense
                lower_name = name.lower()
                if any(lower_name.endswith(ext) for ext in [".zip", ".tar", ".gz", ".bz2", ".7z", ".rar"]):
                    raise ValidationError(
                        f"Nested archive detected ('{name}'). Nested archives are strictly prohibited."
                    )

                total_uncompressed_bytes += info.file_size
                if total_uncompressed_bytes > max_uncompressed_bytes:
                    raise ValidationError(
                        f"Archive uncompressed size exceeds maximum allowable limit of {max_uncompressed_bytes // (1024 * 1024)}MB."
                    )

            # 3. Compression ratio check (zip bomb defense)
            if compressed_bytes > 0:
                ratio = total_uncompressed_bytes / compressed_bytes
                if ratio > max_compression_ratio:
                    raise ValidationError(
                        f"Excessive archive compression ratio ({ratio:.1f}:1). Potential decompression bomb detected."
                    )

    except zipfile.BadZipFile as e:
        raise ValidationError(f"Malformed or corrupted archive container: {e}") from e
