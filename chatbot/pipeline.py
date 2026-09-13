"""
LCC Agentic Pipeline — starter skeleton
========================================
Intake -> Retrieve -> Rerank -> Draft -> Verify -> Escalate-or-Answer

This is a SKELETON meant to be filled in with your real vector DB,
reranker, and LLM calls. Every place you need to plug something in
is marked with `# TODO`. The graph structure, state shape, and the
escalation gate are the parts worth keeping as-is — they're what
make the "zero unverified answers reach the user" claim demonstrable
in a judging round.

Install:
    pip install langgraph langchain-core pydantic --break-system-packages

Run:
    python pipeline.py
"""

from __future__ import annotations
from typing import TypedDict, List, Optional
from langgraph.graph import StateGraph, END


# ---------------------------------------------------------------------------
# 1. State — everything that flows through the graph, stage by stage.
#    Keeping this explicit (vs. a single prompt string) is what makes the
#    pipeline inspectable in your demo.
# ---------------------------------------------------------------------------

class RetrievedChunk(TypedDict):
    chunk_id: str
    source: str          # e.g. "BNS Section 318" or "Case: State v. X (2023)"
    text: str
    relevance_score: float


class LCCState(TypedDict):
    raw_query: str
    clarified_facts: Optional[str]       # filled by Intake Agent
    retrieved: List[RetrievedChunk]      # filled by Retriever Agent
    reranked: List[RetrievedChunk]       # filled by Reranker
    draft_answer: Optional[str]          # filled by Drafter Agent
    draft_citations: List[str]           # chunk_ids the drafter actually used
    verification_notes: Optional[str]    # filled by Critic Agent
    confidence: float                    # 0.0 - 1.0, set by Critic Agent
    final_output: Optional[str]
    escalated: bool


CONFIDENCE_THRESHOLD = 0.75  # tune this against your eval set (see eval.py)


# ---------------------------------------------------------------------------
# 2. Agent nodes
# ---------------------------------------------------------------------------

def intake_agent(state: LCCState) -> LCCState:
    """
    Turns a raw citizen/lawyer query into a clarified fact pattern.
    In production: this is where you'd run a follow-up-question loop
    ("did money leave your account?" / "was an FIR filed?") until the
    fact pattern is specific enough to retrieve against.
    """
    # TODO: replace with a real LLM call that asks clarifying questions
    # or accepts a pre-clarified fact pattern from a multi-turn UI.
    state["clarified_facts"] = state["raw_query"]
    return state


def retriever_agent(state: LCCState) -> LCCState:
    """
    Hybrid search (BM25 keyword + dense vector) across >=2 independent
    sources: bare-act text store + case-law store. Returning candidates
    from two separate indexes (not one merged index) is what lets you
    show "two sources agree" in the demo UI.
    """
    # TODO: replace with real calls, e.g.:
    #   statute_hits = qdrant_client.search(collection="statutes", ...)
    #   case_hits    = qdrant_client.search(collection="case_law", ...)
    state["retrieved"] = [
        {
            "chunk_id": "demo-1",
            "source": "BNS Section 318 (Cheating)",
            "text": "Placeholder statute text — replace with real retrieval.",
            "relevance_score": 0.0,
        },
    ]
    return state


def reranker_node(state: LCCState) -> LCCState:
    """
    Re-scores retrieved chunks for TRUE relevance before the drafter sees
    them. This is the highest-leverage, most-skipped step in student RAG
    projects. Vector search alone is often only ~70% precise.
    """
    # TODO: replace with a real cross-encoder reranker, e.g. Cohere Rerank
    # or an open-source BGE-reranker model:
    #
    #   from sentence_transformers import CrossEncoder
    #   reranker = CrossEncoder("BAAI/bge-reranker-base")
    #   pairs = [(state["clarified_facts"], c["text"]) for c in state["retrieved"]]
    #   scores = reranker.predict(pairs)
    #
    reranked = sorted(state["retrieved"], key=lambda c: c["relevance_score"], reverse=True)
    state["reranked"] = reranked[:5]  # keep top-k
    return state


def drafter_agent(state: LCCState) -> LCCState:
    """
    Writes the answer using ONLY the reranked chunks. Every sentence
    must be traceable to a chunk_id — that traceability is what the
    Critic Agent checks next, and what becomes the citation-chip UI.
    """
    # TODO: replace with a real LLM call, prompted to cite chunk_ids
    # inline, e.g. "...falls under cheating [demo-1]."
    context = "\n".join(f"[{c['chunk_id']}] {c['text']}" for c in state["reranked"])
    state["draft_answer"] = f"(placeholder draft grounded in: {context})"
    state["draft_citations"] = [c["chunk_id"] for c in state["reranked"]]
    return state


def critic_agent(state: LCCState) -> LCCState:
    """
    Independently re-checks the draft against the retrieved sources.
    Flags any claim that doesn't trace back to a real chunk, and
    produces the confidence score that drives the escalation gate.

    Run this as a SEPARATE model call from the drafter (or a rules/
    regex citation-matching layer) — never let the drafter grade its
    own work.
    """
    # TODO: replace with a real verifier call. A simple starting rule:
    # confidence = (# citations that exist in reranked set) / (# claims made)
    cited_ids = set(state["draft_citations"])
    available_ids = {c["chunk_id"] for c in state["reranked"]}
    grounded = cited_ids.issubset(available_ids) and len(cited_ids) > 0

    state["confidence"] = 0.93 if grounded else 0.3
    state["verification_notes"] = (
        "All citations traced to retrieved sources."
        if grounded else
        "One or more citations could not be verified against retrieved sources."
    )
    return state


def escalation_gate(state: LCCState) -> LCCState:
    """
    The last line of defense. Below threshold -> don't answer, escalate.
    This is the node that makes "zero unverified answers reach the user"
    a demonstrable claim rather than a slogan.
    """
    if state["confidence"] >= CONFIDENCE_THRESHOLD:
        state["final_output"] = state["draft_answer"]
        state["escalated"] = False
    else:
        state["final_output"] = (
            "Insufficient evidence to answer confidently. "
            "This query has been routed to an advocate for review."
        )
        state["escalated"] = True
    return state


# ---------------------------------------------------------------------------
# 3. Build the graph
# ---------------------------------------------------------------------------

def build_graph():
    graph = StateGraph(LCCState)

    graph.add_node("intake", intake_agent)
    graph.add_node("retrieve", retriever_agent)
    graph.add_node("rerank", reranker_node)
    graph.add_node("draft", drafter_agent)
    graph.add_node("verify", critic_agent)
    graph.add_node("gate", escalation_gate)

    graph.set_entry_point("intake")
    graph.add_edge("intake", "retrieve")
    graph.add_edge("retrieve", "rerank")
    graph.add_edge("rerank", "draft")
    graph.add_edge("draft", "verify")
    graph.add_edge("verify", "gate")
    graph.add_edge("gate", END)

    return graph.compile()


if __name__ == "__main__":
    app = build_graph()

    initial_state: LCCState = {
        "raw_query": "Someone called claiming to be from customs and scared me into transferring money.",
        "clarified_facts": None,
        "retrieved": [],
        "reranked": [],
        "draft_answer": None,
        "draft_citations": [],
        "verification_notes": None,
        "confidence": 0.0,
        "final_output": None,
        "escalated": False,
    }

    result = app.invoke(initial_state)

    print("=== LCC Pipeline Result ===")
    print("Escalated to human review:", result["escalated"])
    print("Confidence:", result["confidence"])
    print("Verification notes:", result["verification_notes"])
    print("Final output:\n", result["final_output"])
