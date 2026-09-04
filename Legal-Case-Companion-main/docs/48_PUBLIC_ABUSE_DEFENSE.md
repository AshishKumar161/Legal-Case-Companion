# Phase XX: Public Abuse Resilience & Anti-Automation Defense

## Overview
As LCC transitions from allowlisted pilot environments to public internet traffic, automated abuse, scraping, fake consultation bookings, and credential attacks must be mitigated without invasive surveillance.

## Multi-Layered Defense Controls
1. **Disposable Email Blocking**: Real-time evaluation against disposable and temporary mailbox domains (`mailinator.com`, `guerrillamail.com`, etc.).
2. **Consultation Request Velocity Limits**: Clients are capped at a maximum of 5 concurrent pending/unconfirmed consultation requests to prevent denial-of-service spamming against advocate schedules.
3. **Evidence Upload Throttling**: Velocity limits on file uploads to the Evidence Locker to mitigate storage exhaustion and malware queue congestion.
4. **Adaptive Rate Limiting**: Tiered endpoint throttling via Redis-backed SlowAPI middleware:
   - Registration: 5 requests / minute
   - Login / Token Refresh: 15-20 requests / minute
   - Consultation Booking: 10 requests / minute
   - AI Research: Daily budget quotas per user
5. **Privacy-Preserving Audit**: Reputation scoring and anomalous velocity alerts are recorded using pseudonymous actor identifiers with zero sensitive case content stored in abuse telemetry.
