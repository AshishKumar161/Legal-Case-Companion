"""
LCC Dataset Pipeline — 3-year District Court case dataset for similarity matching
====================================================================================
Turns a folder of raw case records (JSON, matching case_schema_example.json) into
a clean, deduplicated, embedded dataset your retriever_agent can query against.

Scope by design: District Courts only, last 3 years (2023-2025), limited to the
5 shortlisted crime categories. This is intentional — a full nationwide scrape
is out of scope for a hackathon; a curated 300-500 case set is enough to make
"find similar cases" genuinely work and be demoable.

Pipeline stages:
    1. load_raw_cases()      -> read your collected JSON records
    2. validate_and_clean()  -> drop incomplete/duplicate records
    3. classify_if_missing() -> rule-based statute-section -> crime_category mapping
    4. build_embedding_text()-> the actual string that gets embedded per case
    5. embed_and_index()     -> push into your vector DB with metadata for filtering

Install:
    pip install sentence-transformers qdrant-client --break-system-packages
    (swap sentence-transformers for InLegalBERT / your chosen embedder)
"""

from __future__ import annotations
import json
import glob
import hashlib
from pathlib import Path
from typing import List, Dict, Any
from datetime import date


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

RAW_CASES_DIR = "raw_cases"          # one .json file per case, matching the schema
YEAR_RANGE = (2023, 2025)            # 3-year window — filter anything outside this
TARGET_CATEGORIES = {
    "cyber_fraud",
    "crimes_against_women",
    "cheating_forgery",
    "theft_burglary",
    "crimes_against_senior_citizens",
}

# Rule-based fallback classifier: statute section -> crime_category.
# Fill this in as you encounter more sections in your real data — it's meant
# to catch cases where the collector didn't manually tag crime_category.
SECTION_TO_CATEGORY = {
    "318": "cheating_forgery",      # BNS Cheating
    "420": "cheating_forgery",      # IPC Cheating (pre-BNS)
    "66D": "cyber_fraud",           # IT Act - cheating by personation via computer
    "354": "crimes_against_women",  # IPC/BNS - assault on woman with intent to outrage modesty
    "379": "theft_burglary",        # IPC Theft
    "303": "theft_burglary",        # BNS Theft
    # TODO: extend this table as your dataset grows.
}


# ---------------------------------------------------------------------------
# Stage 1 — Load
# ---------------------------------------------------------------------------

def load_raw_cases(raw_dir: str = RAW_CASES_DIR) -> List[Dict[str, Any]]:
    cases = []
    for path in glob.glob(f"{raw_dir}/*.json"):
        with open(path, "r", encoding="utf-8") as f:
            try:
                cases.append(json.load(f))
            except json.JSONDecodeError:
                print(f"  [skip] malformed JSON: {path}")
    print(f"Loaded {len(cases)} raw case records from {raw_dir}/")
    return cases


# ---------------------------------------------------------------------------
# Stage 2 — Validate, dedupe, restrict to the 3-year district-court window
# ---------------------------------------------------------------------------

REQUIRED_FIELDS = ["case_id", "court_level", "year", "fact_summary", "statute_sections"]


def validate_and_clean(cases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen_ids = set()
    clean = []

    for c in cases:
        # required fields present
        if not all(c.get(f) for f in REQUIRED_FIELDS):
            continue
        # district courts only
        if c.get("court_level") != "district":
            continue
        # 3-year window only
        if not (YEAR_RANGE[0] <= c.get("year", 0) <= YEAR_RANGE[1]):
            continue
        # dedupe on case_id
        if c["case_id"] in seen_ids:
            continue
        seen_ids.add(c["case_id"])
        clean.append(c)

    print(f"Kept {len(clean)} / {len(cases)} records after validation "
          f"(district courts, {YEAR_RANGE[0]}-{YEAR_RANGE[1]}, deduped).")
    return clean


# ---------------------------------------------------------------------------
# Stage 3 — Classify crime_category where missing, using statute sections
# ---------------------------------------------------------------------------

def classify_if_missing(cases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    for c in cases:
        if c.get("crime_category"):
            continue
        sections = [s.get("section") for s in c.get("statute_sections", [])]
        for sec in sections:
            if sec in SECTION_TO_CATEGORY:
                c["crime_category"] = SECTION_TO_CATEGORY[sec]
                break
        else:
            c["crime_category"] = "uncategorized"  # review manually later

    # keep only the 5 shortlisted categories for this prototype dataset
    filtered = [c for c in cases if c["crime_category"] in TARGET_CATEGORIES]
    print(f"{len(filtered)} / {len(cases)} records fall in the 5 shortlisted crime categories.")
    return filtered


# ---------------------------------------------------------------------------
# Stage 4 — Build the embedding text (this is what similarity search runs on)
# ---------------------------------------------------------------------------

def build_embedding_text(case: Dict[str, Any]) -> str:
    """
    What gets embedded matters more than which embedding model you use.
    Combine: crime category + statute labels + fact summary + keywords,
    normalized to plain text — NOT the raw legalese judgment text, which
    is noisier and hurts similarity quality for a "does this match my
    situation" query written in plain language by a citizen.
    """
    statute_labels = ", ".join(
        f"{s.get('act', '')} {s.get('section', '')} ({s.get('label', '')})"
        for s in case.get("statute_sections", [])
    )
    keywords = ", ".join(case.get("keywords", []))
    parts = [
        f"Crime category: {case.get('crime_category', '')}.",
        f"Relevant sections: {statute_labels}.",
        f"Facts: {case.get('fact_summary', '')}.",
        f"Keywords: {keywords}.",
        f"Outcome: {case.get('outcome', {}).get('disposal_type', '')}.",
    ]
    return " ".join(p for p in parts if p.strip() != ".")


def attach_embedding_text(cases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    for c in cases:
        c["embedding_text"] = build_embedding_text(c)
    return cases


# ---------------------------------------------------------------------------
# Stage 5 — Embed + index (plug into your vector DB here)
# ---------------------------------------------------------------------------

def embed_and_index(cases: List[Dict[str, Any]]):
    """
    TODO: replace with your real embedder + vector DB.
    Example with sentence-transformers + Qdrant:

        from sentence_transformers import SentenceTransformer
        from qdrant_client import QdrantClient
        from qdrant_client.models import PointStruct, VectorParams, Distance

        model = SentenceTransformer("law-ai/InLegalBERT")  # or your chosen model
        client = QdrantClient(":memory:")  # swap for a real Qdrant instance

        client.recreate_collection(
            collection_name="district_court_cases",
            vectors_config=VectorParams(size=768, distance=Distance.COSINE),
        )

        points = []
        for i, c in enumerate(cases):
            vector = model.encode(c["embedding_text"]).tolist()
            points.append(PointStruct(
                id=i,
                vector=vector,
                payload={
                    "case_id": c["case_id"],
                    "crime_category": c["crime_category"],
                    "state": c["state"],
                    "year": c["year"],
                    "outcome": c["outcome"]["disposal_type"],
                    "fact_summary": c["fact_summary"],
                },
            ))
        client.upsert(collection_name="district_court_cases", points=points)

    This gives your retriever_agent (in pipeline.py) a collection it can query
    with BOTH a metadata filter (crime_category="cyber_fraud", year>=2023) AND
    a semantic-similarity search on embedding_text — exactly what "find cases
    that match this situation" needs.
    """
    print(f"[TODO] embed_and_index: {len(cases)} cases ready to push to your vector DB.")
    return cases


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

def build_dataset():
    cases = load_raw_cases()
    cases = validate_and_clean(cases)
    cases = classify_if_missing(cases)
    cases = attach_embedding_text(cases)
    embed_and_index(cases)

    Path("processed").mkdir(exist_ok=True)
    out_path = "processed/district_court_cases_2023_2025.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(cases, f, indent=2, ensure_ascii=False)
    print(f"Wrote {len(cases)} processed case records to {out_path}")

    # quick breakdown by category, useful to paste into your pitch deck
    counts = {}
    for c in cases:
        counts[c["crime_category"]] = counts.get(c["crime_category"], 0) + 1
    print("Category breakdown:", counts)


if __name__ == "__main__":
    build_dataset()
