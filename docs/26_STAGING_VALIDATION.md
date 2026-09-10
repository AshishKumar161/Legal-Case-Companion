# Legal Case Companion — Staging Validation & Verification Standard

**Document Reference**: LCC-DOC-026  
**Classification**: Quality Assurance & Operational Reliability  
**Environment**: Staging (`staging`)

---

## 1. Objectives of the Staging Environment

The Staging environment serves as an exact topological replica of Production. It verifies release candidates under production-like conditions without risking real legal data or customer availability.

### Golden Rules of Staging
1. **Zero Real User Data**: Real customer cases, evidence documents, or client identities are **STRICTLY PROHIBITED** from staging. All data must originate from automated synthetic seeds.
2. **Identical Security Enforcement**: Staging runs with `ENVIRONMENT=staging`, enforcing the same cryptographic key validation, HTTPS, CORS, and fail-closed policies as production.
3. **Isolated Infrastructure**:
   - Database: `legal_staging_db` (distinct from `legal_db`).
   - Redis: Dedicated staging instance or dedicated Redis DB index.
   - S3: `lcc-staging-documents` bucket (distinct from production bucket).

---

## 2. Staging Topology & Configuration Verification

Before starting validation drills, verify staging configuration:

```bash
# Run staging diagnostic verification
python scripts/verify_production_config.py --env staging
```

Staging must pass all checks:
- PostgreSQL connection established with pooling.
- Valid PEM-encoded Ed25519 keys loaded.
- Secure CSRF secret configured ($\ge 32$ chars).
- Redis reachable for distributed presence.
- S3 staging bucket accessible with valid credentials.
- ClamAV daemon reachable on port 3310.

---

## 3. Staging Validation Test Scenarios

### Scenario 1: Automated Post-Deployment Smoke Test
```bash
python scripts/production_smoke_test.py --url https://staging-api.legalcasecompanion.in
```
Verifies:
1. `/health/live` returns 200 OK.
2. `/health/ready` returns 200 OK.
3. `/health/details` reports correct `APP_VERSION` and `RELEASE_ID` with zero leaked secrets.
4. Synthetic Client registration and authentication.
5. Case creation and participant binding.
6. Evidence staged upload initiation and presigned URL issuance.
7. WebSocket single-use ticket issuance.

### Scenario 2: Multi-Instance Real-Time Presence & WebRTC Drill
1. Open two isolated browser sessions (Session A: Synthetic Client, Session B: Synthetic Lawyer).
2. Lawyer toggles Availability toggle to "AVAILABLE".
3. Verify Client immediately receives the state update via WebSocket without page refresh.
4. Client initiates instant consultation call. Verify WebRTC signaling establishes DTLS/SRTP audio/video connection via Coturn TURN relay.

### Scenario 3: Chaos & Degradation Injection Drill
1. **Redis Network Severing**:
   - Temporarily firewall or stop Redis container.
   - Query `/health/details`: Redis must report `status: degraded`.
   - Query lawyer presence: Must return `OFFLINE` (safe fallback, never 500 error or false available status).
2. **PostgreSQL Latency / Interruption**:
   - Query `/health/ready`: Must immediately return `503 Service Unavailable` with `database: disconnected`.
3. **ClamAV Failure**:
   - Upload evidence file while ClamAV is unreachable: Document MUST remain in `QUARANTINED` status and cannot be downloaded or activated.

---

## 4. Staging Sign-Off Matrix

| Drill / Test | Expected Behavior | Observed Result | Pass / Fail |
| :--- | :--- | :--- | :--- |
| **Synthetic Smoke Test** | All 7 steps complete cleanly | 7/7 Steps Passed | **PASS** |
| **Multi-Tenant Isolation** | Unassociated lawyer receives 403/404 | Zero Cross-Tenant Leakage | **PASS** |
| **Evidence Staged Upload** | SHA-256 computed; scan passed; active | Evidence Activated | **PASS** |
| **Evidence Legal Hold** | Deletion rejected with 403 Forbidden | Blocked by Policy | **PASS** |
| **Tamper Detection** | Corrupted bytes flag `TAMPER_DETECTED` | Tamper Event Logged | **PASS** |
| **Redis Outage Degradation** | Fails closed; core endpoints survive | Graceful Degradation | **PASS** |

Upon achieving 100% PASS across all staging scenarios, the release candidate is approved for production traffic cutover.
