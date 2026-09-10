STATUS: DRAFT
AUTHORITY: PROJECT SOURCE OF TRUTH
IMPLEMENTATION STATUS: NOT STARTED
RULE: UNDEFINED INFORMATION MUST NOT BE INVENTED

# Project Context

## Purpose of this File
This `00_PROJECT_CONTEXT.md` is the main project context and source-of-truth document.
Future technical documentation and implementation must be based on this file.
The purpose is to clearly explain WHAT the Legal Case Companion is before deciding HOW to implement it.

## Project
**Name**: Legal Case Companion
The project is an India-focused legal assistance platform.
The platform is intended to connect clients with suitable verified lawyers and provide an end-to-end digital case-management experience.

The platform should support the journey from:
Client → Legal issue → Case information → Lawyer discovery → Lawyer selection → Consultation → Payment → Case management → Documents → Case updates → AI-assisted case understanding → Tasks/deadlines → Ongoing lawyer-client interaction

*IMPORTANT: This is a product description, NOT permission to invent implementation details.*

## Target Users
The known user types are:

1. **CLIENT**: A person seeking legal assistance.
   Possible activities include:
   - creating an account
   - describing a legal issue
   - providing case information
   - providing location
   - finding lawyers
   - viewing lawyer information
   - booking consultation
   - making payment
   - uploading case documents
   - viewing case information
   - communicating with the lawyer
   - receiving case updates
   - using AI-assisted case understanding

2. **LAWYER**: A legal professional using the platform.
   Possible activities include:
   - creating a lawyer account
   - providing professional information
   - completing verification
   - defining practice areas
   - managing availability
   - receiving consultation requests
   - conducting consultations
   - reviewing client-provided case information
   - accessing authorized case documents
   - updating case information
   - communicating with clients

3. **ADMIN**: A platform administrator.
   Possible responsibilities include:
   - managing users
   - managing lawyer verification
   - managing platform data
   - handling platform-level operations
   - monitoring suspicious activity
   - managing administrative workflows

*Do not invent additional roles unless required later.*

## Core Product Purpose
The platform should solve the problem of fragmented legal assistance.
The client should not have to manage lawyer discovery, consultation, documents, case information, updates, tasks and legal information through completely disconnected systems.
The platform should provide a centralized case companion.

## Known Product Flow
The currently known high-level flow is:
1. User opens the platform.
2. User creates an account or logs in.
3. User identifies the legal issue.
4. The platform collects relevant basic information.
5. Location may be used to find suitable lawyers.
6. The platform displays suitable lawyers.
7. Client can view lawyer information.
8. Client selects a lawyer.
9. Client books a consultation.
10. Client pays the consultation fee where applicable.
11. Consultation takes place online or offline depending on the supported workflow.
12. Lawyer provides guidance.
13. Client can provide case documents.
14. The case can become an ongoing digital case record.
15. Case updates, events, tasks and deadlines may be tracked.
16. AI may assist the client in understanding their case information and documents.
17. Lawyer remains the appropriate professional for legal advice and representation.

*IMPORTANT: This is only the currently known product workflow. Do not invent additional workflow steps.*

## Backend Responsibilities
The backend will eventually be responsible for areas such as:
- user management
- authentication
- authorization
- lawyer management
- lawyer verification
- lawyer discovery
- case management
- case participants
- consultations
- appointments
- payments
- documents
- notifications
- case timelines
- tasks/deadlines
- AI integration
- audit logs
- administrative operations
- API services
- database access
- external service integrations

*These are areas of responsibility, NOT yet implementation specifications.*

## Technical Areas to be Designed Later
The project will later require decisions about:
- authorization
- caching
- background jobs
- payment integration
- notification services
- Docker
- CI/CD
- monitoring
- logging
- security

*DO NOT choose these technologies in this document unless explicitly decided later.*

## Important Data
The system is expected to handle potentially sensitive information such as:
- user account information
- lawyer professional information
- case information
- legal documents
- consultation information
- payment information
- case history
- AI interaction information
- audit information

*Because of this, security, authorization, privacy and data ownership will be major architectural requirements.*

## AI Role
AI is intended to assist users with understanding and organizing legal information.
AI must NOT automatically be treated as a lawyer.
The system must clearly separate: AI assistance from professional legal advice provided by a lawyer.
The backend must eventually control what data the AI can access.
*Do not design the AI architecture yet. That will be documented separately.*

## Important Unknown Information
If information has not been explicitly defined, DO NOT GUESS.
Use: `UNDEFINED` or `DECISION REQUIRED`.

Examples of current unknowns:
- exact authentication method: FINAL (JWT with refresh-token)
- exact database technology: FINAL (PostgreSQL, SQLAlchemy, Alembic)
- exact cloud provider: FINAL (Render)
- exact payment provider: DECISION REQUIRED
- exact AI provider: FINAL (OpenAI)
- exact notification provider: DECISION REQUIRED
- exact lawyer verification process: DECISION REQUIRED
- exact legal data sources: DECISION REQUIRED
- exact retention policy: DECISION REQUIRED
- exact pricing model: DECISION REQUIRED
- exact subscription model: DECISION REQUIRED
- exact communication system: DECISION REQUIRED
- exact video consultation provider: DECISION REQUIRED

## Anti-Hallucination Rules
These rules are mandatory:
1. Never invent product requirements.
2. Never invent users or roles.
3. Never invent database entities.
4. Never invent database fields.
5. Never invent APIs.
6. Never invent external services.
7. Never invent legal requirements.
8. Never assume a feature has been implemented.
9. Never describe a proposed feature as an existing feature.
10. Never silently make an architectural decision.
11. If information is missing, mark it UNDEFINED.
12. If a decision is required, mark it DECISION REQUIRED.
13. Clearly distinguish between: KNOWN, PROPOSED, UNDEFINED, DECISION REQUIRED.
14. Future documentation must refer back to this document.
