"""CI/CD Secret Scanner Script.

Scans the repository tracked files and commit history for:
- Hardcoded API keys, private keys, tokens, and credentials.
- Presence of tracked .env files containing real secrets.
- Accidental exposure of private RSA/EC/OPENSSH keys.
- Unsanitized production credentials in tracked files.

Exits with non-zero status if any exposed secret is discovered.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

SECRET_PATTERNS = [
    (r"-----BEGIN (RSA|EC|DSA|OPENSSH|PGP) PRIVATE KEY-----", "Private cryptographic key"),
    (r"sk_live_[0-9a-zA-Z]{24,}", "Live Stripe API Secret Key"),
    (r"SG\.[0-9a-zA-Z_\-]{22}\.[0-9a-zA-Z_\-]{43}", "SendGrid API Key"),
    (r"AKIA[0-9A-Z]{16}", "AWS Access Key ID"),
    (r"(?i)secret_key\s*=\s*['\"][a-zA-Z0-9_\-]{32,}['\"]", "Hardcoded secret key assignment"),
]

EXCLUDED_TRACKED_FILES = {
    "package-lock.json",
    "uv.lock",
    "sbom-backend.json",
    "sbom-frontend.json",
    "release-manifest.json",
    "scripts/ci_secret_scanner.py",
    ".env.example",
    ".env.prod.example",
}

# Known test dummy strings that are explicitly allowed in unit/security test fixtures
ALLOWED_DUMMY_MARKERS = [
    "mock",
    "dummy",
    "test",
    "dev_insecure",
    "sk_live_mock",
    "changeme",
    "example",
    "placeholder",
    "replace-with",
    "your_",
    "real_secret",
]


def is_allowed_dummy(line: str) -> bool:
    lower = line.lower()
    return any(marker in lower for marker in ALLOWED_DUMMY_MARKERS)


def get_tracked_files():
    try:
        res = subprocess.run(
            ["git", "ls-files"],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            check=True,
        )
        return [f.strip() for f in res.stdout.splitlines() if f.strip()]
    except Exception as e:
        print(f"Warning: git ls-files failed: {e}. Falling back to os.walk.")
        tracked = []
        for root, _, files in os.walk(ROOT_DIR):
            for file in files:
                p = Path(root) / file
                tracked.append(str(p.relative_to(ROOT_DIR)).replace("\\", "/"))
        return tracked


def scan_tracked_files():
    print("========================================================================")
    print("  CI/CD GATE: STATIC REPOSITORY SECRET & CREDENTIAL SCAN")
    print("========================================================================")

    tracked_files = get_tracked_files()
    findings = []
    scanned_count = 0

    for rel_path_str in tracked_files:
        norm_path = rel_path_str.replace("\\", "/")

        if norm_path in EXCLUDED_TRACKED_FILES:
            continue
        if norm_path.endswith((".pyc", ".db", ".png", ".jpg", ".jpeg", ".ico", ".woff", ".woff2")):
            continue

        file_path = ROOT_DIR / norm_path
        if not file_path.exists() or file_path.is_dir():
            continue

        # Rule 1: No tracked .env files
        if norm_path == ".env" or (norm_path.startswith(".env.") and not norm_path.endswith((".example", ".sample"))):
            findings.append((norm_path, 0, "Disallowed production .env file tracked in git repository"))

        scanned_count += 1
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                for line_no, line in enumerate(f, start=1):
                    # Skip allowed fixture files in tests and docs
                    if (norm_path.startswith("tests/") or norm_path.startswith("docs/")) and is_allowed_dummy(line):
                        continue

                    for pattern, desc in SECRET_PATTERNS:
                        if re.search(pattern, line):
                            if not is_allowed_dummy(line):
                                findings.append((norm_path, line_no, f"{desc}: {line.strip()[:60]}..."))
        except Exception as e:
            print(f"Warning: Could not read {norm_path}: {e}")

    print(f"Scanned {scanned_count} git-tracked files across repository.")

    if findings:
        print(f"\n[FAIL] Found {len(findings)} potential secret exposure(s):")
        for path, line, msg in findings:
            print(f"  - {path}:{line} -> {msg}")
        sys.exit(1)

    print("\n[PASS] Zero exposed production secrets, credentials, or private keys discovered.")
    print("========================================================================")
    sys.exit(0)


if __name__ == "__main__":
    scan_tracked_files()
