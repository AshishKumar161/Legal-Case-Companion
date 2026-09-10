STATUS: DRAFT

AUTHORITY: DERIVED FROM PROJECT SOURCE OF TRUTH

SOURCE DOCUMENTS:
- docs/00_PROJECT_CONTEXT.md
- docs/01_SYSTEM_ARCHITECTURE.md
- docs/02_DATABASE_DESIGN.md
- docs/03_API_SPECIFICATION.md
- docs/04_AUTHORIZATION_SECURITY.md
- docs/05_BACKEND_MODULES.md
- docs/06_AI_INTEGRATION.md

IMPLEMENTATION STATUS: NOT STARTED

RULE:
FILE CONTENT AND DOCUMENT METADATA MUST HAVE EXPLICIT OWNERSHIP AND ACCESS CONTROL

# File and Document System

## 1. PURPOSE
The file and document system exists to securely support legal documents associated with cases. 
Based on project requirements, supported categories include:
- uploaded case documents.
- supporting evidence.
- lawyer-provided documents.
- other case-related files.

(Categories not supported by the project requirements are excluded).

## 2. DOCUMENT VS FILE
The system distinguishes between a DOCUMENT and a FILE:
- **DOCUMENT**: The application's logical representation (metadata, ownership, authorization rules, lifecycle).
- **FILE**: The actual binary content of the upload.

These have different storage responsibilities.
Conceptually:
- Application Database → document metadata.
- Object/File Storage → actual file bytes.
(The storage provider is NOT yet chosen).

## 3. DOCUMENT OWNERSHIP
The ownership model dictates that a document must be associated with the appropriate case and authorized user according to the database and authorization designs.
The system must be able to determine:
- who uploaded it (the Uploader).
- which case it belongs to (the Target Case).
- who is allowed to access it (Case Participants/Owners).
- what operations are allowed based on roles.

## 4. DOCUMENT ACCESS CONTROL
CRITICAL: A document must NEVER be accessible simply because someone knows its identifier (or storage URL).
Every protected document operation must perform authorization.

Conceptual flow:
User Request → Authentication → Authorization → Case Access Check → Document Access Check → File Retrieval

Authorization decisions depend strictly on the user's relationship to the case:
- Client A → Case A document → ALLOWED when authorized.
- Client A → Case B document → DENIED.
- Unauthorized Lawyer → Case A document → DENIED.
- Authorized Lawyer → Case A document → ALLOWED.

## 5. DOCUMENT OPERATIONS
The system may need to support the following operations. Not all are automatically assumed; they must trace to source requirements.
- **upload**: (KNOWN - from "uploading case documents").
- **list/retrieve metadata**: (KNOWN - from accessing case info).
- **view/download**: (KNOWN - implied by access).
- **update metadata**: (DECISION REQUIRED).
- **replace/version**: (DECISION REQUIRED).
- **delete/archive**: (DECISION REQUIRED).

## 6. UPLOAD FLOW
Conceptual upload flow:
1. **Client / Lawyer**: Initiates upload.
2. **Authenticated Request**: Identity is verified.
3. **Authorization**: Case-level permissions are checked.
4. **Request Validation**: Schema and metadata are validated.
5. **Upload Handling**: Backend or direct-storage proxy receives the stream.
6. **File Validation**: MIME type and basic safety checks.
7. **Storage**: Bytes are written to Object Storage.
8. **Metadata Persistence**: Document record is created in the relational database.
9. **Case Association**: Document is linked to the Case entity.
10. **Audit / Traceability**: The upload action is logged.

## 7. DIRECT VS BACKEND-MEDIATED UPLOAD
Determine whether files should pass through the backend or use controlled direct-to-storage upload (e.g., pre-signed URLs).
- **OPTION A (Backend-Mediated)**: Client → Backend → Storage. (Pros: Simpler, stricter validation. Cons: Higher backend bandwidth/memory).
- **OPTION B (Direct)**: Client → Authorized Storage Upload → Backend Metadata. (Pros: Scales well for large files. Cons: Harder to scan for malware before storage).

STATUS: DECISION REQUIRED
PROPOSED: Option B (Pre-signed URLs) for scalability, paired with asynchronous backend validation.

## 8. FILE STORAGE
The actual file bytes should be stored outside the relational database in a dedicated storage layer.
Possible storage abstraction:
Application → Storage Service → Object/File Storage.
Storage Provider: FINAL: AWS S3.

## 9. STORAGE ABSTRACTION
The backend should not couple business logic directly to a specific storage vendor.
An interface or abstraction must be defined to support:
- upload
- retrieve
- delete/archive
- metadata operations
- signed/temporary access URLs (where appropriate)

## 10. DOCUMENT METADATA
Categories of metadata based on `docs/02_DATABASE_DESIGN.md`:
- document identifier (UUID)
- case association (Case ID)
- uploader (User ID)
- file name (Original)
- content type (MIME)
- storage reference (e.g., Object Key)
- created timestamp

Undefined fields that may be needed (DECISION REQUIRED):
- file size
- updated timestamp
- version
- status

## 11. FILENAME HANDLING
User-provided filenames must not be trusted as storage paths.
Secure handling principles:
- Generate safe, random storage keys (e.g., UUIDs) to prevent collisions and predictable storage keys.
- Prevent path traversal attacks (e.g., rejecting `../../../etc/passwd`).
- Strip invalid characters from original filenames before storing them in metadata.

## 12. CONTENT TYPE
Uploaded content must be validated. The backend must not trust only the client-provided MIME type.
Potential validation layers:
- declared content type (from HTTP headers).
- file extension (from original filename).
- actual content signature (magic bytes).
- security scanning.
(Scanner/Library selection is DECISION REQUIRED).

## 13. FILE SIZE
File size limits must eventually be defined to prevent Denial-of-Service or unmanageable storage costs.
STATUS: DECISION REQUIRED
Limits may differ by operation or file type if eventually required.

## 14. MALICIOUS FILE PROTECTION
Security requirements for uploaded content must address:
- malicious files
- executable content
- embedded scripts (e.g., XSS in SVGs/HTML)
- malware / viruses
- archive bombs (if zip extraction is ever supported)
- malformed files
- dangerous formats
(Specific scanning vendor/implementation is DECISION REQUIRED).

## 15. STORAGE ISOLATION
Protected legal documents must not be stored in a way that accidentally makes them public.
- Storage buckets must be set to Private.
- Storage access must be controlled exclusively through the application backend or an authorized temporary access mechanism.
- Do not expose permanent public URLs unless explicitly required (which is generally never for legal docs).

## 16. TEMPORARY ACCESS
Supporting temporary/signed access to files (e.g., AWS S3 Pre-signed URLs) offers security advantages by keeping bandwidth off the backend while enforcing time-limited authorization.
STATUS: DECISION REQUIRED (Implementation depends on the chosen storage provider).

## 17. DOCUMENT VERSIONS
Determining whether documents need versioning:
- updated documents (e.g., a signed vs unsigned contract).
- maintaining historical versions for legal tracking.
- auditability.
- avoiding accidental overwrite.
STATUS: DECISION REQUIRED.

## 18. DOCUMENT LIFECYCLE
The conceptual lifecycle of a document involves stages:
- created (metadata initialized)
- uploaded (bytes stored)
- available (ready for view/AI)
- replaced/versioned (if supported)
- archived/deleted
Exact lifecycle states and database enums: DECISION REQUIRED.

## 19. SOFT DELETE / ARCHIVE
Determining whether documents should be permanently deleted or archived (soft-delete).
Factors to consider:
- accidental deletion recovery.
- legal importance / compliance.
- auditability.
- storage costs.
- retention requirements.
Current retention policy and deletion strategy: DECISION REQUIRED.

## 20. DATABASE STORAGE
Separation of concerns:
**DATABASE SHOULD REPRESENT**:
- document metadata.
- relationships (to Case, User).
- authorization references.
- ownership.
- file/storage reference keys.
- audit-related metadata where justified.

**FILE STORAGE SHOULD REPRESENT**:
- actual file bytes.

## 21. DOCUMENT ACCESS THROUGH API
API access is mediated by authorization.
Conceptual flow:
API Request → Authenticate → Authorize → Find document metadata → Verify case/resource access → Retrieve file (or pre-signed URL) → Return controlled response.

## 22. DOCUMENT → CASE RELATIONSHIP
The relationship between CASE and DOCUMENT dictates that a document associated with a case must inherit appropriate case-level access restrictions unless a more specific rule exists. There are currently no documented exceptions.

## 23. DOCUMENT → USER RELATIONSHIP
The system must be able to determine the Uploader (User ID) and the accessing user's relationship to the document/case. (No additional user roles are invented; standard Client, Lawyer, Admin apply).

## 24. DOCUMENT → LAWYER RELATIONSHIP
A lawyer's access must be determined strictly by authorization to the related case (via `CaseParticipant`).
Lawyer access must NOT be based solely on:
- knowing a document ID.
- knowing a storage key.
- being a lawyer.
- having a valid login.

## 25. DOCUMENT → AI RELATIONSHIP
CRITICAL: AI must only receive documents that the current user is authorized to access.
Conceptual flow:
User → Backend Authentication → Case Authorization → Document Authorization → Document Retrieval → Controlled Extraction → AI Context → AI Processing.
The AI provider must never be allowed to directly search unrestricted document storage.

## 26. DOCUMENT PROCESSING
Documents may require preprocessing before AI use.
Potential steps (DECISION REQUIRED if undefined):
- text extraction (PROPOSED)
- metadata extraction (PROPOSED)
- OCR (DECISION REQUIRED)
- page segmentation (DECISION REQUIRED)
- chunking (DECISION REQUIRED)
- indexing (DECISION REQUIRED)
- classification (DECISION REQUIRED)

## 27. OCR
Determining whether scanned/image-based documents require Optical Character Recognition (OCR) to extract text for the AI.
STATUS: DECISION REQUIRED.
(No OCR provider or library is chosen).

## 28. DOCUMENT SEARCH
Determining whether users need search over documents (filename, metadata, full-text, semantic).
STATUS: DECISION REQUIRED.

## 29. DOCUMENT INDEXING FOR AI
If the project requires RAG over documents, the conceptual pipeline is:
Document → Validation → Storage → Extraction → Processing → Indexing → Retrieval → AI.
(Vector database, embedding model, chunk size, and indexing framework remain future decisions).

## 30. DOCUMENT EXTRACTION SECURITY
Extracted text must be treated as untrusted data.
Documents may contain malicious instructions intended to manipulate AI (Prompt Injection). Extracted content must NOT automatically become trusted system instructions. (Refer to AI Integration and Security specs).

## 31. DOCUMENT AUDITING
Document operations requiring persistent audit records:
- upload
- access (metadata)
- download (bytes)
- replacement
- deletion
- sharing/access changes (where supported)
- AI retrieval

## 32. DOCUMENT LOGGING
Sensitive document content must not be placed into system logs.
Avoid logging:
- full document contents or extracted text.
- private legal facts.
- private case data.
- authentication secrets from pre-signed URLs.

## 33. DOCUMENT RETENTION
The project does not currently define a retention period for legal documents.
STATUS: DECISION REQUIRED.
Factors affecting the decision: legal compliance, storage costs, user agreements, data privacy laws.

## 34. BACKUP AND RECOVERY
Conceptual requirements for disaster recovery:
- document backup (storage layer replication).
- metadata backup (relational database backups).
- restoration procedures.
- consistency between database metadata and stored files must be maintained.

## 35. STORAGE CONSISTENCY
Failure scenarios must be handled gracefully:
- **Database write succeeds BUT file upload fails**: Results in an orphaned DB record. Requires a cleanup job or transaction rollback.
- **File upload succeeds BUT metadata persistence fails**: Results in an orphaned file in object storage. Requires periodic garbage collection of unreferenced files.
(Implementation mechanisms are DECISION REQUIRED).

## 36. DOCUMENT SECURITY THREATS
Project-specific risks to mitigate:
- unauthorized document access.
- public storage exposure.
- path traversal (if filenames aren't sanitized).
- malicious uploads (malware/viruses).
- data leakage.
- stale access URLs (pre-signed URLs not expiring).
- metadata mismatch.
- orphaned files.
- accidental deletion without soft-delete protection.
- AI data leakage (wrong case context).
- prompt injection through documents.

## 37. DOCUMENT DECISION REGISTER

| Decision | Status | Reason | Source | Impact |
|---|---|---|---|---|
| Storage Provider | FINAL: AWS S3 | Approved | Docs | Infrastructure |
| Upload Architecture | DECISION REQUIRED | Proxy vs Direct | Docs | Backend load |
| File Size Limits | FINAL: 10MB | User input | Docs | Abuse prevention |
| Supported Formats | FINAL: PDF, PNG, JPEG | User input | Docs | Validation |
| Malware Scanning | FINAL: Mandatory quarantine & scan | User input | Docs | Security |
| OCR Requirement | DECISION REQUIRED | AI needs | Docs | AI processing |
| Versioning | DECISION REQUIRED | Not finalized | Docs | Database schema |
| Retention & Deletion | DECISION REQUIRED | Compliance | Docs | Storage costs |
| Document Search | DECISION REQUIRED | Product needs | Docs | DB/Search engine |

## 38. DOCUMENT TRACEABILITY

| Requirement | Source Document | Source Section | Status | Implementation Impact |
|---|---|---|---|---|
| Support uploaded documents | 00_PROJECT_CONTEXT.md | Known Product Flow | KNOWN | Core feature |
| Storage outside Database | 01_SYSTEM_ARCHITECTURE.md | Document Flow | KNOWN | Object storage required |
| Document Case relation | 02_DATABASE_DESIGN.md | Data Ownership | KNOWN | Auth checks |
| Access control validation | 04_AUTHORIZATION_SECURITY.md | Doc Access Control | KNOWN | API middleware |
| AI restricted retrieval | 06_AI_INTEGRATION.md | Case Isolation | KNOWN | RAG filtering |

## 39. DOCUMENT DATA FLOW
Conceptual flow:
1. **CLIENT / LAWYER**: Requests document upload or retrieval.
2. **AUTHENTICATION**: Identity confirmed.
3. **AUTHORIZATION**: User is verified as an owner/participant of the target case.
4. **DOCUMENT REQUEST**: Action requested (e.g., upload).
5. **VALIDATION**: File extension, metadata, and safety checks pass.
6. **STORAGE**: Bytes placed securely in isolated Object Storage.
7. **METADATA**: Document record created/updated in the database.
8. **CASE ASSOCIATION**: DB links the document to the legal case.
9. **AUDIT**: Action logged in the AuditLog.
10. **OPTIONAL PROCESSING**: Async jobs trigger (e.g., text extraction).
11. **OPTIONAL AI / SEARCH**: Indexed for future RAG queries.

## 40. UNDEFINED / DECISION REQUIRED
Unresolved document-system decisions:
- Selection of storage provider (FINAL: AWS S3).
- Choice between backend-mediated uploads and direct-to-storage pre-signed uploads.
- Implementation of temporary/pre-signed URLs for downloads.
- Strict limits on file sizes and MIME types.
- Malware scanning provider or integration strategy.
- OCR tooling requirements.
- Document versioning logic and database structure.
- Soft-delete versus hard-delete policies and retention timelines.
- Needs and technology for full-text document search.
- Mechanisms for handling storage/database eventual consistency.
