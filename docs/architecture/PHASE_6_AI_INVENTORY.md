# Phase 6: Complete AI Architecture & LLM Inventory

This inventory documents all AI/LLM-related components within the Legal Case Companion (LCC) repository, their responsibilities, callers, dependencies, providers, prompt builders, output formats, audit logging mechanisms, and consolidation status classifications.

---

## 1. Inventory Matrix

| File | Responsibility | Callers | Dependencies | Provider | Prompt Builder | Output Format | Audit Logging | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `app/core/ai_config.py` | Canonical configuration for model names, temperatures, max tokens, timeouts, retries, backoff, and prompt versions | `app.providers.ai.*`, `app.services.*` | `pydantic`, `app.core.config` | N/A (Config) | N/A | Configuration Dataclasses | N/A | **KEEP** |
| `app/core/ai_exceptions.py` | Normalized application-level AI exceptions preventing provider SDK leakages | `app.providers.ai.*`, `app.services.*` | `app.core.exceptions.AppException` | N/A (Exceptions) | N/A | Exception Objects | Logged at handler | **KEEP** |
| `app/providers/ai/base.py` | Canonical `AIProvider` Protocol, `TokenUsage`, and execution metadata abstractions | `app.providers.ai.*`, `app.services.*` | `typing.Protocol`, `pydantic` | Abstract Protocol | N/A | Typed Protocol / Dataclasses | Provider metadata | **KEEP** |
| `app/providers/ai/openai.py` | Production OpenAI provider implementation with retry classification, backoff, and normalized error translation | `app.providers.ai.factory` | `openai`, `app.core.ai_config`, `app.core.ai_exceptions` | OpenAI API | N/A | Text / JSON Dict | Execution token usage | **KEEP** |
| `app/providers/ai/mock.py` | Canonical mock AI provider supporting deterministic scenario configuration, grounding mocks, and latency simulation | `app.providers.ai.factory`, test fixtures | `app.core.ai_config`, `app.providers.ai.base` | Mock Provider | N/A | Text / JSON Dict | Simulated token usage | **KEEP** |
| `app/providers/ai/factory.py` | Dependency injection factory for canonical AI provider instances based on application runtime settings | Application services, tests | `app.core.config`, `app.providers.ai.*` | Selected canonical provider | N/A | `AIProvider` instance | Factory logging | **KEEP** |
| `app/services/ai_prompt_policy.py` | Centralized prompt security policy, multilingual injection defense, delimiter tag defanging, and safe context assembly | `assistant_service.py`, `ai_conversation_service.py`, `ai_research_service.py` | `re`, `json`, `html` | N/A | Canonical Prompt Policy | Structured Prompts | Injection flags | **KEEP** |
| `app/services/ai_provider.py` | Legacy provider module converted into backward-compatible facade delegating to `app.providers.ai` | `assistant_service.py`, legacy tests | `app.providers.ai.factory` | Delegated Canonical Provider | Facade methods | Text / Dict | Delegated | **MERGE / FACADE** |
| `app/services/llm_provider.py` | Secondary legacy LLM provider converted into backward-compatible facade delegating to `app.providers.ai` | `ai_conversation_service.py`, legacy tests | `app.providers.ai.factory` | Delegated Canonical Provider | Facade methods | Text / Dict | Delegated | **MERGE / FACADE** |
| `app/services/assistant_service.py` | Core Case Assistant orchestration: retrieval, prompt generation, LLM execution, grounding, and citation validation | `app/api/v1/cases.py`, `app/api/v1/assistant.py` | `AIProvider`, `ClaimVerifier`, `AIBudgetService`, `AuditService` | `app.providers.ai` | `SafeContextBuilder` | `AssistantResponse` | Case Audit Log | **KEEP** |
| `app/services/ai_conversation_service.py` | Multi-turn conversational AI orchestration, message history assembly, context bounds, and budget enforcement | `app/api/v1/ai_conversations.py` | `AIProvider`, `AIBudgetService`, `SafeContextBuilder` | `app.providers.ai` | `SafeContextBuilder` | `AIConversationMessage` | Conversation Audit Log | **KEEP** |
| `app/services/ai_research_service.py` | Legal research queries, statute and case law synthesis, authority ranking | `app/api/v1/legal_research.py` | `AIProvider`, `SafeContextBuilder`, `AIBudgetService` | `app.providers.ai` | `SafeContextBuilder` | Research Report Dict | Research Audit Log | **KEEP** |
| `app/services/claim_verifier.py` | Independent claim verification against cited chunks and legal authorities; token/semantic overlap validation | `assistant_service.py`, test suites | `app.schemas.assistant` | N/A | N/A | `VerificationResult` | Verification status | **KEEP** |
| `app/services/ai_budget_service.py` | AI token budget and query quota enforcement per user/organization with concurrency locks and refund semantics | API endpoints, AI services | `app.models.ai_budget`, `sqlalchemy` | N/A | N/A | Quota Status / Boolean | Audit ledger entries | **KEEP** |
| `app/schemas/assistant.py` | Authoritative Pydantic schemas for assistant requests, legal answers, claims, citations, and grounding states | AI services, API routes | `pydantic` | N/A | N/A | Pydantic Models | N/A | **KEEP** |
| `app/schemas/ai_conversation.py` | Pydantic schemas for multi-turn conversations, participant messages, context limits | AI conversation API | `pydantic` | N/A | N/A | Pydantic Models | N/A | **KEEP** |

---

## 2. Overlapping Implementations & Consolidation Decision

### Comparison of Duplicate Stacks:
- **Stack A (`app/services/ai_provider.py`):** Originally an OpenAI client wrapper with hardcoded retry logic, JSON formatting, and basic mock fallbacks. Used by `assistant_service.py`.
- **Stack B (`app/services/llm_provider.py`):** A secondary implementation with overlapping methods (`generate_response`, `generate_structured_response`), slightly different parameter names, and duplicate retry loops. Used by `ai_conversation_service.py`.

### Consolidation Strategy:
1. **Canonical Engine:** Created `app/providers/ai/` implementing the `AIProvider` Protocol (`app/providers/ai/base.py`), backed by `CanonicalOpenAIProvider` (`openai.py`) and `CanonicalMockAIProvider` (`mock.py`), dynamically provided via `factory.py`.
2. **Backward-Compatible Facades:** Both `app/services/ai_provider.py` and `app/services/llm_provider.py` are preserved as backward-compatible facades delegating directly to `get_canonical_ai_provider()`. This prevents breaking legacy imports or tests while unifying all AI traffic through one hardened pipeline.
3. **Prompt & Context Unification:** Replaced ad-hoc pseudo-XML string formatting across all services with `PromptSecurityPolicy` and `SafeContextBuilder` in `app/services/ai_prompt_policy.py`.
