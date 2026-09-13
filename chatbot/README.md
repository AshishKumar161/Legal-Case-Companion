# LCC Starter — Agentic Pipeline + Eval Harness

Two files, both skeletons meant to be filled in, not run as-is for real answers.

## `pipeline.py` — the agentic graph
Intake → Retrieve → Rerank → Draft → Verify → Escalation gate, built with
LangGraph. The state shape (`LCCState`) and the escalation gate are the parts
worth keeping exactly as structured — they're what let you demo "this system
refuses to guess" live, and what the eval harness measures against.

Every `# TODO` marks a spot to wire in your real vector DB (Qdrant/Weaviate),
reranker (BGE-reranker or Cohere Rerank), and LLM calls.

```
pip install langgraph langchain-core pydantic --break-system-packages
python pipeline.py
```

## `eval.py` — proving the numbers, not just claiming them
Uses RAGAS to score faithfulness, answer relevancy, context precision, and
context recall against a labeled test set you build. Start with the 5
shortlisted crime categories from the roadmap (cyber fraud, crimes against
women, cheating/forgery, theft/burglary, crimes against senior citizens) so
your score isn't skewed toward one easy case type.

```
pip install ragas datasets --break-system-packages
python eval.py
```

## `dataset_pipeline.py` — 3-year District Court dataset for case-similarity matching
Turns raw case JSON (see `case_schema_example.json`) into a clean, deduped,
auto-classified, embedding-ready dataset scoped to **District Courts only,
2023–2025**, filtered to the 5 shortlisted crime categories.

Where the raw cases come from (you collect these — no bulk scraper included
on purpose, since eCourts/NJDG rate-limit and ToS restrict automated bulk
pulls):
- **eCourts Judgment Search** (judgments.ecourts.gov.in) — individual lookup, free
- **Indian Kanoon** — has a paid API for structured bulk access, cheapest realistic route to volume
- **NJDG** — richest source but its open API needs a government departmental ID/key; not realistic for a student team without an institutional tie-up — mention as a "Phase 2, with institutional access" line, don't plan the prototype around it

**Realistic scope for the prototype: 300–500 curated cases**, not a full
3-year nationwide scrape — that's what actually fits a hackathon timeline
and still makes "find similar cases" genuinely demoable.

```
mkdir raw_cases          # drop one .json file per case here, matching case_schema_example.json
pip install sentence-transformers qdrant-client --break-system-packages
python dataset_pipeline.py
```

Output: `processed/district_court_cases_2023_2025.json` — ready to embed and
push into the same vector DB your `retriever_agent` (in `pipeline.py`) queries
against, with metadata (`crime_category`, `state`, `year`) for filtering
combined with semantic similarity on `embedding_text`.

1. Get `pipeline.py` running end-to-end with placeholder data (it already
   does — try it now).
2. Swap in a real vector DB + a handful of real statute/case chunks for one
   crime category (start with cyber fraud — see roadmap Part 5).
3. Swap in a real LLM call for the drafter and critic agents.
4. Add a real reranker.
5. Build a 20-30 row test set in `eval.py` for that one category, run it,
   get a real faithfulness number.
6. Repeat for the remaining 4 categories, then widen the test set.

By the time you're demoing, you want: a working pipeline, a real confidence
score shown per answer, at least one live escalation triggered on purpose,
and one eval number on a slide that you can defend if a judge asks "how do
you know it's accurate?"
