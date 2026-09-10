# 32 — AI PRODUCTION SAFETY & EVIDENCE GROUNDING GOVERNANCE

## 1. System Mission & Safety Invariants

The Legal Case Companion (LCC) AI is strictly an **evidence-grounded legal research and workflow copilot**. It is not an autonomous legal representative and does not provide ungrounded legal counsel.

### Core Non-Negotiable Invariants
1. **Zero Hallucination / Grounding Prerequisite**: The AI must never invent case facts, citations, case laws, or document extracts. Answers must cite verifiable chunk IDs.
2. **Strict Resource Isolation**: The AI model context must NEVER receive evidence or chunks from cases where the caller is not an authorized participant.
3. **Safe Refusal on Insufficient Evidence**: If retrieval yields 0 chunks or relevance falls below threshold ($0.70$), the system must return a standardized refusal:
   > *"Evidence insufficient. The system cannot reliably answer this point from the available sources."*
4. **Prompt Injection Neutralization**: All untrusted inputs (user queries, document chunks, case notes) pass through sanitization defanging delimiter breakout attempts.

---

## 2. Prompt Injection Defense Architecture

Untrusted text passes through `sanitize_untrusted_prompt_text` in [app/services/ai_provider.py](file:///c:/Users/akuma/OneDrive/Desktop/lcc/Legal-Case-Companion-main/app/services/ai_provider.py):

```text
[Untrusted Input] ──> [XML Tag Escape: </evidence> -> &lt;/evidence&gt;]
                               │
                               ▼
            [Instruction Defanging: "ignore previous..." -> [DEFANGED_INSTRUCTION]]
                               │
                               ▼
            [Record Telemetry: metrics_collector.record_ai_safety_event()]
                               │
                               ▼
            [Encapsulated System Directive: Strict JSON Output Constraint]
```

### Monitored Injection Vectors
- System prompt overrides (`"ignore all previous instructions"`, `"disregard all prior instructions"`).
- Context delimiter escapes (`</evidence>`, `<system>`).
- Cross-tenant data extraction attempts (`"reveal documents from other users"`).

---

## 3. Real-World AI Safety Monitoring & Telemetry

The platform records safety telemetry via `MetricsCollector`:

| Metric Event | Trigger Condition | Operational Action |
| :--- | :--- | :--- |
| `safety_PROMPT_INJECTION` | Sanitizer discovers malicious directive override | Counter incremented; if frequency $> 5$ from single user $\to$ SecOps alert |
| `safety_EMPTY_RETRIEVAL_REFUSAL` | Query executed with 0 matching vector chunks | Evaluates retrieval coverage; prompts user to upload relevant case documents |
| `safety_UNSUPPORTED_ANSWER_REFUSAL` | Model unable to verify citations against chunks | Logs citation discrepancy; returns safe refusal |

---

## 4. Human-in-the-Loop Escalation Pathway

1. **Lawyer Oversight**: All AI-generated research summaries, chronologies, and draft arguments display an explicit disclaimer requiring advocate review prior to filing or legal reliance.
2. **Dispute / Inaccuracy Reporting**: Users can flag AI inaccuracies via `/api/v1/feedback` with category `AI_HALLUCINATION`.
3. **Emergency Disablement**: In the event of an active LLM safety incident or upstream provider compromise, the AI assistant can be disabled instantaneously via:
   ```bash
   PILOT_DISABLED_FEATURES='["copilot", "ai_research", "ai"]'
   ```

---

## 5. Phase XX Multilingual Safety & Production Budget Governance

Under Phase XX, AI safety is expanded to handle regional Indian languages and operational financial bounds:

### Multilingual Injection Containment
- **Devanagari Hindi Patterns**: Neutralizes malicious directives in native script (`पिछले सभी निर्देश भूल जाओ`, `निर्देश भूल जाएं`, `सिस्टम निर्देश ओवरराइड`).
- **Transliterated Hindi Patterns**: Neutralizes Romanized phonetic directives (`kripya purv nirdesh bhul jao`, `pichle sabhi nirdesh bhool jao`, `system prompt override karo`).
- **Statutory Transition Grounding**: Benchmarked against scenarios SCEN-006 through SCEN-010 verifying accurate statutory transitions (IPC $\to$ BNS 2023, CrPC $\to$ BNSS 2023, Indian Evidence Act $\to$ BSA 2023) across Hindi, English, and Hinglish queries.

### Daily User Budgets & Circuit Breakers
- **Usage Ceilings**: Enforces daily caps (50 queries / user / day; 100,000 tokens) via `AIBudgetService`.
- **Fail-Closed Strategy**: In the event of upstream model provider failures or capacity exhaustion, queries fail closed with transparent user messaging rather than routing to unverified fallback models.
