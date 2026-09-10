# Legal Case Companion (LCC) - Document Retention & Destruction Policy

**Effective Date:** September 5, 2026  
**Framework:** DPDPA 2023, Information Technology (Reasonable Security Practices and Procedures and Sensitive Personal Data or Information) Rules, 2011

---

## 1. Storage & Encryption Standards
All litigation documents, scanned evidence, court notices, and consultation notes uploaded to LCC Evidence Lockers are subject to:
* **AES-256 Envelope Encryption:** Each case file is encrypted with a unique data key prior to persisting to cloud object storage.
* **Integrity Hashing:** SHA-256 cryptographic checksums are recorded on ingestion to guarantee chain-of-custody and prevent tampering.

---

## 2. Retention Periods by Category

| Record Type | Active Matter Period | Post-Closure Retention | Deletion Mechanism |
| :--- | :--- | :--- | :--- |
| **Privileged Client Evidence** | Entire duration of matter | 90 days post matter closure | Automatic cryptographic shredding |
| **Official Court Orders / Judgments** | Indefinite | 7 years (statutory alignment) | User-controlled manual purge |
| **Financial Invoices & Receipts** | Indefinite | 8 years (mandatory under Indian Income Tax & GST laws) | Immutable financial archive |
| **Telemetry & Latency Logs** | 30 rolling days | 90 days rolling aggregates | Automated TTL partition drops |

---

## 3. Cryptographic Deletion Protocols
When a user initiates document deletion or exercises their Right to Erasure:
1. The unique AES-256 encryption key associated with the file is irreversibly deleted from Key Management Service (KMS).
2. The underlying physical storage object is scheduled for immediate overwrite.
3. An immutable audit record is logged in the `AuditEvent` ledger noting the deletion timestamp and user identity (without retaining document content).
