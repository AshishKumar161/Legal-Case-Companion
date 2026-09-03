#!/usr/bin/env python3
"""
Legal Case Companion (LCC) — Production Configuration & Operational Diagnostics CLI
Phase 30: Validates environment variables, secrets, database connectivity, storage,
antivirus daemon, TURN relay, and payments without leaking sensitive values.
"""

import argparse
import os
import socket
import sys
import time
from urllib.parse import urlparse

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import create_engine, text



def mask_secret(value: str | None) -> str:
    if not value:
        return "[MISSING]"
    if "<set-in-environment>" in value or "replace" in value.lower():
        return "[PLACEHOLDER / UNCONFIGURED]"
    if len(value) <= 8:
        return "[PRESENT] (****)"
    return f"[PRESENT] (len={len(value)}, prefix={value[:4]}...)"


def check_tcp_socket(host: str, port: int, timeout_sec: float = 3.0) -> tuple[bool, str]:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout_sec)
            s.connect((host, port))
            return True, "reachable"
    except Exception as e:
        return False, str(e)


def main():
    parser = argparse.ArgumentParser(description="LCC Production Readiness Diagnostics")
    parser.add_argument(
        "--env",
        choices=["development", "test", "production"],
        help="Target environment to validate against",
    )
    args = parser.parse_args()

    # Import application settings
    from app.core.config import settings

    target_env = args.env or settings.ENVIRONMENT
    print("=" * 72)
    print(f"  LEGAL CASE COMPANION — OPERATIONAL CONFIGURATION DIAGNOSTICS")
    print(f"  Target Environment: {target_env.upper()} (Current Settings: {settings.ENVIRONMENT})")
    print("=" * 72)

    issues: list[str] = []
    warnings: list[str] = []

    # 1. Core Secrets & Cryptographic Keys
    print("\n[1] Authentication & Cryptographic Keys:")
    priv_status = mask_secret(settings.JWT_PRIVATE_KEY)
    pub_status = mask_secret(settings.JWT_PUBLIC_KEY)
    csrf_status = mask_secret(settings.CSRF_SECRET_KEY)

    print(f"  - JWT_PRIVATE_KEY (Ed25519) : {priv_status}")
    print(f"  - JWT_PUBLIC_KEY (Ed25519)  : {pub_status}")
    print(f"  - CSRF_SECRET_KEY           : {csrf_status}")

    if target_env == "production":
        if "[MISSING]" in priv_status or "[PLACEHOLDER" in priv_status:
            issues.append("Production requires a valid PEM-encoded Ed25519 JWT_PRIVATE_KEY.")
        if "[MISSING]" in pub_status or "[PLACEHOLDER" in pub_status:
            issues.append("Production requires a valid PEM-encoded Ed25519 JWT_PUBLIC_KEY.")
        if "[MISSING]" in csrf_status or "[PLACEHOLDER" in csrf_status:
            issues.append("Production requires a secure random CSRF_SECRET_KEY.")

    # 2. Database Connectivity & Pooling
    print("\n[2] Database & Storage Engine:")
    db_url_parsed = urlparse(settings.DATABASE_URL)
    print(f"  - Scheme: {db_url_parsed.scheme}, Host: {db_url_parsed.hostname or 'local'}, DB: {db_url_parsed.path}")
    print(f"  - Pool Size: {settings.DB_POOL_SIZE}, Max Overflow: {settings.DB_MAX_OVERFLOW}")

    try:
        t0 = time.perf_counter()
        engine = create_engine(settings.DATABASE_URL)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        latency_ms = (time.perf_counter() - t0) * 1000.0
        print(f"  - Connectivity: [SUCCESS] (ping latency: {latency_ms:.2f}ms)")
    except Exception as e:
        print(f"  - Connectivity: [FAILED] ({e})")
        issues.append(f"Database connection failed: {e}")

    # 3. Private S3 Document Storage
    print("\n[3] Private Document Storage (AWS S3):")
    print(f"  - Bucket: {settings.AWS_S3_BUCKET_NAME}")
    print(f"  - Region: {settings.AWS_REGION}")
    print(f"  - Access Key: {mask_secret(settings.AWS_ACCESS_KEY_ID)}")
    print(f"  - Secret Key: {mask_secret(settings.AWS_SECRET_ACCESS_KEY)}")
    print(f"  - Webhook Secret: {mask_secret(settings.AWS_WEBHOOK_SECRET)}")

    if target_env == "production":
        if not settings.AWS_S3_BUCKET_NAME:
            issues.append("AWS_S3_BUCKET_NAME is required in production.")
        if not settings.AWS_WEBHOOK_SECRET:
            warnings.append("AWS_WEBHOOK_SECRET should be set for async malware scanning callbacks.")

    # 4. Malware Scanner (ClamAV Daemon)
    print("\n[4] Antivirus & Malware Scanner (ClamAV):")
    if settings.CLAMAV_HOST:
        clam_ok, clam_msg = check_tcp_socket(settings.CLAMAV_HOST, settings.CLAMAV_PORT)
        print(f"  - Daemon: {settings.CLAMAV_HOST}:{settings.CLAMAV_PORT} -> {'[REACHABLE]' if clam_ok else '[UNREACHABLE]'} ({clam_msg})")
        print(f"  - Fail-Closed Policy: [ACTIVE] (Unreachable daemon keeps documents QUARANTINED)")
        if not clam_ok and target_env == "production":
            warnings.append(f"ClamAV daemon at {settings.CLAMAV_HOST}:{settings.CLAMAV_PORT} is unreachable: {clam_msg}")
    else:
        print("  - Daemon: [NOT CONFIGURED] (Operating with Heuristic Signature Scanner)")
        if target_env == "production":
            warnings.append("CLAMAV_HOST is not configured; production deployments should enable ClamD.")

    # 5. WebRTC TURN Relay (Coturn)
    print("\n[5] WebRTC NAT Traversal (TURN Relay):")
    print(f"  - Server URL: {settings.TURN_SERVER_URL or '[NOT CONFIGURED]'}")
    print(f"  - Username  : {mask_secret(settings.TURN_USERNAME)}")
    print(f"  - Credential: {mask_secret(settings.TURN_CREDENTIAL)}")
    if target_env == "production" and not settings.TURN_SERVER_URL:
        warnings.append("TURN_SERVER_URL is unconfigured; video calls across strict NAT/firewalls may fail.")

    # 6. Payment Gateway (Stripe)
    print("\n[6] Payments & Webhooks (Stripe):")
    stripe_key_status = mask_secret(settings.STRIPE_API_KEY)
    stripe_wh_status = mask_secret(settings.STRIPE_WEBHOOK_SECRET)
    print(f"  - STRIPE_API_KEY       : {stripe_key_status}")
    print(f"  - STRIPE_WEBHOOK_SECRET: {stripe_wh_status}")

    if target_env == "production":
        if "[MISSING]" in stripe_key_status or "[PLACEHOLDER" in stripe_key_status:
            issues.append("STRIPE_API_KEY is required in production.")
        if "[MISSING]" in stripe_wh_status or "[PLACEHOLDER" in stripe_wh_status:
            issues.append("STRIPE_WEBHOOK_SECRET is required in production.")

    # 7. Native Video & LiveKit SFU
    print("\n[7] Native Video SFU (LiveKit):")
    livekit_url_status = mask_secret(settings.LIVEKIT_URL)
    livekit_key_status = mask_secret(settings.LIVEKIT_API_KEY)
    livekit_sec_status = mask_secret(settings.LIVEKIT_API_SECRET)
    print(f"  - LIVEKIT_URL       : {settings.LIVEKIT_URL or '[NOT CONFIGURED]'}")
    print(f"  - LIVEKIT_API_KEY   : {livekit_key_status}")
    print(f"  - LIVEKIT_API_SECRET: {livekit_sec_status}")
    if target_env == "production":
        if not settings.LIVEKIT_URL:
            warnings.append("LIVEKIT_URL is not configured; production video will require LiveKit SFU for multi-party reliability.")
        if not settings.LIVEKIT_API_KEY or not settings.LIVEKIT_API_SECRET:
            warnings.append("LiveKit API credentials missing; server cannot issue signed LiveKit room tokens.")

    # 8. Local Recording Storage Persistence
    print("\n[8] Consultation Video Recording Storage:")
    rec_path = os.path.abspath(settings.LOCAL_RECORDING_STORAGE_PATH)
    rec_exists = os.path.exists(rec_path)
    rec_writable = os.access(rec_path, os.W_OK) if rec_exists else False
    print(f"  - Storage Path      : {rec_path}")
    print(f"  - Directory Exists  : {'[YES]' if rec_exists else '[NO - WILL BE CREATED ON STARTUP]'}")
    print(f"  - Writable          : {'[YES]' if rec_writable else '[NOT CHECKED / CREATED ON INIT]'}")
    if target_env == "production":
        print(f"  - Durability Policy : Requires named volume (Docker: app_storage) or attached persistent disk (Render).")

    # 9. Operational CORS & URL Bindings
    print("\n[9] Network & CORS:")
    print(f"  - FRONTEND_URL: {settings.FRONTEND_URL}")
    print(f"  - CORS Origins: {settings.BACKEND_CORS_ORIGINS}")
    if "*" in str(settings.BACKEND_CORS_ORIGINS):
        issues.append("Wildcard '*' CORS origin is prohibited in authenticated production environments.")

    # Summary
    print("\n" + "=" * 72)
    print("  DIAGNOSTICS SUMMARY")
    print("=" * 72)
    print(f"  Critical Issues: {len(issues)}")
    print(f"  Warnings       : {len(warnings)}")

    for issue in issues:
        print(f"  [ERROR]   {issue}")
    for warning in warnings:
        print(f"  [WARNING] {warning}")

    if issues:
        print("\nResult: [FAILED] — Configuration has critical blocking issues for target environment.")
        return 1

    print("\nResult: [PASSED] — Configuration satisfies environment readiness requirements.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
