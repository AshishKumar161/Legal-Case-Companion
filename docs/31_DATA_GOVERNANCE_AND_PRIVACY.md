# 31 — DATA GOVERNANCE, PRIVACY & COMPLIANCE MATRIX

## 1. Compliance Principles & Disclaimer

> [!CAUTION]
> **LEGAL NOTICE & COMPLIANCE SEPARATION**:
> Technical controls implemented in software **DO NOT EQUATE TO REGULATORY COMPLIANCE** under the Digital Personal Data Protection (DPDP) Act 2023, Information Technology Act 2000, or Bar Council of India (BCI) rules. 
> 
> This document explicitly separates:
> 1. **Technical Controls** (engineered and verified in code).
> 2. **Organizational Requirements** (internal operational policies, training, and staffing).
> 3. **Legal Review Requirements** (mandatory external legal counsel determinations).

---

## 2. Comprehensive Compliance Separation Matrix

| Area | Technical Control (Engineered) | Organizational Requirement | Legal Review Required | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Personal Data Inventory** | PII inventory mapped; fields classified in models; log scrubber redacts credentials, tokens, and PII. | Maintain physical asset registry and data flow diagrams. | Review data classifications against DPDP Act Section 2 definitions. | **TECHNICAL READY (Legal Review Pending)** |
| **Purpose Limitation** | Case and client data access strictly restricted to assigned participants via RBAC and BOLA checks. | Establish employee access policy and confidentiality agreements. | Review customer consent forms and purpose descriptions in privacy notice. | **TECHNICAL READY (Org In Progress)** |
| **Collection Minimization** | Registration accepts only email, phone, role; no unneeded KYC collected upfront. | Periodically audit registration forms and analytics payload schemas. | Counsel review of mandatory vs optional fields under DPDP rules. | **TECHNICAL READY (Legal Review Pending)** |
| **Retention Schedules** | Evidence versions tracked; `legal_hold` flag halts scheduled deletion during litigation. | Formulate enterprise document retention policy with practice-area tiers. | Legal confirmation of statutory retention periods under Indian Evidence Act. | **TECHNICAL READY (Policy Required)** |
| **Account Deletion & Right to Erasure** | `DELETE /api/v1/auth/account` anonymizes email/name, revokes sessions, soft-deletes record, preserves statutory audit trail. | Support team verify identity prior to fulfilling manual erasure requests. | Legal determination on statutory conflicts (Tax, BCI, Criminal Procedure Code). | **TECHNICAL READY (Legal Review Pending)** |
| **Correction & Update** | Self-service profile editing for contact and practice details in `/api/v1/profiles`. | Verification of updated Bar Council enrollment before status re-approval. | Counsel review of name-change procedures and advocate enrollment continuity. | **TECHNICAL READY (Org Operational)** |
| **Consent & Legal Basis** | Consent checkboxes recorded with timestamps and version during registration and video recordings. | Document consent withdrawal workflows and alternative legal grounds. | Legal drafting of DPDP-compliant notice and consent artifacts in regional languages. | **TECHNICAL READY (Notice Drafting Required)** |
| **Access Handling (DSAR)** | Case and evidence export tools available to authenticated case participants. | Standard operating procedure for handling formal Data Subject Access Requests. | Legal review of 30-day response timeline guidelines under DPDP rules. | **TECHNICAL READY (SOP Required)** |
| **Processor & Vendor Oversight**| TLS 1.3 enforced; least-privilege IAM roles for S3 and backing services. | Execute Data Processing Agreements (DPAs) with AWS, Redis Cloud, OpenAI, Stripe. | Counsel review of vendor DPA clauses and limitation of liability caps. | **TECHNICAL READY (Contractual Review Open)** |
| **Controlled Evidence Sharing** | Granular `EvidenceAccessGrant` with `VIEW`/`DOWNLOAD` levels and expiry timestamps. | Case ownership verification before granting emergency custody transfers. | Review advocate-client privilege protections under Indian Evidence Act Sec 126. | **TECHNICAL READY (Legal Approved)** |
| **AI Processing & Privacy** | Prompt sanitization defangs injection; user prompts grounded in retrieved chunks; no PII sent in system prompts. | Restrict internal AI model fine-tuning; prohibit training on customer case facts. | Counsel review of OpenAI Zero Data Retention (ZDR) enterprise terms. | **TECHNICAL READY (ZDR Verification Open)** |
| **Payment Processing** | Stripe webhook HMAC verification, idempotent processing, PCI-DSS compliant hosted fields. | Monthly reconciliation of platform fees and advocate payouts. | Compliance review with RBI Payment Aggregator / Payment Gateway (PA/PG) guidelines. | **TECHNICAL READY (Financial Review Open)** |
| **Security Incident Response** | Automated incident trigger on tampering; 15-min SLA for SEV-1; immutable audit logging. | Appoint Data Protection Officer (DPO) and 24/7 incident response team. | Legal procedure for 6 hours / 72 hours breach notification to CERT-In and Data Protection Board. | **TECHNICAL READY (DPO Assignment Pending)** |
| **Grievance Redressal** | Feedback and issue reporting API (`/api/v1/feedback`) with priority and status tracking. | Appoint Grievance Officer; publish contact info on website. | Legal review of grievance resolution timelines under IT Rules and DPDP Act. | **TECHNICAL READY (Grievance Officer Pending)** |
| **Cross-Border Transfers** | AWS Asia Pacific (Mumbai) `ap-south-1` primary region; data stored within Indian territory. | Verify backup locations and third-party vendor server locations. | Counsel verification against Central Government notification of restricted transfer countries. | **TECHNICAL READY (Geographic Verified)** |
| **Terms of Service & Notices** | Frontend routes `/terms` and `/privacy` available for legal text rendering. | Annual review of terms of service and advocate platform guidelines. | Mandatory legal drafting of Platform Terms of Service and Advocate Code of Conduct. | **TECHNICAL READY (Legal Drafting Open)** |

---

## 3. Phase XX Compliance Registry & Legal Notice Versioning

Under Phase XX, data governance is reinforced with formal compliance tracking and versioned consent auditability:

1. **Compliance Registry (`compliance_registry_items`)**:
   - Distinctly tracks:
     - `technical_readiness`: Automated controls implemented and tested in code.
     - `contractual_readiness`: Vendor agreements and processing contracts executed.
     - `policy_readiness`: Internal SOPs and governance frameworks adopted.
     - `legal_approval`: Formal affirmative sign-off by qualified external Indian legal counsel.
   - Prevents software systems from inferring legal approval from technical completion.

2. **Multilingual Consent & Document Versioning (`legal_document_versions`, `user_document_consents`)**:
   - Supports parallel language versions (`en-IN`, `hi-IN`) for Terms of Service, Privacy Notices, and AI Disclosures.
   - Stores cryptographic hashes of IP and User-Agent (`ip_hash`, `user_agent_hash`) to provide non-repudiable evidentiary audit trails without retaining unnecessary personal data.
   - Historical consent records are immutable and preserved indefinitely for statutory compliance.
