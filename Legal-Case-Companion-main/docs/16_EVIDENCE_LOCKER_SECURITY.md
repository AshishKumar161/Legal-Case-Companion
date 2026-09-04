# Phase XIV: Secure Evidence Locker, Document Custody, Integrity & Controlled Sharing

## 1. Domain Separation & Philosophy

The Evidence Locker is a dedicated, high-security subsystem designed specifically for legally sensitive files exchanged between clients, lawyers, and authorized case participants.

```text
Ordinary Document (Document)          Collaborative Note (CaseNote)          Evidence (Evidence)
----------------------------          -----------------------------          -------------------
- Case research & pleadings           - Strategy and thoughts                - Legally sensitive exhibits
- Bulk storage                        - Visibility scopes                    - Immutable versioning
- Standard scanning                   - Internal workflow                    - Cryptographic SHA-256 hash
                                                                             - Append-only chain of custody
                                                                             - Controlled sharing & grants
                                                                             - Immediate revocation
                                                                             - Legal hold & retention
```

A standard case document does **not** automatically become Evidence. Evidence objects must be explicitly deposited into the vault through authorized workflows.

---

## 2. Threat Model & Technical Controls

| Threat | Attack Vector | Technical Control |
|---|---|---|
| **BOLA / IDOR Case Crossing** | User B attempts to access User A's evidence by guessing or supplying UUID. | `authorize_case_access` and `authorize_evidence_access` strictly verify membership. Unauthorized requests return `404 Not Found` to prevent existence discovery. |
| **BOLA / IDOR Cross-Lawyer** | Lawyer B attempts to view Lawyer A's shared evidence. | Evidence access requires an active, unrevoked, unexpired `EvidenceAccessGrant` for the caller's specific user ID. |
| **Unauthorized Sharing** | Client attempts to share evidence with arbitrary external users or unrelated lawyers. | Server validates that target user is an active participant (`CaseParticipant`) or assigned consultation lawyer for that specific case. Non-case users are rejected (`403 Forbidden`). |
| **Object Byte Tampering** | Cloud storage bytes modified out-of-band by insider or compromised credential. | Verification pipeline recalculates SHA-256 of stored bytes and compares against recorded digest. Any mismatch flags `TAMPER_DETECTED` and records an immutable `INTEGRITY_FAILED` custody event. |
| **Malware / Executable Upload** | Attacker uploads Trojan, executable, or macro-laden file disguised as evidence. | Content signature validation (`validate_file_magic_bytes`), filename traversal/double extension checks (`validate_filename_security`), and composite heuristic + ClamAV malware scanning before activation. |
| **Public S3 Exposure** | Leaked permanent storage links bypass platform authorization. | Private AWS S3 storage with AES-256 server-side encryption. URLs are generated on-demand with 60-second TTLs and safe `Content-Disposition` headers. |
| **Silent Version Overwrite** | User modifies file, losing original forensic evidence. | Previous versions are completely immutable. Every modification creates a new `EvidenceVersion` (Version N+1) with distinct SHA-256 and storage key. |
| **Premature / Hostile Deletion** | Spoliation of evidence during active dispute. | Technical `legal_hold` flag blocks deletion requests with `403 Forbidden`. Active `retention_until` dates are enforced. |
| **Privilege Escalation** | Viewer role modifies or deletes evidence. | `authorize_evidence_management` restricts mutations strictly to Evidence Creator, Case OWNER, or holders of explicit `MANAGE` grants. |
| **AI Retrieval Bypass** | LLM assistant retrieves private evidence without user consent. | AI retrieval strictly filters on user case and evidence access grants. |

---

## 3. Storage Architecture

```text
cases/
  {case_id}/
    evidence/
      {evidence_id}/
        versions/
          {version_id}
```

- **Non-guessable structure**: All components use application-generated UUIDv7 identifiers.
- **Path traversal prevention**: Filenames are sanitized and never used as storage keys.
- **Storage Separation**: PostgreSQL stores metadata, access grants, versions, SHA-256 digests, and custody events. Private AWS S3 stores encrypted raw bytes.

---

## 4. Cryptographic Integrity & Tamper Detection

1. **At Ingestion**:
   $$\text{digest} = \text{SHA-256}(\text{file\_bytes})$$
   Stored in `evidence_versions.sha256`. Scan status set to `PASSED`. Evidence marked `ACTIVE`.
2. **At Verification Time** (`POST /cases/{case_id}/evidence/{evidence_id}/verify-integrity`):
   - Fetches bytes from private storage.
   - Computes live SHA-256 digest.
   - Evaluates:
     $$\text{computed} \stackrel{?}{=} \text{recorded}$$
   - **Match**: Records `INTEGRITY_VERIFIED` custody event, sets `integrity_status = VERIFIED_MATCH`.
   - **Mismatch**: Records `INTEGRITY_FAILED` custody event, sets `integrity_status = TAMPER_DETECTED`, triggers high-priority security audit alert (`EVIDENCE_TAMPER_DETECTED`).

---

## 5. Chain of Custody Model

Every sensitive action appends an immutable event to `evidence_custody_events`:

```text
Event 1: UPLOADED (by Client A)
   ↓ previous_event_id
Event 2: SCAN_PASSED (SHA-256 recorded)
   ↓ previous_event_id
Event 3: SHARED (to Lawyer 1, access_level=DOWNLOAD)
   ↓ previous_event_id
Event 4: VIEWED (by Lawyer 1)
   ↓ previous_event_id
Event 5: DOWNLOADED (by Lawyer 1)
   ↓ previous_event_id
Event 6: INTEGRITY_VERIFIED (Matching SHA-256)
   ↓ previous_event_id
Event 7: ACCESS_REVOKED (by Client A)
```

Each event preserves:
- Action type (`EvidenceCustodyAction`)
- Actor User ID (`actor_user_id`)
- Timestamp (server-authoritative UTC)
- Version ID (`version_id`)
- Backward pointer (`previous_event_id`)
- Contextual metadata (hash snapshots, grantee IDs, revocation reasons)

---

## 6. Access Control Hierarchy

| Role / Grant Level | View Metadata | Inline Preview | Download Bytes | Upload New Version | Share / Revoke | Toggle Legal Hold | Delete Item |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Evidence Creator** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| **Case OWNER** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| **Grantee: VIEW** | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| **Grantee: DOWNLOAD** | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ |
| **Grantee: MANAGE** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| **Platform Admin** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| **Unauthorized User** | ✗ (404) | ✗ (404) | ✗ (404) | ✗ (404) | ✗ (404) | ✗ (404) | ✗ (404) |

---

## 7. Explicit Technical vs. Legal Disclaimer

The Evidence Locker provides **cryptographic integrity verification, tamper detection, and technical provenance logging**. It does **not** automatically guarantee statutory forensic certification or court admissibility under specific jurisdictional evidentiary statutes (e.g. Indian Evidence Act Section 65B) without the requisite formal administrative and procedural affidavits.
