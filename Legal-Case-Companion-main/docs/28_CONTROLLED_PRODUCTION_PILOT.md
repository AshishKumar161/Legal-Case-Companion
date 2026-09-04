# 28 — CONTROLLED PRODUCTION PILOT OPERATING MODEL

## 1. Objective & Scope

This runbook establishes the formal operating model for the **Controlled Production Pilot** of Legal Case Companion (LCC). The objective is to safely onboard verified real-world users (advocates and litigants) in India without exposing the platform to unconstrained public exposure, capacity exhaustion, or unmonitored regulatory risk.

---

## 2. Operating Model & Configuration Enforcements

The pilot operating model is governed by explicit configuration directives:

| Configuration Key | Pilot Default | Production Rule | Purpose |
| :--- | :--- | :--- | :--- |
| `PILOT_MODE` | `True` | Must be explicit `True` in pilot environments | Enables pilot gating across all endpoints |
| `PILOT_ALLOWLIST_ENABLED` | `True` | Strictly enforced | Rejects registrations not approved on allowlist |
| `PILOT_SIGNUP_ENABLED` | `True` | Can be toggled to `False` immediately | Circuit breaker to freeze onboarding |
| `PILOT_MAX_CLIENTS` | `100` | Hard threshold | Prevents unmetered client enrollment |
| `PILOT_MAX_LAWYERS` | `50` | Hard threshold | Caps lawyer onboarding for high-touch verification |
| `PILOT_START_TIME` | ISO timestamp | Optional window start | Rejects activity prior to formal pilot kickoff |
| `PILOT_END_TIME` | ISO timestamp | Optional window end | Concludes pilot period |
| `PILOT_GLOBAL_READ_ONLY` | `False` | Emergency toggle | Freezes all state mutations (`503 EMERGENCY_READ_ONLY`) |
| `PILOT_DISABLED_FEATURES` | `[]` | JSON array of feature slugs | Disables selected high-risk features dynamically |

---

## 3. Allowlist Governance & Onboarding Playbook

### 3.1 Eligibility Criteria
1. **Lawyers**: Must possess an active Bar Council Enrollment Number verified manually by the compliance team against state bar council directories.
2. **Clients**: Must be pre-identified pilot participants or referred by enrolled pilot advocates.

### 3.2 Enrollment Procedure
1. Authorized operator holding `PILOT_GOVERNANCE` permission executes:
   ```bash
   curl -X POST https://api.legalcasecompanion.in/api/v1/pilot/allowlist \
     -H "Authorization: Bearer <OPERATOR_TOKEN>" \
     -H "Content-Type: application/json" \
     -d '{
       "identifier": "advocate.sharma@delhibar.in",
       "identifier_type": "EMAIL",
       "role_target": "LAWYER",
       "valid_until": "2026-12-31T23:59:59Z",
       "notes": "Enrolled under Bar Association Pilot Cohort A"
     }'
   ```
2. The allowlist engine logs an immutable `AuditEvent` (`PILOT_ALLOWLIST_ENTRY_ADDED`).
3. The user registers via the frontend `/register` route. If the email is not present on the allowlist, the API returns `403 Forbidden` (`PILOT_NOT_ALLOWLISTED`).

### 3.3 Emergency De-Enrollment
To revoke an allowlist entry immediately:
```bash
curl -X DELETE https://api.legalcasecompanion.in/api/v1/pilot/allowlist/<ENTRY_ID> \
  -H "Authorization: Bearer <OPERATOR_TOKEN>"
```

---

## 4. Emergency Circuit Breakers

### 4.1 Onboarding Freeze
If suspicious user creation patterns or infrastructure load spikes are observed:
```bash
# Set PILOT_SIGNUP_ENABLED=False in environment and reload API workers
docker compose -f docker-compose.prod.yml exec backend sh -c 'export PILOT_SIGNUP_ENABLED=False'
```
*Effect*: Existing users remain fully operational; all new registrations receive `403 Forbidden` (`PILOT_SIGNUP_DISABLED`).

### 4.2 Global Read-Only Mode
During database maintenance, storage corruption investigation, or active security incidents:
```bash
# Set PILOT_GLOBAL_READ_ONLY=True in environment
```
*Effect*:
- All `GET` requests proceed normally (users can read case metadata, view scheduled consultations).
- All `POST`, `PUT`, `PATCH`, `DELETE` requests receive `503 Service Unavailable` (`EMERGENCY_READ_ONLY`).
- Exempted routes: `/api/v1/auth/logout`, `/api/v1/incidents/*`, `/api/v1/pilot/*`.

### 4.3 Feature Disablement
To temporarily disable instant video consultations or file uploads without taking down the platform:
```bash
PILOT_DISABLED_FEATURES='["instant_consultation", "evidence_upload"]'
```

---

## 5. Daily SRE Pilot Review Checklist

Each day during the pilot, the designated SRE lead executes:
1. `GET /api/v1/pilot/status` — Review client and lawyer capacity utilization.
2. `GET /api/v1/pilot/slos` — Confirm API availability $\ge 99.9\%$ and p95 latency $< 500\text{ ms}$ with sample confidence.
3. `GET /api/v1/pilot/alerts` — Verify zero `FIRING` alerts.
4. `GET /api/v1/pilot/funnel` — Track client and lawyer journey conversion drop-offs.
5. `GET /api/v1/pilot/costs` — Audit infrastructure unit cost burn rate.
6. `POST /api/v1/data-quality/reconcile?repair=false` — Audit data integrity and stale leases.
7. `GET /api/v1/incidents?status=INVESTIGATING` — Verify all open incidents are assigned and tracked.

---

## 6. Phase XIX Stage 2 Capacity Expansion

Following successful validation in Stage 1, capacity is expanded under formal operational approval:
- `PILOT_MAX_CLIENTS`: Raised from `100` to `250`.
- `PILOT_MAX_LAWYERS`: Raised from `50` to `100`.
- `PILOT_ALLOWLIST_ENABLED`: Remains strictly `True`.
- Status: **`EXPAND PILOT WITH CONDITIONS`** (ADR-007).
