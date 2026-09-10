import re
from dataclasses import dataclass, field


@dataclass
class StructuredLegalQuery:
    original_question: str
    normalized_question: str
    retrieval_query: str
    detected_entities: dict[str, list[str]] = field(default_factory=dict)
    query_intent: str = "FACTUAL_LOOKUP"


class QueryUnderstandingService:
    """Deterministic Query Understanding service for legal questions."""

    @staticmethod
    def analyze_query(question: str) -> StructuredLegalQuery:
        cleaned = question.strip()
        normalized = " ".join(cleaned.split())

        detected_entities: dict[str, list[str]] = {
            "sections": [],
            "orders": [],
            "firs": [],
            "dates": [],
            "amounts": [],
        }

        # 1. Detect Sections / Acts
        section_matches = re.findall(r"\bsection\s+(\d+[a-z]?(?:\s*\([0-9a-z]+\))*)", normalized, re.IGNORECASE)
        if section_matches:
            detected_entities["sections"] = list(set(section_matches))

        # 2. Detect Orders & Rules
        order_matches = re.findall(r"\border\s+([ivxlcdm\d]+)(?:\s+rule\s+(\d+))?", normalized, re.IGNORECASE)
        if order_matches:
            detected_entities["orders"] = [f"Order {m[0]} Rule {m[1]}".strip() if m[1] else f"Order {m[0]}" for m in order_matches]

        # 3. Detect FIR numbers
        fir_matches = re.findall(r"\bfir\s*(?:no\.?|number)?\s*[:\s]*(\d+[/-]\d{2,4})", normalized, re.IGNORECASE)
        if fir_matches:
            detected_entities["firs"] = list(set(fir_matches))

        # 4. Detect Dates
        date_matches = re.findall(r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}(?:st|nd|rd|th)?\s+[a-zA-Z]+\s+\d{4})\b", normalized, re.IGNORECASE)
        if date_matches:
            detected_entities["dates"] = list(set(date_matches))

        # 5. Detect Amounts
        amount_matches = re.findall(r"\b(?:rs\.?|inr|rupees)\s*([\d,]+(?:\.\d+)?)\b", normalized, re.IGNORECASE)
        if amount_matches:
            detected_entities["amounts"] = list(set(amount_matches))

        # 6. Intent classification
        intent = "FACTUAL_LOOKUP"
        q_lower = normalized.lower()
        if any(w in q_lower for w in ["compare", "difference", "versus", "vs", "contradict", "conflict"]):
            intent = "COMPARISON_OR_CONFLICT"
        elif any(w in q_lower for w in ["timeline", "chronology", "sequence", "when did", "dates"]):
            intent = "TIMELINE_ANALYSIS"
        elif any(w in q_lower for w in ["clause", "termination", "breach", "obligation", "liability"]):
            intent = "CONTRACT_ANALYSIS"

        # 7. Formulate optimized retrieval query
        # Boost specific legal keywords if detected
        boosted_terms = []
        for cat, items in detected_entities.items():
            for it in items:
                boosted_terms.append(f"{cat}:{it}")

        retrieval_query = normalized
        return StructuredLegalQuery(
            original_question=cleaned,
            normalized_question=normalized,
            retrieval_query=retrieval_query,
            detected_entities=detected_entities,
            query_intent=intent,
        )
