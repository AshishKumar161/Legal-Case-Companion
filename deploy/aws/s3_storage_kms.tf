# ==============================================================================
# Legal Case Companion (LCC) — Production AWS S3 & KMS Infrastructure
# Provides secure, private, legally compliant storage for Evidence Locker,
# Consultation Video Recordings, and Encrypted Database Backups.
# Conforms to Bharatiya Sakshya Adhiniyam, 2023 (Section 63) and DPDP Act, 2023.
# ==============================================================================

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region                      = var.aws_region
  skip_credentials_validation = var.aws_account_id != null
  skip_requesting_account_id  = var.aws_account_id != null
  skip_metadata_api_check     = var.aws_account_id != null
}

variable "aws_region" {
  type        = string
  default     = "ap-south-1" # Mumbai region for Indian Data Sovereignty compliance
  description = "AWS deployment region ensuring compliance with Indian Digital Personal Data Protection (DPDP) Act."
}

variable "environment" {
  type        = string
  default     = "prod"
  description = "Target environment moniker (prod, staging)."
}

variable "aws_account_id" {
  type        = string
  default     = null
  description = "Optional AWS Account ID override for offline planning or mock environments."
}

locals {
  account_id = var.aws_account_id != null ? var.aws_account_id : try(data.aws_caller_identity.current[0].account_id, "123456789012")
}

# ------------------------------------------------------------------------------
# 1. AWS KMS Customer Managed Key (CMK) for Evidence & Vault Encryption
# ------------------------------------------------------------------------------
resource "aws_kms_key" "lcc_storage_key" {
  description             = "LCC Customer Managed Key for Evidence Locker and Database Encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true # Automatic 365-day rotation; historical versions preserved for decryption

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "EnableRootPermissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${local.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "AllowLCCBackendServiceAccess"
        Effect = "Allow"
        Principal = {
          AWS = aws_iam_role.lcc_backend_role.arn
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:DescribeKey"
        ]
        Resource = "*"
      }
    ]
  })

  tags = {
    Project     = "LegalCaseCompanion"
    Environment = var.environment
    Compliance  = "DPDP-India-Section63BSA"
  }
}

resource "aws_kms_alias" "lcc_storage_key_alias" {
  name          = "alias/lcc-${var.environment}-storage-key"
  target_key_id = aws_kms_key.lcc_storage_key.key_id
}

data "aws_caller_identity" "current" {
  count = var.aws_account_id == null ? 1 : 0
}

# ------------------------------------------------------------------------------
# 2. Evidence Locker Storage Bucket (Private, KMS Encrypted, WORM Object Lock)
# NOTE: Object Versioning alone is NOT WORM protection. Any user with
# s3:DeleteObjectVersion can delete versions. S3 Object Lock provides true WORM.
# ------------------------------------------------------------------------------
resource "aws_s3_bucket" "evidence_bucket" {
  bucket              = "lcc-${var.environment}-evidence-locker"
  force_destroy       = false # Prevent accidental deletion of court evidence
  object_lock_enabled = true  # Enables WORM immutability per Section 63 BSA

  tags = {
    Name        = "LCC Evidence Locker"
    Environment = var.environment
    DataClass   = "ConfidentialLegalEvidence"
    Compliance  = "BSA-Section63-WORM"
  }
}

# Enforce Versioning for Immutable Audit Trail
resource "aws_s3_bucket_versioning" "evidence_versioning" {
  bucket = aws_s3_bucket.evidence_bucket.id
  versioning_configuration {
    status = "Enabled"
  }
}

# Enforce S3 Object Lock Default Retention (Governance Mode + Legal Hold capable)
# - Governance Mode: Protects objects against deletion by operators without s3:BypassGovernanceRetention
# - Legal Hold: Enables case-specific litigation holds independent of retention periods
resource "aws_s3_bucket_object_lock_configuration" "evidence_object_lock" {
  bucket = aws_s3_bucket.evidence_bucket.id

  rule {
    default_retention {
      mode  = "GOVERNANCE"
      years = 3 # Baseline retention; active litigation holds override expiration
    }
  }
}

# Enforce Server-Side Encryption with Customer Managed Key (SSE-KMS)
resource "aws_s3_bucket_server_side_encryption_configuration" "evidence_encryption" {
  bucket = aws_s3_bucket.evidence_bucket.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.lcc_storage_key.arn
      sse_algorithm     = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

# Block ALL Public Access at Bucket Level
resource "aws_s3_bucket_public_access_block" "evidence_public_block" {
  bucket = aws_s3_bucket.evidence_bucket.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Strict TLS 1.3 / Minimum TLS 1.2 & Transport Security Bucket Policy
resource "aws_s3_bucket_policy" "evidence_bucket_policy" {
  bucket     = aws_s3_bucket.evidence_bucket.id
  depends_on = [aws_s3_bucket_public_access_block.evidence_public_block]

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "EnforceHTTPSRequestsOnly"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          aws_s3_bucket.evidence_bucket.arn,
          "${aws_s3_bucket.evidence_bucket.arn}/*"
        ]
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      },
      {
        Sid       = "EnforceMinimumTLSVersion"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          aws_s3_bucket.evidence_bucket.arn,
          "${aws_s3_bucket.evidence_bucket.arn}/*"
        ]
        Condition = {
          NumericLessThan = {
            "s3:TlsVersion" = 1.2
          }
        }
      },
      {
        Sid       = "DenyIncorrectEncryptionHeader"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:PutObject"
        Resource  = "${aws_s3_bucket.evidence_bucket.arn}/*"
        Condition = {
          StringNotEquals = {
            "s3:x-amz-server-side-encryption" = "aws:kms"
          }
        }
      }
    ]
  })
}

# ------------------------------------------------------------------------------
# 3. Video Recordings Storage Bucket (Private, Tiered Archival, Litigation Aware)
# ------------------------------------------------------------------------------
resource "aws_s3_bucket" "recordings_bucket" {
  bucket        = "lcc-${var.environment}-consultation-recordings"
  force_destroy = false

  tags = {
    Name        = "LCC Consultation Recordings"
    Environment = var.environment
    DataClass   = "PrivilegedAttorneyClientVideo"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "recordings_encryption" {
  bucket = aws_s3_bucket.recordings_bucket.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.lcc_storage_key.arn
      sse_algorithm     = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "recordings_public_block" {
  bucket = aws_s3_bucket.recordings_bucket.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Strict TLS Policy for Consultation Recordings
resource "aws_s3_bucket_policy" "recordings_bucket_policy" {
  bucket     = aws_s3_bucket.recordings_bucket.id
  depends_on = [aws_s3_bucket_public_access_block.recordings_public_block]

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "EnforceHTTPSRequestsOnly"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          aws_s3_bucket.recordings_bucket.arn,
          "${aws_s3_bucket.recordings_bucket.arn}/*"
        ]
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      },
      {
        Sid       = "EnforceMinimumTLSVersion"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          aws_s3_bucket.recordings_bucket.arn,
          "${aws_s3_bucket.recordings_bucket.arn}/*"
        ]
        Condition = {
          NumericLessThan = {
            "s3:TlsVersion" = 1.2
          }
        }
      }
    ]
  })
}

# Tiered Archival Lifecycle Policy:
# - Day 90: Transition to Glacier Instant Retrieval (GLACIER_IR) for fast legal review.
# - Day 365: Transition to Glacier Deep Archive for long-term evidentiary preservation.
# - NOTE: Automatic deletion is NOT configured to avoid destroying records under active litigation.
#   Deletion requires explicit workflow trigger verifying case closure and absence of litigation holds.
resource "aws_s3_bucket_lifecycle_configuration" "recordings_lifecycle" {
  bucket = aws_s3_bucket.recordings_bucket.id

  rule {
    id     = "archive-consultation-recordings-tiered"
    status = "Enabled"

    filter {}

    transition {
      days          = 90
      storage_class = "GLACIER_IR"
    }

    transition {
      days          = 365
      storage_class = "DEEP_ARCHIVE"
    }
  }
}

# ------------------------------------------------------------------------------
# 4. Encrypted Database Backups Bucket (Offsite Disaster Recovery Vault)
# ------------------------------------------------------------------------------
resource "aws_s3_bucket" "db_backups_bucket" {
  bucket              = "lcc-${var.environment}-db-backups"
  force_destroy       = false
  object_lock_enabled = true # WORM protection against ransomware & operator tampering

  tags = {
    Name        = "LCC Database Disaster Recovery Vault"
    Environment = var.environment
    DataClass   = "EncryptedPostgresBackups"
  }
}

resource "aws_s3_bucket_versioning" "db_backups_versioning" {
  bucket = aws_s3_bucket.db_backups_bucket.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_object_lock_configuration" "db_backups_object_lock" {
  bucket = aws_s3_bucket.db_backups_bucket.id

  rule {
    default_retention {
      mode = "COMPLIANCE" # Compliance Mode: Impossible for anyone (including root) to delete before retention
      days = 35           # Rolling 35-day immutable backup window
    }
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "db_backups_encryption" {
  bucket = aws_s3_bucket.db_backups_bucket.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.lcc_storage_key.arn
      sse_algorithm     = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "db_backups_public_block" {
  bucket = aws_s3_bucket.db_backups_bucket.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_policy" "db_backups_bucket_policy" {
  bucket     = aws_s3_bucket.db_backups_bucket.id
  depends_on = [aws_s3_bucket_public_access_block.db_backups_public_block]

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "EnforceHTTPSRequestsOnly"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          aws_s3_bucket.db_backups_bucket.arn,
          "${aws_s3_bucket.db_backups_bucket.arn}/*"
        ]
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      },
      {
        Sid       = "EnforceMinimumTLSVersion"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          aws_s3_bucket.db_backups_bucket.arn,
          "${aws_s3_bucket.db_backups_bucket.arn}/*"
        ]
        Condition = {
          NumericLessThan = {
            "s3:TlsVersion" = 1.2
          }
        }
      }
    ]
  })
}

# ------------------------------------------------------------------------------
# 5. IAM Role & Scoped Least-Privilege Policies for LCC Application Tasks
# ------------------------------------------------------------------------------
resource "aws_iam_role" "lcc_backend_role" {
  name = "lcc-${var.environment}-backend-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = ["ecs-tasks.amazonaws.com", "ec2.amazonaws.com"]
        }
      }
    ]
  })
}

resource "aws_iam_policy" "lcc_storage_access_policy" {
  name        = "lcc-${var.environment}-storage-access-policy"
  description = "Scoped S3, WORM Legal Hold, and KMS permissions for LCC backend workers"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3ObjectOperations"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:GetObjectVersion",
          "s3:ListBucket",
          "s3:PutObjectLegalHold",
          "s3:GetObjectLegalHold"
        ]
        Resource = [
          aws_s3_bucket.evidence_bucket.arn,
          "${aws_s3_bucket.evidence_bucket.arn}/*",
          aws_s3_bucket.recordings_bucket.arn,
          "${aws_s3_bucket.recordings_bucket.arn}/*",
          aws_s3_bucket.db_backups_bucket.arn,
          "${aws_s3_bucket.db_backups_bucket.arn}/*"
        ]
      },
      {
        Sid    = "KMSOperations"
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey",
          "kms:DescribeKey"
        ]
        Resource = [aws_kms_key.lcc_storage_key.arn]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "attach_storage_access" {
  role       = aws_iam_role.lcc_backend_role.name
  policy_arn = aws_iam_policy.lcc_storage_access_policy.arn
}
