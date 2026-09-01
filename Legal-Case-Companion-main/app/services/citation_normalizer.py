import re
from dataclasses import dataclass, field
from typing import ClassVar


@dataclass
class NormalizedLegalCitation:
    raw_reference: str
    normalized_citation: str
    citation_type: str  # STATUTE_PROVISION, JUDICIAL_CITATION, CONSTITUTIONAL_ARTICLE, RULE_ORDER
    act_or_court: str | None = None
    section_or_article: str | None = None
    year: int | None = None
    volume_or_number: str | None = None
    search_tokens: list[str] = field(default_factory=list)


class LegalCitationNormalizer:
    """Normalizes Indian legal citations, statutory provisions, and court references."""

    # Map popular short acronyms to formal canonical Act names
    ACT_ALIASES: ClassVar[dict[str, str]] = {
        "ni act": "Negotiable Instruments Act 1881",
        "n.i. act": "Negotiable Instruments Act 1881",
        "ipc": "Indian Penal Code 1860",
        "i.p.c.": "Indian Penal Code 1860",
        "crpc": "Code of Criminal Procedure 1973",
        "cr.p.c.": "Code of Criminal Procedure 1973",
        "cpc": "Code of Civil Procedure 1908",
        "c.p.c.": "Code of Civil Procedure 1908",
        "ica": "Indian Contract Act 1872",
        "contract act": "Indian Contract Act 1872",
        "arbitration act": "Arbitration and Conciliation Act 1996",
        "companies act": "Companies Act 2013",
        "it act": "Information Technology Act 2000",
        "gst act": "Central Goods and Services Tax Act 2017",
        "cgst act": "Central Goods and Services Tax Act 2017",
        "constitution": "Constitution of India 1950",
    }

    @classmethod
    def normalize_citation(cls, raw: str) -> NormalizedLegalCitation | None:
        if not raw or not raw.strip():
            return None

        cleaned = " ".join(raw.strip().split())
        cleaned_lower = cleaned.lower()

        # 1. Check Constitutional Articles (e.g., Article 21, Art. 226)
        art_match = re.search(r"\b(?:article|art\.?)\s*(\d+[a-z]?(?:\s*\([0-9a-z]+\))*)", cleaned, re.IGNORECASE)
        if art_match:
            art_num = art_match.group(1).upper()
            return NormalizedLegalCitation(
                raw_reference=cleaned,
                normalized_citation=f"Article {art_num}, Constitution of India",
                citation_type="CONSTITUTIONAL_ARTICLE",
                act_or_court="Constitution of India",
                section_or_article=f"Article {art_num}",
                year=1950,
                search_tokens=[f"article {art_num.lower()}", "constitution of india", "article 21", "article 226"],
            )

        # 2. Check Orders & Rules of CPC (e.g., Order 39 Rule 1, Order XXXIX Rule 2)
        order_match = re.search(r"\border\s*([ivxlcdm\d]+)(?:\s*(?:rule|r\.?)\s*(\d+))?", cleaned, re.IGNORECASE)
        if order_match:
            order_num = order_match.group(1).upper()
            rule_num = order_match.group(2)
            norm_text = f"Order {order_num} Rule {rule_num}, Code of Civil Procedure 1908" if rule_num else f"Order {order_num}, Code of Civil Procedure 1908"
            return NormalizedLegalCitation(
                raw_reference=cleaned,
                normalized_citation=norm_text,
                citation_type="RULE_ORDER",
                act_or_court="Code of Civil Procedure 1908",
                section_or_article=f"Order {order_num} Rule {rule_num}" if rule_num else f"Order {order_num}",
                year=1908,
                search_tokens=[f"order {order_num.lower()}", f"order {order_num.lower()} rule {rule_num}" if rule_num else "", "code of civil procedure"],
            )

        # 3. Check Statutory Sections (e.g., Section 138 of NI Act, Sec 420 IPC, Section 9 Arbitration Act)
        sec_match = re.search(r"\b(?:section|sec\.?|s\.)\s*(\d+[a-z]?(?:\s*\([0-9a-z]+\))*)", cleaned, re.IGNORECASE)
        if sec_match:
            sec_num = sec_match.group(1).upper()

            # Identify Act context
            act_identified = None
            for alias, canonical_act in cls.ACT_ALIASES.items():
                if alias in cleaned_lower:
                    act_identified = canonical_act
                    break

            norm_text = f"Section {sec_num}" + (f", {act_identified}" if act_identified else "")
            tokens = [f"section {sec_num.lower()}", f"sec {sec_num.lower()}"]
            if act_identified:
                tokens.append(act_identified.lower())
                tokens.append(f"section {sec_num.lower()} {act_identified.lower()}")

            return NormalizedLegalCitation(
                raw_reference=cleaned,
                normalized_citation=norm_text,
                citation_type="STATUTE_PROVISION",
                act_or_court=act_identified,
                section_or_article=f"Section {sec_num}",
                search_tokens=tokens,
            )

        # 4. Check Law Reports Citations (e.g., (2021) 5 SCC 120, AIR 2020 SC 1400, 2024 INSC 510)
        scc_match = re.search(r"\(?(\d{4})\)?\s*(\d+)?\s*(scc|air|insc|scale)\s*(\d+)", cleaned, re.IGNORECASE)
        if scc_match:
            year = int(scc_match.group(1))
            vol = scc_match.group(2) or ""
            reporter = scc_match.group(3).upper()
            page = scc_match.group(4)
            norm_text = f"({year}) {vol} {reporter} {page}".replace("  ", " ").strip()
            return NormalizedLegalCitation(
                raw_reference=cleaned,
                normalized_citation=norm_text,
                citation_type="JUDICIAL_CITATION",
                act_or_court="Supreme Court of India",
                year=year,
                volume_or_number=f"{reporter} {page}",
                search_tokens=[norm_text.lower(), f"{reporter.lower()} {page}", str(year)],
            )

        return None

    @classmethod
    def extract_all_citations(cls, text: str) -> list[NormalizedLegalCitation]:
        """Extracts and normalizes all recognized legal references from a block of text."""
        citations: list[NormalizedLegalCitation] = []
        if not text:
            return citations

        # Split into clauses/sentences to detect individual references
        patterns = [
            r"\b(?:section|sec\.?|s\.)\s*\d+[a-z]?(?:\s*\([0-9a-z]+\))?(?:\s+(?:of|under)\s+(?:the\s+)?[a-zA-Z\s\.\(\)]+)?",
            r"\b(?:article|art\.?)\s*\d+[a-z]?(?:\s*\([0-9a-z]+\))?",
            r"\border\s*[ivxlcdm\d]+(?:\s*(?:rule|r\.?)\s*\d+)?",
            r"\(?\d{4}\)?\s*\d*\s*(?:scc|air|insc|scale)\s*\d+",
        ]

        seen = set()
        for pat in patterns:
            matches = re.finditer(pat, text, re.IGNORECASE)
            for m in matches:
                matched_str = m.group(0).strip()
                if matched_str.lower() not in seen:
                    seen.add(matched_str.lower())
                    norm = cls.normalize_citation(matched_str)
                    if norm:
                        citations.append(norm)

        return citations
