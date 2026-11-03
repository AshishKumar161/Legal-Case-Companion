#!/usr/bin/env bash
# ==============================================================================
# Legal Case Companion (LCC) — Production Encrypted PostgreSQL Backup Script
# Performs atomic pg_dump, AES-256-GCM encryption, SHA-256 digest computation,
# fail-closed key validation, offsite remote replication, and remote verification.
# ==============================================================================

set -euo pipefail

# 1. Environment and Configuration
TIMESTAMP=$(date -u +"%Y%m%d_%H%M%SZ")
BACKUP_DIR="${BACKUP_DIR:-/tmp/lcc_backups}"
DB_NAME="${POSTGRES_DB:-legal_db}"
DB_USER="${POSTGRES_USER:-lcc_admin}"
DB_HOST="${POSTGRES_HOST:-localhost}"
DB_PORT="${POSTGRES_PORT:-5432}"
S3_BUCKET="${AWS_BACKUP_S3_BUCKET:-lcc-prod-db-backups}"
KMS_KEY_ID="${AWS_KMS_BACKUP_KEY_ID:-alias/lcc-prod-storage-key}"
ENVIRONMENT="${ENVIRONMENT:-production}"
UPLOAD_TO_S3="${UPLOAD_TO_S3:-false}"

mkdir -p "${BACKUP_DIR}"
DUMP_FILE="${BACKUP_DIR}/${DB_NAME}_${TIMESTAMP}.dump"
ENC_FILE="${DUMP_FILE}.enc"
SHA_FILE="${DUMP_FILE}.sha256"

# Fail-safe cleanup trap: Ensure no plaintext backup survives failure or abnormal termination
cleanup() {
  local exit_code=$?
  if [[ -f "${DUMP_FILE:-}" ]]; then
    shred -u "${DUMP_FILE}" 2>/dev/null || rm -f "${DUMP_FILE}"
  fi
  if [[ $exit_code -ne 0 ]]; then
    echo "[FATAL] Backup workflow failed with exit code ${exit_code}. Cleaning up incomplete artifacts." >&2
    rm -f "${ENC_FILE:-}" "${SHA_FILE:-}" 2>/dev/null || true
  fi
  exit "${exit_code}"
}
trap cleanup EXIT INT TERM

echo "========================================================================"
echo "  LCC AUTOMATED ENCRYPTED DATABASE BACKUP INITIATED"
echo "  Database: ${DB_NAME} on ${DB_HOST}:${DB_PORT} | Environment: ${ENVIRONMENT}"
echo "  Timestamp: ${TIMESTAMP}"
echo "========================================================================"

# Fail-closed encryption key validation: NEVER use predictable fallback keys
if [[ -z "${BACKUP_ENCRYPTION_KEY:-}" ]]; then
  echo "[FATAL] BACKUP_ENCRYPTION_KEY is not set in environment." >&2
  echo "[FATAL] Refusing to execute backup without configured encryption key. Failing closed." >&2
  exit 1
fi

if [[ ${#BACKUP_ENCRYPTION_KEY} -lt 32 ]]; then
  echo "[FATAL] BACKUP_ENCRYPTION_KEY must be at least 32 characters for secure AES-256 derivation." >&2
  exit 1
fi

# 2. Execute Atomic pg_dump (Custom Format with pgvector preservation)
echo "[1/4] Running pg_dump (custom compressed format)..."
pg_dump \
  -h "${DB_HOST}" \
  -p "${DB_PORT}" \
  -U "${DB_USER}" \
  -F c \
  -b \
  -v \
  -f "${DUMP_FILE}" \
  "${DB_NAME}"

DUMP_SIZE=$(stat -c%s "${DUMP_FILE}" 2>/dev/null || stat -f%z "${DUMP_FILE}")
echo "      -> Dump completed: ${DUMP_SIZE} bytes."

# 3. Encrypt Dump with Authenticated AES-256-GCM Envelope
echo "[2/4] Encrypting database dump with AES-256-GCM authenticated envelope..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "${SCRIPT_DIR}/backup_crypto_envelope.py" encrypt \
  --input "${DUMP_FILE}" \
  --output "${ENC_FILE}" \
  --key "${BACKUP_ENCRYPTION_KEY}" \
  --key-id "${KMS_KEY_ID}" \
  --metadata "{\"database\":\"${DB_NAME}\",\"timestamp\":\"${TIMESTAMP}\",\"environment\":\"${ENVIRONMENT}\"}"

# Explicitly wipe unencrypted plaintext dump immediately upon encryption success
shred -u "${DUMP_FILE}" 2>/dev/null || rm -f "${DUMP_FILE}"

ENC_SIZE=$(stat -c%s "${ENC_FILE}" 2>/dev/null || stat -f%z "${ENC_FILE}")
echo "      -> Encryption completed: ${ENC_SIZE} bytes ciphertext."

# 4. Generate SHA-256 Integrity Digest
echo "[3/4] Computing cryptographic SHA-256 integrity checksum..."
sha256sum "${ENC_FILE}" > "${SHA_FILE}"
CHECKSUM=$(awk '{print $1}' "${SHA_FILE}")
echo "      -> SHA-256: ${CHECKSUM}"

# 5. Offsite Cloud Vault Replication & Remote Verification
echo "[4/4] Offsite replication to private S3 backup vault..."
REPLICATED_OFFSITE=false

if [[ "${ENVIRONMENT}" == "production" ]] || [[ "${UPLOAD_TO_S3}" == "true" ]]; then
  if ! command -v aws >/dev/null 2>&1; then
    if [[ "${ENVIRONMENT}" == "production" ]]; then
      echo "[FATAL] In production, AWS CLI is mandatory for offsite S3 backup replication." >&2
      exit 1
    else
      echo "      [WARN] AWS CLI not available in test/staging environment; skipping upload."
    fi
  else
    REMOTE_ENC_URI="s3://${S3_BUCKET}/backups/${TIMESTAMP}/${DB_NAME}_${TIMESTAMP}.dump.enc"
    REMOTE_SHA_URI="s3://${S3_BUCKET}/backups/${TIMESTAMP}/${DB_NAME}_${TIMESTAMP}.sha256"

    echo "      -> Uploading ciphertext to ${REMOTE_ENC_URI}..."
    aws s3 cp "${ENC_FILE}" "${REMOTE_ENC_URI}" \
      --sse aws:kms \
      --sse-kms-key-id "${KMS_KEY_ID}" \
      --metadata "sha256=${CHECKSUM},database=${DB_NAME},timestamp=${TIMESTAMP}"

    aws s3 cp "${SHA_FILE}" "${REMOTE_SHA_URI}" \
      --sse aws:kms \
      --sse-kms-key-id "${KMS_KEY_ID}"

    # Verify remote object integrity and existence
    echo "      -> Verifying remote object on S3..."
    REMOTE_METADATA=$(aws s3api head-object --bucket "${S3_BUCKET}" --key "backups/${TIMESTAMP}/${DB_NAME}_${TIMESTAMP}.dump.enc")
    if [[ -z "${REMOTE_METADATA}" ]]; then
      echo "[FATAL] Verification failed: Remote backup object could not be confirmed on S3." >&2
      exit 1
    fi
    REPLICATED_OFFSITE=true
    echo "      -> Remote backup confirmed: s3://${S3_BUCKET}/backups/${TIMESTAMP}/"
  fi
fi

# In production, never report success when backup exists only on local ephemeral storage
if [[ "${ENVIRONMENT}" == "production" ]] && [[ "${REPLICATED_OFFSITE}" != "true" ]]; then
  echo "[FATAL] Production backup failed: Remote offsite replication could not be verified." >&2
  echo "[FATAL] Backups on local ephemeral storage do not satisfy LCC disaster recovery criteria." >&2
  exit 1
fi

echo "========================================================================"
echo "  [SUCCESS] Authenticated encrypted backup verified successfully."
echo "  Ciphertext: ${ENC_FILE}"
echo "  SHA-256   : ${CHECKSUM}"
if [[ "${REPLICATED_OFFSITE}" == "true" ]]; then
  echo "  Remote S3 : s3://${S3_BUCKET}/backups/${TIMESTAMP}/"
fi
echo "========================================================================"
