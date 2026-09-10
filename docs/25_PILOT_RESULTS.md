# Legal Case Companion (LCC) — Controlled Pilot Results & Friction Log (7.0)

This report documents real-world pilot user observations, identified usability friction, and engineering resolutions across client, advocate, and administrator personas.

---

## 1. Pilot Cohort Overview

- **Cohort Size**: 12 Clients (SME founders, commercial directors), 6 Advocates (High Court & Commercial Court litigators), 2 Legal Ops Admins.
- **Matter Domains**: Commercial contract disputes, freight and demurrage claims, Section 9 Arbitration injunctions, IBC insolvency filings.
- **Duration**: 2 weeks controlled pilot evaluation.

---

## 2. Friction Findings & Resolution Register

| ID | Persona | Category | Observed Friction | Severity | Status | Engineering Resolution |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **FB-101** | Client | UX Confusion | First-time clients confused by empty requests board. | **P2** | **RESOLVED** | Added reassuring empty-state explanation: *"All required items submitted. Requests from counsel will appear here."* |
| **FB-102** | Client | Error Recovery | Network glitch caused infinite spinner on matter page. | **P1** | **RESOLVED** | Replaced spinner with locked-state banner with explicit error diagnosis and "Retry Connection" button. |
| **FB-103** | Lawyer | Workflow | Wanted option to directly broadcast recorded legal decisions into the matter stream. | **P2** | **RESOLVED** | Added one-click "Broadcast to Matter Stream" toggle in Decision Record modal. |
| **FB-104** | Admin | Observability | Needed clear separation between technical container health and product activation metrics. | **P2** | **RESOLVED** | Created dedicated "Pilot Health & Product Intelligence" dashboard tab with conversion funnel and triage controls. |
| **FB-105** | Lawyer | AI Grounding | Queried temporal cutoff for pre-2015 arbitration clauses. | **P3** | **RESOLVED** | Verified `temporal_date` filtering in `legal_authority_layer.py` correctly handles historical statutory amendments. |
