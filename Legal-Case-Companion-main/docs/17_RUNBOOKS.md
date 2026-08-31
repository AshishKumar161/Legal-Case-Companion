# Operational Runbooks

## Overview
This document contains actionable procedures for managing the Legal Case Companion backend in production.

## 1. Deployment & Rollback (Render)

### Deployment
Deployment is managed via Render auto-deploys tied to the `main` branch.
1. Merge pull request to `main` (requires passing CI/CD tests).
2. Monitor deployment logs on Render dashboard.
3. Validate `/health` and `/ready` endpoints after deployment.

### Rollback
If a deployment introduces a critical regression (P0/P1):
1. Navigate to the Render Dashboard > "lcc-backend" web service.
2. Under "Events", locate the previously successful deployment.
3. Click **Rollback to this deploy**.
4. Monitor `/health` to confirm the previous image is active.
> [!WARNING]
> If the bad deployment included a database migration, you MUST manually downgrade the database using Render Shell (`alembic downgrade <revision>`) BEFORE rolling back the application code to avoid schema mismatches.

## 2. Security Incident Response

### Compromised JWT Secret
1. Generate a new Ed25519 key pair locally: `openssl genpkey -algorithm ed25519 -out private.pem`
2. Update the `JWT_PRIVATE_KEY` and `JWT_PUBLIC_KEY` environment variables in the Render Dashboard.
3. Trigger a manual deploy to cycle all active backend instances.
> [!IMPORTANT]
> **Impact**: All users will be instantly logged out and must re-authenticate.

### S3 Document Leak / Compromise
1. Immediately revoke the compromised IAM User credentials via AWS Console.
2. In Render, rotate `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`.
3. If specific documents were exposed, cycle their S3 object ACLs or move them to a quarantine bucket using AWS CLI.
4. Check AWS CloudTrail logs to identify the extent of the unauthorized access.

### AI Leakage / Prompt Injection Bypass
1. Temporarily disable the AI retrieval endpoint via Render Environment Variable (if feature flag exists) or block the route at the API gateway layer.
2. Audit the specific `document_chunks` and `cases` accessed by the malicious user.
3. Roll back or ban the offending user account.

## 3. Database Restoration

### Render Managed PostgreSQL Restore
1. Navigate to the "lcc-db" PostgreSQL instance in the Render Dashboard.
2. Select "Restores" or "Backups".
3. Choose the Point-In-Time (PITR) timestamp prior to the corruption event.
4. Restore to a *new* database instance (Render requirement).
5. Once provisioned, update `DATABASE_URL` in the `lcc-backend` service to point to the new DB.
6. Verify application connectivity via `/ready`.
7. Retain the corrupted instance for forensics before deletion.

## 4. Secret Rotation Schedule
- **JWT Keys**: Rotate every 6 months.
- **AWS IAM Keys**: Rotate every 90 days.
- **Payment Webhook Secret**: Rotate annually or upon staff offboarding.
