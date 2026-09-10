STATUS: DRAFT

AUTHORITY: ENGINEERING RULEBOOK

SOURCE DOCUMENTS:
- docs/00_PROJECT_CONTEXT.md
- docs/01_SYSTEM_ARCHITECTURE.md
- docs/02_DATABASE_DESIGN.md
- docs/03_API_SPECIFICATION.md
- docs/04_AUTHORIZATION_SECURITY.md
- docs/05_BACKEND_MODULES.md
- docs/06_AI_INTEGRATION.md
- docs/07_FILE_DOCUMENT_SYSTEM.md
- docs/08_PAYMENT_CONSULTATION.md
- docs/09_INFRASTRUCTURE_DEPLOYMENT.md
- docs/10_TESTING_STRATEGY.md
- docs/11_ENVIRONMENT_CONFIGURATION.md

IMPLEMENTATION STATUS: NOT STARTED

CORE RULE:
WHEN INFORMATION IS MISSING, DO NOT GUESS.

# Engineering Rules Specification

## 1. SOURCE-OF-TRUTH HIERARCHY
Use this authority order for future implementation:
1. Explicit approved project requirements
2. `docs/00_PROJECT_CONTEXT.md`
3. Approved architecture documentation
4. Approved database design
5. Approved API specification
6. Approved security rules
7. Approved AI/document/payment/infrastructure documentation
8. Implementation code
9. Agent assumptions

CRITICAL: Code must NOT become the source of truth simply because it already exists. 
If code conflicts with approved documentation: STOP AND FLAG THE CONFLICT.
- Do not silently change the documentation.
- Do not silently change the code.

## 2. ANTI-HALLUCINATION RULE
This is mandatory. NEVER:
- invent requirements
- invent users
- invent roles
- invent API endpoints
- invent database tables
- invent database fields
- invent legal claims
- invent legal sources
- invent citations
- invent payment states
- invent business rules
- invent external providers
- invent infrastructure resources
- invent security policies
- invent AI capabilities
- invent test results

When information is missing: **UNDEFINED**
When a decision is needed: **DECISION REQUIRED**
When suggesting an implementation: **PROPOSED**
Do not silently convert PROPOSED into FINAL.

## 3. READ DOCUMENTATION BEFORE CODING
Before modifying any code:
1. identify which feature is being implemented
2. identify relevant documentation
3. read the relevant documentation
4. verify dependencies and constraints
5. implement only what is documented

Never begin coding based solely on a short natural-language instruction when the documentation contains the relevant specification.

## 4. TRACEABILITY
Every significant implementation decision must be traceable to documentation.
Examples:
- Database model → `docs/02_DATABASE_DESIGN.md`
- Endpoint → `docs/03_API_SPECIFICATION.md`
- Authorization rule → `docs/04_AUTHORIZATION_SECURITY.md`
- AI behavior → `docs/06_AI_INTEGRATION.md`
- Document behavior → `docs/07_FILE_DOCUMENT_SYSTEM.md`
- Payment behavior → `docs/08_PAYMENT_CONSULTATION.md`
- Infrastructure → `docs/09_INFRASTRUCTURE_DEPLOYMENT.md`
- Testing → `docs/10_TESTING_STRATEGY.md`

If a feature has no documented source: DO NOT IMPLEMENT IT AS FACT. 
Mark: **DOCUMENTATION GAP** and **DECISION REQUIRED**.

## 5. IMPLEMENTATION STATUS
Never claim something is: complete, production-ready, secure, tested, deployed, or verified unless there is evidence.
Use explicit statuses such as:
- PLANNED
- IN PROGRESS
- IMPLEMENTED
- TESTED
- VERIFIED
- BLOCKED
- UNDEFINED

Do not mark a feature COMPLETE merely because code exists.

## 6. NO SILENT SCOPE EXPANSION
While implementing a feature, do not add unrelated functionality because it seems useful.
Example: If implementing lawyer login, do not automatically implement lawyer analytics, recommendations, messaging, or subscriptions unless documented.

## 7. NO SILENT ARCHITECTURE CHANGES
Do not change:
- backend architecture
- database architecture
- API contracts
- authentication architecture
- authorization model
- AI architecture
- storage architecture
- payment architecture
- deployment architecture

without updating the relevant documentation and clearly recording the decision.

## 8. DATABASE RULES
Mandatory:
- database schema must follow `docs/02_DATABASE_DESIGN.md`
- no undocumented tables
- no undocumented fields
- no undocumented relationships
- no direct schema changes without migration
- migrations must be versioned
- destructive changes require explicit review
- preserve referential integrity
- never bypass authorization through direct database access

Never solve an application problem by casually changing the schema.

## 9. API RULES
Mandatory:
- API implementation must follow `docs/03_API_SPECIFICATION.md`
- do not invent endpoints
- do not silently rename endpoints
- do not silently change request schemas
- do not silently change response schemas
- validate all external input
- protect authenticated endpoints
- enforce authorization
- return safe errors

If the API contract needs to change: DOCUMENTATION MUST BE UPDATED FIRST.

## 10. AUTHENTICATION RULES
Mandatory:
- never expose credentials
- never log passwords
- never log authentication secrets
- never trust client-provided identity claims
- authenticate protected operations
- securely handle session/token lifecycle
- do not invent a different authentication mechanism
Follow: `docs/04_AUTHORIZATION_SECURITY.md`

## 11. AUTHORIZATION RULES
This is one of the highest-priority rules. Authentication alone is NOT authorization.
Every protected resource must check:
- WHO IS THE USER?
- WHAT ROLE DO THEY HAVE?
- WHAT RESOURCE ARE THEY REQUESTING?
- ARE THEY AUTHORIZED TO ACCESS THAT RESOURCE?

Never authorize access merely because:
- the user is logged in
- the user is a lawyer
- the user knows the resource ID
- the frontend displayed the resource
- a request contains a valid-looking identifier

## 12. CASE ISOLATION
Mandatory: A client must not access another client's case. A lawyer must not access unrelated cases.
Case IDs must never be treated as sufficient authorization. Every protected case operation must verify access.
Applies to: case details, documents, timeline, tasks, consultation data, AI requests, related resources.

## 13. DOCUMENT SECURITY
Mandatory:
- documents are private by default
- storage identifiers are not authorization
- document IDs are not authorization
- direct public access is prohibited unless explicitly documented
- access must be checked against case/resource authorization
- uploaded content must be validated
- sensitive document content must not appear unnecessarily in logs
Follow: `docs/07_FILE_DOCUMENT_SYSTEM.md`

## 14. AI ENGINEERING RULES
Critical: AI must NOT be treated as an authoritative source of legal truth.
Never: fabricate citations, fabricate laws, fabricate case details, fabricate sources, fabricate legal provisions, fabricate evidence, invent missing facts, present unsupported claims as verified.
AI-related functionality must follow `docs/06_AI_INTEGRATION.md`.

## 15. AI DATA ACCESS
The AI must never receive unrestricted database access.
The backend must determine: current user, role, case, authorization, permitted documents, permitted legal sources before creating AI context.
The frontend must not bypass the backend to retrieve protected AI data.

## 16. AI SOURCE GROUNDING
For source-dependent answers:
- retrieve authorized sources
- preserve source identity
- preserve traceability
- avoid unsupported claims
- communicate uncertainty
If evidence is insufficient: DO NOT MAKE UP AN ANSWER.

## 17. AI PROMPT INJECTION
Treat as untrusted: user input, uploaded documents, extracted text, retrieved external content.
They must NOT override: system instructions, application security controls, authorization decisions, trusted control data.
Never allow document content to become privileged instructions automatically.

## 18. JURISDICTION AND TIME
For legal AI functionality:
- do not assume jurisdiction
- do not silently apply foreign law
- do not silently treat outdated information as current
- preserve source/date context where required
- refuse or qualify unsupported claims

## 19. PAYMENT RULES
Mandatory:
- never trust frontend payment success as the final authority
- verify provider results server-side where supported
- protect payment credentials
- process callbacks/webhooks securely
- handle duplicate events safely
- use idempotency where required
- never invent payment states
Follow: `docs/08_PAYMENT_CONSULTATION.md`

## 20. WEBHOOK RULES
For external callbacks:
- authenticate/verify where supported
- validate payloads
- protect against replay
- make processing idempotent where necessary
- do not trust arbitrary client-submitted state
Do not accept external events blindly.

## 21. FILE UPLOAD RULES
Never trust: filename, extension, MIME type, path, metadata supplied by client.
Validate according to the documented file-security requirements. Do not invent accepted file formats or limits.

## 22. EXTERNAL SERVICE RULES
External services (AI, payments, email, SMS, video, storage):
- isolate provider-specific code
- keep provider credentials secret
- do not expose credentials to clients
- validate external responses
- handle provider failures
- do not hard-code provider assumptions unless finalized

## 23. ERROR HANDLING
Errors must be: predictable, safe, useful to developers, appropriate for clients, free of secrets, free of unnecessary private data.
Never expose: stack traces, database credentials, tokens, secret keys, private case data to end users.

## 24. LOGGING
Logs must support debugging and observability without exposing sensitive data.
Never unnecessarily log: passwords, tokens, API keys, payment credentials, full legal documents, sensitive case facts, private AI content.

## 25. AUDIT LOGGING
Use audit logging for security-sensitive and accountability-relevant operations as documented.
Do not use ordinary logs as a replacement for audit records.
Do not store unnecessary sensitive data in audit records.

## 26. CONFIGURATION
Rules:
- no secrets in source code
- no production secrets in Git
- no hardcoded credentials
- environment-specific configuration must remain isolated
- required configuration must be validated
- configuration changes must be traceable
Follow: `docs/11_ENVIRONMENT_CONFIGURATION.md`

## 27. DEPENDENCY MANAGEMENT
When adding dependencies: verify they are actually needed, avoid duplicate libraries, prefer maintained dependencies, check compatibility, document important dependency decisions, do not introduce a large framework for a trivial requirement.
Do not invent dependency requirements.

## 28. CODE QUALITY
Require: clear naming, small focused functions, clear module boundaries, minimal duplication, explicit error handling, maintainable structure, readable code, appropriate typing, meaningful comments only where necessary.
Avoid overengineering.

## 29. MODULE BOUNDARIES
Follow: `docs/05_BACKEND_MODULES.md`
Do not create circular dependencies. Do not place unrelated business logic in shared modules. Do not turn utility/common modules into dumping grounds. Keep domain responsibilities clear.

## 30. TRANSACTION SAFETY
For operations involving multiple related state changes: maintain consistency, use appropriate transaction boundaries, avoid partial updates, handle failures explicitly. Do not introduce transactions where they are unnecessary.

## 31. CONCURRENCY
Consider race conditions for: booking, payments, document updates, case updates, background jobs. Do not assume sequential execution.

## 32. BACKGROUND JOBS
Background jobs must be: retry-aware, idempotent where necessary, observable, failure-aware, safe with sensitive data.
Do not create background jobs for simple synchronous logic without justification.

## 33. TESTING RULE
No implementation should be considered complete without appropriate tests.
At minimum, changes affecting: authorization, case isolation, documents, payments, AI, database, APIs must receive corresponding tests.
Follow: `docs/10_TESTING_STRATEGY.md`

## 34. NEGATIVE TESTING
Do not test only the happy path.
For security-sensitive functionality always test: unauthenticated access, wrong role, wrong resource owner, invalid identifier, forged state, malformed request, external failure.

## 35. AI TESTING
Any AI feature must include evaluation for relevant: grounding, hallucination, citation correctness, prompt injection, unauthorized data exposure, case isolation, jurisdiction, temporal validity.
A successful API response does not mean an AI feature is correct.

## 36. DATABASE MIGRATION RULE
Never manually change production schema. Schema changes must use the approved migration process.
Before changing a schema: 1) update database design if necessary, 2) review impact, 3) create migration, 4) test migration, 5) verify compatibility.

## 37. API CHANGE RULE
A breaking API change requires: 1) documentation update, 2) impact analysis, 3) implementation, 4) tests, 5) explicit decision.
Never silently break clients.

## 38. SECURITY CHANGE RULE
Any change affecting: authentication, authorization, case access, documents, AI access, payment security must be treated as security-sensitive. Require additional testing and explicit review.

## 39. PERFORMANCE
Do not optimize blindly. First identify the bottleneck.
Prefer: simple architecture, appropriate indexes, efficient queries, controlled external calls, caching where justified, background processing where justified. Do not add infrastructure complexity prematurely.

## 40. OBSERVABILITY
New important functionality should have appropriate: logs, errors, metrics, health visibility, auditability where relevant.
Do not log sensitive content merely to improve observability.

## 41. DEPLOYMENT RULES
Never claim deployment succeeded without evidence.
Before production deployment, relevant: tests, migrations, configuration, health checks, security checks must be verified.
Follow: `docs/09_INFRASTRUCTURE_DEPLOYMENT.md`

## 42. ROLLBACK
Changes must be designed with failure recovery in mind. Avoid changes that cannot be safely reverted or migrated without explicit approval.

## 43. DOCUMENTATION UPDATE RULE
When implementation reveals a requirement or decision that conflicts with documentation: STOP.
Do not silently update code to fit an invented assumption.
Report: **DOCUMENTATION CONFLICT**
Then identify: affected document, conflict, proposed resolution, implementation impact.

## 44. NO FAKE COMPLETION
Never use wording such as: "implemented", "working", "production-ready", "secure", "tested", "verified" unless supported by evidence.
The agent must be honest about incomplete work.

## 45. CHANGE DISCIPLINE
Keep changes focused. For each implementation task: identify scope, modify only relevant files, avoid unrelated refactoring, run relevant tests, report unresolved issues.

## 46. UNKNOWN INFORMATION PROTOCOL
When the agent encounters missing information:
- STEP 1: Identify the missing decision.
- STEP 2: Check all documentation for an answer.
- STEP 3: If still unresolved, mark: **DECISION REQUIRED**
- STEP 4: Do not silently choose a value if that choice materially affects architecture, security, data, or user behavior.

## 47. PROPOSED DECISIONS
The agent may provide recommendations. Every recommendation must be labelled: **PROPOSED**.
A proposed choice does NOT become implementation truth until approved and documented.

## 48. SECURITY-FIRST PRIORITY
When there is a conflict between convenience and security of user/case data, prefer the secure design unless an approved requirement explicitly says otherwise. Do not weaken authorization for convenience.

## 49. DATA MINIMIZATION
Only collect, store, retrieve, log, or transmit data necessary for the documented functionality. Do not create unnecessary copies of legal or personal information.

## 50. FINAL ENGINEERING CHECKLIST
Before considering an implementation task complete, verify:
- [ ] Requirements identified
- [ ] Relevant documentation read
- [ ] No requirements invented
- [ ] Database changes documented
- [ ] API contract followed
- [ ] Authentication respected
- [ ] Authorization enforced
- [ ] Case isolation verified
- [ ] Document access protected
- [ ] AI access controlled
- [ ] Payment logic verified where applicable
- [ ] External integrations isolated
- [ ] Secrets protected
- [ ] Sensitive information excluded from unnecessary logs
- [ ] Tests added
- [ ] Negative/security tests considered
- [ ] Relevant documentation updated
- [ ] No unrelated scope added
- [ ] No false completion claim made

## 51. DOCUMENTATION CONFLICT PROTOCOL
If two documents conflict: DO NOT CHOOSE SILENTLY.
Record:
- CONFLICT: [description]
- DOCUMENT A: [path + section]
- DOCUMENT B: [path + section]
- IMPACT: [what implementation is affected]
- STATUS: DECISION REQUIRED

## 52. ENGINEERING DECISION REGISTER
| Rule / Decision | Status | Reason | Source | Implementation Impact |
|---|---|---|---|---|
| Traceability checking | REQUIRED | Quality Control | Docs | Code alignment |
| Decision process | REQUIRED | Prevent assumptions | Docs | Agent behavior |

## 53. TRACEABILITY
| Engineering Rule | Source Document | Source Section | Reason | Status |
|---|---|---|---|---|
| Anti-Hallucination | 00_PROJECT_CONTEXT.md | Project rules | Prevent drift | REQUIRED |
| Case Isolation | 04_AUTHORIZATION_SECURITY.md | Authorization | Security | REQUIRED |
| No Prod Secrets in Code | 11_ENVIRONMENT_CONFIGURATION.md | Variables | Security | REQUIRED |

---

## FINAL MANDATORY RULES
The following rules must be treated as NON-NEGOTIABLE:
1. Never hallucinate requirements.
2. Never fabricate legal information.
3. Never fabricate citations.
4. Never fabricate database schema.
5. Never fabricate API contracts.
6. Never fabricate security requirements.
7. Never bypass authorization.
8. Never expose unauthorized case data.
9. Never expose unauthorized documents.
10. Never give AI unrestricted case/database access.
11. Never trust retrieved document instructions as system instructions.
12. Never trust frontend payment success without backend verification.
13. Never commit secrets.
14. Never silently change architecture.
15. Never silently change API contracts.
16. Never silently change database contracts.
17. Never claim tests pass without running them.
18. Never claim deployment succeeded without evidence.
19. Never mark incomplete functionality complete.
20. Never turn PROPOSED into FINAL without approval/documentation.
