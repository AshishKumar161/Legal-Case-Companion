# Legal Case Companion (LCC) - Privacy Notice

**Effective Date:** September 5, 2026  
**Jurisdiction:** Republic of India  
**Applicable Framework:** Digital Personal Data Protection Act, 2023 (DPDPA 2023) & Information Technology Act, 2000

---

## 1. Introduction & Operational Scope
Legal Case Companion ("LCC", "Platform", "we", "us") operates as a secure digital case management and consultation intermediary. This Privacy Notice governs the collection, processing, storage, and erasure of personal data provided by litigants ("Clients"), practicing legal professionals ("Advocates"), and administrative users.

LCC operates under a strict **Zero-Knowledge Evidence Architecture**: internal support staff, platform administrators, and analytics workers are technically precluded from querying, reading, or inspecting privileged case files, litigation notes, or confidential evidence locker contents.

---

## 2. Categories of Data Collected

### 2.1 Identity & Verification Data
* **Clients:** Full name, verified mobile number, email address, general dispute jurisdiction (State/District).
* **Advocates:** Full name, State Bar Council enrollment number, year of enrollment, verified digital enrollment certificate, practice areas, language proficiencies, bank payout account details (IFSC, Account Number).

### 2.2 Case Workspace & Legal Operational Data
* Case titles, synopsis, party names (as appearing in public court records), Court Case Numbers (CNR), hearing dates, court orders, and case deadlines.
* Encrypted evidence locker files (PDFs, images, scanned petitions).

### 2.3 Financial & Transactional Data
* Consultation payment records, gross transaction values, statutory 18% GST (SAC 9982), platform fees, payment gateway identifiers (Razorpay / Cashfree tokens). LCC does not store raw credit/debit card numbers or net banking credentials.

---

## 3. Purpose of Processing & Legal Basis
Data is processed strictly for:
1. Facilitating lawyer discovery and scheduling video/audio consultations.
2. Maintaining client case workspaces and evidence lockers.
3. Synchronizing public court records from authorized eCourts registries.
4. Generating server-authoritative GST tax invoices and advocate payout disbursements.
5. Fulfilling statutory accounting and regulatory obligations under Indian tax laws.

---

## 4. Zero-Trust Access & Privacy Isolation
* **Support Personnel Access:** Support operators have access only to ticket metadata, delivery logs, and communication threads. Internal operator notes are strictly isolated and never shared with counterparties. Support staff cannot query or access client legal documents.
* **Attorney-Client Privilege:** Communications between clients and advocates conducted via the platform remain privileged under Sections 126-129 of the Indian Evidence Act, 1872 (and corresponding provisions of the Bharatiya Sakshya Adhiniyam, 2023).
* **Analytics Telemetry:** Telemetry logs collect aggregated workflow progression (funnel conversions, latencies) with zero PII, raw CNRs, or litigation text.

---

## 5. Data Storage, Security & Residency
* **Data Residency:** 100% of user data and evidence records are hosted on secure Indian cloud infrastructure (AWS Mumbai / Azure Central India).
* **Encryption Standards:** All data in transit is encrypted using TLS 1.3. All evidence records and backups are encrypted at rest using AES-256 with envelope key rotation.

---

## 6. Data Subject Rights (DPDPA 2023)
Users retain statutory rights to:
1. **Right to Access:** Request a consolidated export of all personal information and uploaded case records.
2. **Right to Correction:** Correct inaccurate profile or enrollment information.
3. **Right to Erasure:** Request complete account closure and cryptographic destruction of uploaded documents, subject only to statutory tax retention periods.
4. **Right to Nominate:** Nominate a representative in the event of death or incapacity.

---

## 7. Data Protection Officer (DPO) & Grievance Redressal
In accordance with Rule 3(2) of the Information Technology (Intermediary Guidelines and Digital Media Ethics Code) Rules, 2021:

* **Grievance Officer:** Head of Trust & Privacy  
* **Email:** `grievance-officer@lcc.internal`  
* **Physical Address:** Legal Case Companion Operations, Connaught Place, New Delhi 110001, India  
* **Response SLA:** Acknowledgment within 24 hours; resolution within 15 days.
