"""
Tests for LCC Authenticated Backup Encryption (scripts/backup_crypto_envelope.py).

Validates:
- AES-256-GCM authenticated envelope encryption and decryption with exact fidelity.
- Strict detection and rejection of tampered ciphertext (bit flipping) via InvalidTag.
- Rejection of tampered authentication tags via InvalidTag.
- Rejection of tampered Authenticated Additional Data (AAD) metadata.
- Rejection of decryption with incorrect passphrase or key.
- Key rotation support and key version identification.
- Nonce uniqueness across successive backup runs.
"""

import os
import tempfile
import pytest
from cryptography.exceptions import InvalidTag

from scripts.backup_crypto_envelope import (
    encrypt_backup_envelope,
    decrypt_backup_envelope,
    MAGIC_HEADER,
    FORMAT_VERSION,
)


@pytest.fixture
def sample_payload():
    return b"PGDMP_HEADER_DATA_1536_DIM_VECTORS_REPRESENTATIVE_MIGRATION_SNAPSHOT_" * 1000


def test_authenticated_backup_encryption_roundtrip(sample_payload):
    with tempfile.TemporaryDirectory() as tmp_dir:
        input_file = os.path.join(tmp_dir, "test.dump")
        enc_file = os.path.join(tmp_dir, "test.dump.enc")
        dec_file = os.path.join(tmp_dir, "restored.dump")

        with open(input_file, "wb") as f:
            f.write(sample_payload)

        passphrase = "PrimaryProductionDrillPassphrase_2026_AES256"
        metadata = {
            "database": "legal_db",
            "environment": "production",
            "alembic_head": "z3a4b5c6d7e8",
        }

        # 1. Encrypt
        enc_result = encrypt_backup_envelope(
            input_file, enc_file, passphrase, key_id="lcc-kms-cmk-2026-v1", metadata=metadata
        )
        assert enc_result["status"] == "ENCRYPTED"
        assert enc_result["key_id"] == "lcc-kms-cmk-2026-v1"
        assert os.path.exists(enc_file)

        # 2. Decrypt
        dec_result = decrypt_backup_envelope(
            enc_file, dec_file, passphrase, expected_key_id="lcc-kms-cmk-2026-v1"
        )
        assert dec_result["status"] == "AUTHENTICATED_AND_DECRYPTED"
        assert dec_result["metadata"]["database"] == "legal_db"

        # 3. Verify exact byte fidelity
        with open(dec_file, "rb") as f:
            restored = f.read()
        assert restored == sample_payload


def test_tampered_ciphertext_fails_with_invalid_tag(sample_payload):
    """Flipping even a single bit in the ciphertext MUST raise InvalidTag."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        input_file = os.path.join(tmp_dir, "test.dump")
        enc_file = os.path.join(tmp_dir, "test.dump.enc")
        dec_file = os.path.join(tmp_dir, "restored.dump")

        with open(input_file, "wb") as f:
            f.write(sample_payload)

        passphrase = "SecretPassphrase123"
        encrypt_backup_envelope(input_file, enc_file, passphrase)

        # Tamper: corrupt one byte near the end of the file (within ciphertext / auth tag)
        with open(enc_file, "r+b") as f:
            f.seek(-5, os.SEEK_END)
            byte = f.read(1)[0]
            f.seek(-5, os.SEEK_END)
            f.write(bytes([byte ^ 0xFF]))  # flip bits

        # Decryption MUST fail with InvalidTag before returning any plaintext
        with pytest.raises(InvalidTag):
            decrypt_backup_envelope(enc_file, dec_file, passphrase)


def test_tampered_aad_metadata_fails_with_invalid_tag(sample_payload):
    """Tampering with unencrypted header AAD metadata must be detected by the GCM tag."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        input_file = os.path.join(tmp_dir, "test.dump")
        enc_file = os.path.join(tmp_dir, "test.dump.enc")
        dec_file = os.path.join(tmp_dir, "restored.dump")

        with open(input_file, "wb") as f:
            f.write(sample_payload)

        passphrase = "SecretPassphrase123"
        encrypt_backup_envelope(input_file, enc_file, passphrase, metadata={"role": "backup_operator"})

        # Tamper: modify a byte in the AAD portion
        with open(enc_file, "r+b") as f:
            f.seek(60)  # offset inside AAD JSON
            f.write(b"X")

        with pytest.raises(InvalidTag):
            decrypt_backup_envelope(enc_file, dec_file, passphrase)


def test_incorrect_passphrase_fails_with_invalid_tag(sample_payload):
    """An incorrect decryption key must fail authentication."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        input_file = os.path.join(tmp_dir, "test.dump")
        enc_file = os.path.join(tmp_dir, "test.dump.enc")
        dec_file = os.path.join(tmp_dir, "restored.dump")

        with open(input_file, "wb") as f:
            f.write(sample_payload)

        encrypt_backup_envelope(input_file, enc_file, "CorrectPassphrase_ABC")

        with pytest.raises(InvalidTag):
            decrypt_backup_envelope(enc_file, dec_file, "WrongPassphrase_XYZ")


def test_key_rotation_and_historical_key_id(sample_payload):
    """Historical backups with rotated key IDs can be identified and decrypted with appropriate key."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        input_file = os.path.join(tmp_dir, "test.dump")
        enc_v1 = os.path.join(tmp_dir, "v1.dump.enc")
        enc_v2 = os.path.join(tmp_dir, "v2.dump.enc")
        dec_file = os.path.join(tmp_dir, "restored.dump")

        with open(input_file, "wb") as f:
            f.write(sample_payload)

        # Key Version 1
        key_v1 = "Key_2025_AnnualRotation_v1"
        encrypt_backup_envelope(input_file, enc_v1, key_v1, key_id="lcc-kms-cmk-2025-v1")

        # Key Version 2 (Rotated)
        key_v2 = "Key_2026_AnnualRotation_v2"
        encrypt_backup_envelope(input_file, enc_v2, key_v2, key_id="lcc-kms-cmk-2026-v2")

        # Verify key ID mismatch assertion
        with pytest.raises(ValueError, match="Key ID mismatch"):
            decrypt_backup_envelope(enc_v1, dec_file, key_v1, expected_key_id="lcc-kms-cmk-2026-v2")

        # Verify historical v1 backup decrypts with v1 key
        res_v1 = decrypt_backup_envelope(enc_v1, dec_file, key_v1, expected_key_id="lcc-kms-cmk-2025-v1")
        assert res_v1["key_id"] == "lcc-kms-cmk-2025-v1"

        # Verify new v2 backup decrypts with v2 key
        res_v2 = decrypt_backup_envelope(enc_v2, dec_file, key_v2, expected_key_id="lcc-kms-cmk-2026-v2")
        assert res_v2["key_id"] == "lcc-kms-cmk-2026-v2"


def test_unique_nonce_generation(sample_payload):
    """Each backup encryption MUST generate a distinct unique 96-bit nonce."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        input_file = os.path.join(tmp_dir, "test.dump")
        enc1 = os.path.join(tmp_dir, "enc1.dump.enc")
        enc2 = os.path.join(tmp_dir, "enc2.dump.enc")

        with open(input_file, "wb") as f:
            f.write(sample_payload)

        res1 = encrypt_backup_envelope(input_file, enc1, "SamePassphrase")
        res2 = encrypt_backup_envelope(input_file, enc2, "SamePassphrase")

        assert res1["nonce_hex"] != res2["nonce_hex"]
        assert res1["salt_hex"] != res2["salt_hex"]
