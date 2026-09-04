# Phase XX: Public Onboarding Readiness & Gating

## Overview
LCC prepares the platform architecture for eventual public internet onboarding while enforcing strict staged gates. Public self-registration is never enabled by default; it requires affirmative human launch gate execution.

## Onboarding Modes
1. `CONTROLLED`: Stage 2 Pilot constraints active (250 clients, 100 advocates, allowlisted Bar cohorts).
2. `INVITE_ONLY`: Pre-authorized registration tokens or domain allowlist required.
3. `VERIFIED_PROFESSIONAL`: Dedicated intake for State Bar Council verified advocates.
4. `PUBLIC`: General public registration (disabled until formal launch approval).

## Mandatory Onboarding Gates
No user can achieve `ACTIVE` status without satisfying:
- Email verification via HMAC-signed time-limited tokens.
- Terms of Service & Privacy Notice explicit version acceptance.
- Professional verification for advocates (Bar Council enrollment number, State Bar certificate).
- Anti-abuse verification (disposable email domain checks, IP velocity limits, CAPTCHA on anomaly).
