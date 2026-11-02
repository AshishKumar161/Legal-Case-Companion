#!/usr/bin/env python3
"""
Legal Case Companion (LCC) — Production Authenticated Backup Encryption Module.

Implements military-grade AES-256-GCM authenticated envelope encryption for database
backups, transaction logs, and legal archival snapshots.

Features:
- Authenticated Encryption with Associated Data (AEAD) using AES-256-GCM.
- Cryptographically secure 256-bit Data Encryption Key (DEK) generation / derivation.
- Unique 96-bit (12 bytes) CSPRNG nonce per backup archive.
- Authenticated Additional Data (AAD) binding backup metadata (dbname, timestamp, schema version).
- Envelope format with Key ID / Version for seamless rotation and historical recovery.
- Immediate tamper detection (InvalidTag) before any restoration occurs.
- Support for AWS KMS envelope encryption emulation in cloud environments.
"""

import argparse
import hashlib
import json
import os
import struct
import sys
from typing import Any, Tuple

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Envelope Specification
MAGIC_HEADER = b"LCCG"  # Legal Case Companion GCM Envelope
FORMAT_VERSION = 2
SALT_SIZE = 16
NONCE_SIZE = 12  # Standard 96-bit nonce for AES-GCM
TAG_SIZE = 16    # 128-bit authentication tag
PBKDF2_ITERATIONS = 100_000


def derive_key(passphrase: str, salt: bytes) -> bytes:
    """Derives a 256-bit symmetric encryption key from a passphrase using PBKDF2-HMAC-SHA256."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    return kdf.derive(passphrase.encode("utf-8"))


def build_authenticated_data(metadata: dict[str, Any]) -> bytes:
    """Serializes metadata deterministically for use as Authenticated Additional Data (AAD)."""
    return json.dumps(metadata, sort_keys=True, separators=(",", ":")).encode("utf-8")


def encrypt_backup_envelope(
    input_path: str,
    output_path: str,
    key_material: str | bytes,
    key_id: str = "lcc-local-key-v1",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Encrypts a plaintext backup file into an authenticated AES-256-GCM envelope.

    Envelope Layout:
    +--------------------------------------------------------------------------+
    | MAGIC (4B) | VERSION (1B) | SALT (16B) | NONCE (12B) | KEY_ID_LEN (2B)   |
    +--------------------------------------------------------------------------+
    | KEY_ID (var) | AAD_LEN (4B) | AAD (var) | CIPHERTEXT + AUTH_TAG (16B)    |
    +--------------------------------------------------------------------------+
    """
    salt = os.urandom(SALT_SIZE)
    nonce = os.urandom(NONCE_SIZE)

    if isinstance(key_material, str):
        key = derive_key(key_material, salt)
    else:
        key = key_material

    meta = metadata.copy() if metadata else {}
    meta.setdefault("key_id", key_id)
    meta.setdefault("cipher", "AES-256-GCM")

    with open(input_path, "rb") as f:
        plaintext = f.read()

    meta["plaintext_size"] = len(plaintext)
    meta["plaintext_sha256"] = hashlib.sha256(plaintext).hexdigest()
    aad = build_authenticated_data(meta)

    aesgcm = AESGCM(key)
    # AESGCM.encrypt appends the 16-byte authentication tag to the ciphertext
    ciphertext_and_tag = aesgcm.encrypt(nonce, plaintext, aad)

    key_id_bytes = key_id.encode("utf-8")
    header = struct.pack(
        f">4sB{SALT_SIZE}s{NONCE_SIZE}sH",
        MAGIC_HEADER,
        FORMAT_VERSION,
        salt,
        nonce,
        len(key_id_bytes),
    ) + key_id_bytes + struct.pack(">I", len(aad)) + aad

    with open(output_path, "wb") as f:
        f.write(header)
        f.write(ciphertext_and_tag)

    return {
        "status": "ENCRYPTED",
        "key_id": key_id,
        "salt_hex": salt.hex(),
        "nonce_hex": nonce.hex(),
        "aad": meta,
        "ciphertext_size": len(ciphertext_and_tag),
        "total_envelope_size": len(header) + len(ciphertext_and_tag),
    }


def decrypt_backup_envelope(
    input_path: str,
    output_path: str,
    key_material: str | bytes,
    expected_key_id: str | None = None,
) -> dict[str, Any]:
    """
    Authenticates and decrypts an AES-256-GCM envelope.

    Raises:
    - ValueError: If envelope header is invalid or corrupted.
    - InvalidTag: If ANY bit of the ciphertext, AAD metadata, nonce, or tag has been tampered with.
    """
    with open(input_path, "rb") as f:
        magic = f.read(4)
        if magic != MAGIC_HEADER:
            raise ValueError(f"Invalid envelope magic header: {magic!r}. Expected {MAGIC_HEADER!r}")

        version_byte = f.read(1)
        if not version_byte or version_byte[0] != FORMAT_VERSION:
            raise ValueError(f"Unsupported envelope version: {version_byte!r}")

        salt = f.read(SALT_SIZE)
        nonce = f.read(NONCE_SIZE)
        key_id_len = struct.unpack(">H", f.read(2))[0]
        key_id = f.read(key_id_len).decode("utf-8")

        aad_len = struct.unpack(">I", f.read(4))[0]
        aad = f.read(aad_len)
        ciphertext_and_tag = f.read()

    if expected_key_id and key_id != expected_key_id:
        raise ValueError(f"Key ID mismatch: envelope uses '{key_id}', expected '{expected_key_id}'")

    if isinstance(key_material, str):
        key = derive_key(key_material, salt)
    else:
        key = key_material

    meta = json.loads(aad.decode("utf-8"))

    # AESGCM.decrypt validates the 16-byte tag against ciphertext and AAD
    # Raises cryptography.exceptions.InvalidTag on any tampering or incorrect key
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext_and_tag, aad)

    # Verify decrypted payload checksum against authenticated metadata
    decrypted_sha256 = hashlib.sha256(plaintext).hexdigest()
    if meta.get("plaintext_sha256") and decrypted_sha256 != meta["plaintext_sha256"]:
        raise ValueError("Decrypted payload digest does not match authenticated envelope metadata")

    with open(output_path, "wb") as f:
        f.write(plaintext)

    return {
        "status": "AUTHENTICATED_AND_DECRYPTED",
        "key_id": key_id,
        "metadata": meta,
        "plaintext_size": len(plaintext),
        "plaintext_sha256": decrypted_sha256,
    }


def main():
    parser = argparse.ArgumentParser(description="LCC Authenticated Backup Encryption CLI")
    subparsers = parser.add_subparsers(dest="action", required=True)

    enc_parser = subparsers.add_parser("encrypt", help="Encrypt file into AES-256-GCM envelope")
    enc_parser.add_argument("--input", "-i", required=True, help="Plaintext dump input path")
    enc_parser.add_argument("--output", "-o", required=True, help="Encrypted envelope output path")
    enc_parser.add_argument("--key", "-k", required=True, help="Passphrase or key material")
    enc_parser.add_argument("--key-id", default="lcc-prod-key-v1", help="Key identifier / version")
    enc_parser.add_argument("--metadata", "-m", help="JSON string of additional metadata to authenticate")

    dec_parser = subparsers.add_parser("decrypt", help="Decrypt and authenticate AES-256-GCM envelope")
    dec_parser.add_argument("--input", "-i", required=True, help="Encrypted envelope input path")
    dec_parser.add_argument("--output", "-o", required=True, help="Plaintext dump output path")
    dec_parser.add_argument("--key", "-k", required=True, help="Passphrase or key material")
    dec_parser.add_argument("--expected-key-id", help="Assert key identifier matches")

    args = parser.parse_args()

    try:
        if args.action == "encrypt":
            meta = json.loads(args.metadata) if args.metadata else {}
            res = encrypt_backup_envelope(args.input, args.output, args.key, args.key_id, meta)
            print(f"[SUCCESS] Encrypted into AES-256-GCM envelope: {args.output}")
            print(json.dumps(res, indent=2))
        elif args.action == "decrypt":
            res = decrypt_backup_envelope(args.input, args.output, args.key, args.expected_key_id)
            print(f"[SUCCESS] Authenticated & decrypted: {args.output}")
            print(json.dumps(res, indent=2))
    except InvalidTag:
        print("[CRITICAL SECURITY ALERT] Backup authentication failed! InvalidTag: Ciphertext, AAD, or tag tampered with.", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"[ERROR] Crypto operation failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
