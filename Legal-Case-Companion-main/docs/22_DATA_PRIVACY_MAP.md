# Legal Case Companion (LCC) — Data Privacy & Transmission Map (6.0)

This document maps data collection, storage, access control, retention, and external transmission boundaries across Legal Case Companion, strictly adhering to Indian data privacy principles and advocate-client confidentiality standards.

---

## 1. Product-Level Data Inventory & Boundary Map

| Data Category | Specific Elements | Storage Location | Access Controls | Retention Policy | External Transmission |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Authentication & Identity** | Email, hashed password (Argon2id), full name, user role | PostgreSQL (`users` table) | Self, Admin (read-only for support) | Retained until account deletion request | None (zero external auth brokers unless Google OAuth opted) |
| **Case Metadata & Intake** | Title, dispute description, case status, dates | PostgreSQL (`cases` table) | Explicit matter participants only | Duration of matter $+ 3\text{ years}$ | None |
| **Privileged Legal Documents** | PDF, DOCX, scanned evidence contracts | AWS S3 (`ap-south-1`) with SSE-S3 | Matter participants via 15-min presigned URL | Duration of matter | Sent to AWS Malware scanner; text extracted locally |
| **Legal Strategy Notes** | Internal counsel strategy notes | PostgreSQL (`case_notes` table) | Counsel only (`is_counsel_only=True`) | Duration of matter | Never transmitted externally |
| **Copilot AI Queries** | Legal questions, retrieved document snippets | In-memory during LLM execution; vector embeddings | Scoped to matter participants | Ephemeral during inference; audit metadata stored | Transmitted to OpenAI API via HTTPS; zero model training clause |
| **Pilot User Feedback** | Categorized feedback, sanitized page URL, friction notes | PostgreSQL (`pilot_feedback` table) | Admin & Product Team | Retained for product roadmap cycle | None; URLs sanitized of tokens and query params |
| **Operational Telemetry** | Request ID, HTTP status, endpoint path, latency | Server stdout / Render log stream | SysOps / Admin | 30 days rolling log retention | None; raw text and tokens filtered |

---

## 2. AI Data Protection & Transmission Boundaries

1. **Zero Model Training**: Enterprise/API agreement with OpenAI explicitly excludes API data from model training or continuous learning.
2. **Context Minimization**: Only the top-5 most relevant document chunks are included in the prompt; entire files are never dumped into context.
3. **No Confidential Strategy in LLM**: Counsel-only internal strategy notes are strictly excluded from retrieval indexes.
4. **Citation Stripping**: If the model generates a citation to an ungrounded or non-existent document, the citation is stripped before the user sees it.

---

## 3. Email Notification Privacy Rule

1. **No Sensitive Legal Details in Email**: Email notifications function strictly as alert signposts (e.g. *"A new matter request has been submitted in Case #A1B2C3"*).
2. **No Document Attachments in Email**: Evidence files, contracts, or detailed legal arguments are never attached to email notifications.
3. **Authentication Boundary**: Users must authenticate into the AppShell to view legal matter contents.
