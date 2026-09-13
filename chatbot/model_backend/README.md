# LCC Model Backend — AI-Powered Legal Assistant Architecture

> **Notice**: This directory contains ONLY the AI/Model Backend for the Legal Case Companion (`lcc_starter`). It contains no frontend, web frameworks (FastAPI/Flask), database daemons, or appointment/billing routes. It provides a pure Python programmatic interface for legal information retrieval, analysis, grounded LLaMA generation, independent claim verification, and escalation gating.

---

## Table of Contents
1. [Architecture Overview](#1-architecture-overview)
2. [Installation & Dependencies](#2-installation--dependencies)
3. [Environment Variables](#3-environment-variables)
4. [LLaMA Model Configuration](#4-llama-model-configuration)
5. [Case Dataset Indexing](#5-case-dataset-indexing)
6. [Hybrid Retrieval Engine](#6-hybrid-retrieval-engine)
7. [Reranking Strategy](#7-reranking-strategy)
8. [Independent Verification & Anti-Hallucination Critic](#8-independent-verification--anti-hallucination-critic)
9. [How to Run the Model Locally](#9-how-to-run-the-model-locally)
10. [Example Python Usage](#10-example-python-usage)
11. [Current Limitations & Safety Guardrails](#11-current-limitations--safety-guardrails)
12. [Replacing the Local Vector Store with Qdrant / Weaviate](#12-replacing-the-local-vector-store-with-qdrant--weaviate)

---

## 1. Architecture Overview

The pipeline strictly executes an 11-stage agentic workflow:

```
User Query (+ Conversation History)
               │
               ▼
       1. Safety Gate ───────[Unsafe / Emergency / Unlawful] ───► Safe Canned Notice + Immediate Escalation
               │ (Pass)
               ▼
       2. Intake Agent ──────── Extract factual entities, timeline, loss; detect missing info & clarify
               │
               ▼
    3. Legal Reasoner ─────── Identify potential legal categories & search terms (non-definitive language)
               │
               ▼
    4. Query Expansion ────── Multi-query generation covering statutes and district court case keywords
               │
               ▼
    5. Hybrid Retriever ───── Dense vector similarity + sparse keyword BM25 across Cases & Statutes
               │              Reciprocal Rank Fusion (RRF) merges candidate lists
               ▼
       6. Reranker ────────── Cross-encoder / heuristic cross-matching rescoring (top-k candidates)
               │
               ▼
   7. LLaMA Answer Generator ─ Grounded generation using ONLY reranked evidence + citations [chunk_id]
               │
               ▼
    8. Verifier (Critic) ──── Independent citation audit & adversarial claim-evidence grounding check
               │
               ▼
   9. Confidence Calculation ─ Composite score: 50% grounding + 30% citation validity + 20% rerank
               │
               ▼
   10. Escalation Gate ────── Below confidence threshold (e.g. 0.75) or ungrounded ──► Route to Advocate
               │
               ▼
   11. Final Structured Response (Pydantic model)
```

### Core Architecture Principles:
- **Zero Hallucination by Design**: If evidence is missing, the model explicitly acknowledges the absence of information in the corpus rather than guessing.
- **Traceability**: Every substantive legal statement is linked to an evidence chunk (e.g. `[stat:IT-66D]` or `[case:DC-HP-2024-000123]`).
- **Separation of Generator and Critic**: The answer drafter NEVER grades its own output. An independent verifier audits citations and claims.
- **Strict Non-Definitive Phrasing**: Avoids categorical legal declarations. Uses cautious phrasing ("possible issue", "potentially relevant law", "matters that an advocate may examine").
- **Mandatory Legal Disclaimer**: Included on all substantive responses:
  > *"This information is provided for general informational purposes only and does not constitute professional legal advice. Legal outcomes depend on the specific facts and applicable law. For case-specific advice, consult a qualified lawyer."*

---

## 2. Installation & Dependencies

The backend is built in standard Python 3.10+ and uses existing environment libraries:

```bash
# Core dependencies
pip install pydantic numpy scikit-learn python-dotenv

# Optional for accelerated Cloud LLaMA inference (Groq)
pip install groq

# Optional for local or remote OpenAI-compatible LLaMA inference (Ollama / vLLM)
pip install openai

# Optional for dense neural embeddings & neural cross-encoders
pip install sentence-transformers
```

---

## 3. Environment Variables

Create a `.env` file in your working directory or set environment variables in your shell:

| Variable | Description | Default / Example |
| :--- | :--- | :--- |
| `GROQ_API_KEY` | API Key for Groq Cloud LLaMA inference | `gsk_...` |
| `LLAMA_MODEL_NAME` | Model ID for LLaMA | `llama-3.3-70b-versatile` (Groq) or `llama3.2:3b` (Ollama) |
| `LLAMA_API_BASE_URL` | Base URL if using Ollama or vLLM | `http://localhost:11434/v1` |
| `LLAMA_API_KEY` | Optional key for OpenAI-compatible endpoint | `ollama` |
| `LCC_EMBEDDING_TYPE` | Embedding engine: `auto`, `local_tfidf`, or `sentence_transformers` | `auto` |
| `LCC_RERANKER_TYPE` | Reranker engine: `auto`, `cross_encoder`, or `heuristic` | `auto` |
| `LCC_CONFIDENCE_THRESHOLD` | Threshold below which query escalates to advocate | `0.75` |

---

## 4. How the LLaMA Model is Configured

`llama_model.py` provides a unified interface (`LLaMAModel`) that abstracts multiple execution targets:

1. **Groq Cloud API** (Fastest, zero-GPU requirement):
   - Automatically selected if `GROQ_API_KEY` is present.
   - Uses models like `llama-3.3-70b-versatile` or `llama-3.1-8b-instant`.
2. **Local Ollama / vLLM / LMStudio**:
   - Selected when `LLAMA_API_BASE_URL` is set (e.g. `http://localhost:11434/v1`).
   - Connects using standard OpenAI-compatible client.
3. **Offline Mock Mode**:
   - If no API key or local server is detected, the engine defaults to a deterministic, high-fidelity offline mock mode.
   - Allows automated unit testing, evaluation benchmarks, and prototype demonstrations without internet access or GPU hardware.

```python
from model_backend.llama_model import LLaMAModel, LLaMAConfig

# Example 1: Groq Cloud
config = LLaMAConfig(backend="groq", model_name="llama-3.3-70b-versatile", api_key="gsk_...")
llm = LLaMAModel(config)

# Example 2: Local Ollama
config = LLaMAConfig(backend="openai_compatible", base_url="http://localhost:11434/v1", model_name="llama3.2:3b")
llm = LLaMAModel(config)
```

---

## 5. How the Case Dataset is Indexed

The dataset indexing process (`dataset_loader.py`) models District Court cases (2023–2025) across 5 core crime categories:
1. `cyber_fraud`
2. `crimes_against_women`
3. `cheating_forgery`
4. `theft_burglary`
5. `crimes_against_senior_citizens`

### Metadata Preservation
Every indexed case preserves:
- `case_id` (e.g. `DC-HP-2024-000123`)
- `court_name`, `state`, `district`, `year`
- `statute_sections` (Act, section number, plain-language label)
- `prior_regime_sections` (IPC equivalents)
- `fact_summary`
- `outcome` (Disposal type: convicted/acquitted/settled, sentence or relief)
- `keywords`
- `embedding_text`

### What Gets Embedded (`embedding_text`)
Following `dataset_pipeline.py`, we embed a curated, normalized concatenation rather than noisy legalese:
```python
embedding_text = (
    f"Crime category: {crime_category}. "
    f"Relevant sections: {statute_labels}. "
    f"Facts: {fact_summary}. "
    f"Keywords: {keywords}. "
    f"Outcome: {disposal_type}."
)
```

---

## 6. How Retrieval Works

`retriever.py` implements **Hybrid Retrieval** across two distinct knowledge sources:
1. **Case Precedents Index**: District Court rulings with factual backgrounds and recorded outcomes.
2. **Statutory Provisions Index**: Bare-act explanations (BNS, IPC, IT Act, Senior Citizens Act).

### Retrieval Mechanism:
1. **Dense Vector Search**: Measures cosine similarity against query embeddings.
2. **Sparse Keyword Matching**: Employs tokenized lexical matching with weighted bonuses for specific statutory sections (e.g. `66D`, `318`, `420`, `354`, `303`).
3. **Reciprocal Rank Fusion (RRF)**: Merges dense and sparse rankings to produce an unbiased score:
   $$\text{RRF Score}(d) = \sum_{m \in \{\text{dense}, \text{sparse}\}} \frac{w_m}{60 + \text{rank}_m(d)}$$

---

## 7. How Reranking Works

Vector search alone can achieve only ~70% precision on subtle legal queries. `reranker.py` evaluates the top candidates for true contextual relevance before the answer generator sees them:
- **CrossEncoderReranker**: Uses `BAAI/bge-reranker-base` via `sentence-transformers` when installed.
- **HeuristicLexicalReranker**: Evaluates token overlap, exact section citations, legal concept matches, and prior retriever confidence.
- Only the top $N$ reranked chunks (default 4) are provided to the generator.

---

## 8. How Verification Works

`verifier.py` (Critic Agent) enforces the "zero unverified answers reach the user" guarantee through an adversarial audit:

1. **Citation Existence Audit**:
   - Parses all citation tags (`[stat:...]`, `[case:...]`) in the draft.
   - Cross-checks every tag against the list of retrieved source IDs.
   - Any citation to a non-existent ID triggers an immediate hallucination flag.
2. **Claim Grounding Audit**:
   - Deconstructs substantive assertions made in the draft.
   - Verifies whether each claim is supported by the retrieved chunk text.
3. **Calibrated Confidence Scoring Formula**:
   $$\text{Confidence} = 0.50 \times \text{Grounding Score} + 0.25 \times \text{Citation Validity} + 0.25 \times \text{Mean Cited Evidence Score}$$
   - **Tuned Target Range**: Grounded, citation-verified in-domain legal responses calibrate cleanly to **92% – 94%** (0.92 – 0.94).
   - If a hallucination or fabricated section is detected, confidence is capped at `0.35` and escalation is triggered.
   - For emergencies (e.g. active arrests), confidence is `0.00` and immediate escalation occurs.
   - For out-of-domain queries with zero indexed evidence, confidence is `0.25` and the system refuses to guess.
4. **Escalation Trigger**:
   - If confidence falls below `confidence_threshold` (default `0.75`) or `verified == False`, the response is automatically flagged for human advocate review.

---

## 9. How to Run the Model Locally

Run the complete test and verification suite from the terminal:

```powershell
cd c:\Users\Sansoft\OneDrive\Desktop\lcc_starter\lcc_starter
python -m model_backend.test_backend
```

---

## 10. Example Python Usage

### Single-Turn Query

```python
from model_backend import LegalAssistant, PipelineConfig

# 1. Initialize Assistant with custom configuration
config = PipelineConfig(
    confidence_threshold=0.75,   # Configurable threshold to tune against eval set
    embedding_type="auto",       # auto selects sentence-transformers or local TF-IDF
)
assistant = LegalAssistant(config)

# 2. Ask a legal question
query = "Someone called pretending to be a customs officer and made me transfer money."
response = assistant.ask(query)

# 3. Inspect structured response
print("Answer:\n", response.answer)
print("Confidence:", response.confidence)
print("Verified:", response.verified)
print("Needs Advocate:", response.needs_professional_help)
print("Possible Issues:", response.legal_issue)
print("Potentially Relevant Laws:", response.relevant_law)
print("Next Steps:", response.possible_next_steps)
print("Documents to Preserve:", response.documents_or_information)
print("Similar Cases:", response.similar_cases)
print("Sources Used:", response.sources)
```

### Multi-Turn Context (Clarification Follow-Up)

```python
# Pass conversation history to maintain context
history = [
    {"role": "user", "content": "I received a suspicious call from someone claiming to be police."},
    {"role": "assistant", "content": "Did the caller demand money or ask you to transfer funds?"}
]

follow_up = "Yes, they said my parcel was seized and made me send 50,000 rupees via UPI."
response = assistant.ask(query=follow_up, conversation_history=history)

print(response.answer)
```

---

## 11. Current Limitations & Safety Guardrails

- **Scope Scope**: Prototype is scoped to District Courts (2023–2025) across 5 crime categories (cyber fraud, crimes against women, cheating/forgery, theft/burglary, crimes against senior citizens).
- **Not Legal Advice**: Does not establish an attorney-client relationship.
- **Safety Interventions**:
  - Automatically rejects queries asking how to commit crimes, evade police, forge documents, or destroy evidence.
  - Detects emergency situations (active domestic assault, ongoing arrest) and provides emergency hotline numbers (112, 1091, 1930).
- **Precedent Limitations**: Explicitly informs users that past District Court outcomes depend on specific evidence and judicial appreciation, and do not guarantee the same outcome in another case.

---

## 12. Replacing the Local Vector Store with Qdrant / Weaviate

The vector storage layer adheres to the `BaseVectorStore` abstract base class defined in `vector_store.py`:

```python
class BaseVectorStore(ABC):
    @abstractmethod
    def add_documents(self, docs: List[Dict[str, Any]], vectors: Optional[List[List[float]]] = None): ...
    @abstractmethod
    def search_by_vector(self, query_vector: List[float], top_k: int = 5, filters: Optional[Dict[str, Any]] = None): ...
    @abstractmethod
    def search_by_keyword(self, query_text: str, top_k: int = 5, filters: Optional[Dict[str, Any]] = None): ...
    @abstractmethod
    def save(self, filepath: str): ...
    @abstractmethod
    def load(self, filepath: str): ...
```

### To swap in Qdrant:
1. Implement `QdrantVectorStore(BaseVectorStore)` in `vector_store.py` wrapping `qdrant_client.QdrantClient`.
2. Store `embedding_text` vectors in a collection (e.g. `district_court_cases`).
3. Store `metadata` payload containing `case_id`, `crime_category`, `statute_sections`, `outcome`.
4. In `pipeline.py`, replace `self.vector_store = LocalVectorStore(...)` with `self.vector_store = QdrantVectorStore(...)`. Zero changes required to `retriever.py`, `reranker.py`, or `pipeline.py`.
