# Phase 6: Canonical AI Architecture & Pipeline Specification

## 1. Canonical Provider Architecture

The Legal Case Companion (LCC) AI architecture enforces strict separation of concerns, decoupling business and legal domain logic from underlying LLM SDKs and external network protocols.

```
+-------------------------------------------------------------------------+
|                              Application API Layer                      |
|                  (/cases/ask, /conversations, /legal-research)          |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
|                         AI Domain Orchestrator Services                 |
|             (AssistantService, AIConversationService, AIResearchService) |
+-------------------------------------------------------------------------+
       |                                   |                    |
       v                                   v                    v
+-----------------------+        +-------------------+  +-----------------+
| Safe Context Builder  |        | AIBudgetService   |  | Audit & Metrics |
| & Prompt Policy       |        | (Pre-LLM Lock)    |  | Logging         |
+-----------------------+        +-------------------+  +-----------------+
       |
       v
+-------------------------------------------------------------------------+
|                  Canonical AIProvider Protocol (base.py)                |
+-------------------------------------------------------------------------+
                      |                                   |
                      v                                   v
+-----------------------------------------+ +-----------------------------+
| CanonicalOpenAIProvider (openai.py)     | | CanonicalMockAIProvider     |
| - Exponential Backoff & Transient Retry | | (mock.py)                   |
| - Normalized AIExceptions               | | - Deterministic Scenarios   |
| - Token & Cost Accounting               | | - Test Injections           |
+-----------------------------------------+ +-----------------------------+
```

### 1.1 Canonical Protocol Interface (`app/providers/ai/base.py`)
All AI providers conform to the `AIProvider` Protocol:
- `generate(system_prompt, user_prompt, temperature, max_tokens) -> str`: Unstructured text generation with transient retry and error normalization.
- `generate_structured(system_prompt, user_prompt, schema, candidate_chunks, authority_provisions, temperature) -> dict[str, Any]`: JSON-enforced structured generation with schema conformance.
- `embed(texts) -> list[list[float]]`: High-dimensional text embeddings for vector indexing.
- `health_check() -> bool`: Provider liveness validation.

### 1.2 Provider Factory (`app/providers/ai/factory.py`)
Providers are instantiated via `get_canonical_ai_provider()`. In test environments or when `USE_MOCK_AI=True`, `CanonicalMockAIProvider` is selected. In production, `CanonicalOpenAIProvider` is loaded with credentials verified from `app.core.config.settings`.

---

## 2. Standardized AI Request Flow

The canonical request pipeline follows an invariant 8-stage sequence:

1. **Authorization & Validation:** Caller identity, tenant isolation, and case/document ownership are validated before any AI processing.
2. **Deterministic Context Construction:** `SafeContextBuilder` bounds chunk counts, extracts relevant authorities, and safely escapes metadata delimiters into structured objects.
3. **Prompt Policy Assembly:** `PromptSecurityPolicy` defangs untrusted injection sequences, embeds delimiter tags (`<case_data>`, `<legal_authorities>`, `<user_query>`), and applies strict system instructions.
4. **Pre-Execution Quota & Budget Check:** `AIBudgetService.consume_budget()` atomically checks and debits tokens before sending external requests.
5. **Provider Execution:** The provider executes with retry on transient network errors (HTTP 429, 500, 503, timeouts), while non-transient errors (400, 401, 403) fail immediately.
6. **Structured Output Validation:** Raw JSON responses are validated against Pydantic models (`LegalAnswer`, `AssistantResponse`). Invalid payloads trigger normalized `AIInvalidResponseError`.
7. **Grounding & Independent Verification:**
   - Citations are strictly cross-referenced against candidate chunks and retrieved statutes. Unmatched citations are flagged or dropped.
   - Claims are validated independently by `ClaimVerifier` through token/semantic overlap against cited sources.
   - Grounding status is classified deterministically (`SUPPORTED`, `PARTIALLY_SUPPORTED`, `UNSUPPORTED`, `INSUFFICIENT_EVIDENCE`).
8. **Audit & Response Serialization:** Audit entries are recorded with execution latency, token counts, actual model name, prompt version, and grounding outcome before returning the final response.

---

## 3. Centralized Model Configuration (`app/core/ai_config.py`)

All model parameters are centralized in `AI_CONFIG`:
- **Default Chat Model:** `gpt-4o` (overrideable via `settings.AI_MODEL`)
- **Default Embedding Model:** `text-embedding-3-small`
- **Default Temperatures:** 0.1 for high-precision legal extraction, 0.3 for conversational summarization
- **Maximum Output Tokens:** 2048
- **Maximum Context Chunks:** 10 candidate document chunks
- **Maximum Authorities:** 5 legal statutes/provisions
- **Timeout:** 30.0 seconds
- **Max Retries:** 3 attempts with exponential backoff factor of 2.0

---

## 4. Prompt Versioning & Audit Metadata

Every prompt template maintains a formal version string:
- `case_assistant_v1`: RAG question answering over legal case records and statutes.
- `ai_conversation_v1`: Multi-turn conversational legal research and advice.
- `legal_research_v1`: Standalone statutory and case precedent exploration.

These versions are recorded in all audit logs alongside the actual model executed and token consumption metrics.

---

## 5. Deprecation and Facade Migration

Legacy AI modules `app/services/ai_provider.py` and `app/services/llm_provider.py` have been converted into lightweight facades. They forward calls to `app/providers/ai/factory.py` and normalize output structures, guaranteeing 100% backward compatibility for existing callers and test fixtures.
