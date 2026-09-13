"""
Legal Reasoner Module for LCC AI/Model Backend.
Responsible for:
1. Identifying POTENTIAL legal categories and legal issues.
2. Generating high-precision search queries for retrieval against statute and case repositories.
3. Enforcing strictly cautious, non-definitive phrasing ("possible issue", "potentially relevant law").
4. Preventing definitive, ungrounded legal diagnoses.
"""

from __future__ import annotations
import json
import logging
from typing import List, Dict, Any

from .schemas import IntakeResult, LegalIssue, LegalReasoningResult
from .llama_model import LLaMAModel
from .prompts import LEGAL_REASONER_PROMPT

logger = logging.getLogger("lcc.legal_reasoner")


class LegalReasoner:
    """
    Identifies potential legal issues and formulates search terms.
    Adheres strictly to Indian criminal law categories and non-definitive wording.
    """

    def __init__(self, llama_model: LLaMAModel):
        self.llm = llama_model

    def analyze(self, intake_result: IntakeResult) -> LegalReasoningResult:
        """
        Takes intake facts and formulates legal issues and search queries.
        """
        prompt = f"""FACT PATTERN REPORTED:
"{intake_result.clarified_facts}"

Detected category: {intake_result.detected_category}
Key entities: {intake_result.extracted_entities}

Analyze this situation and return a JSON object adhering to this schema:
{{
  "possible_issues": [
    {{
      "title": "Short title with cautious phrasing (e.g. Possible Cheating by Personation)",
      "possible_category": "cyber_fraud | crimes_against_women | matrimonial_disputes | cheating_forgery | theft_burglary | crimes_against_senior_citizens | other",
      "description": "Explanation using strictly non-definitive language ('A possible issue that arises...', 'Potentially relevant considerations include...')",
      "potentially_relevant_law": [
        "Potentially applicable section and Act (e.g. Section 66D IT Act, Section 318 BNS)"
      ],
      "search_keywords": [
        "targeted search keywords"
      ]
    }}
  ],
  "search_queries": [
    "2-3 high precision search queries to retrieve both statutes and district court precedents"
  ],
  "reasoning_summary": "Brief neutral summary of the preliminary reasoning."
}}
"""

        raw_output = self.llm.generate(
            prompt=prompt,
            system_prompt=LEGAL_REASONER_PROMPT,
            temperature=0.1,
            json_mode=True,
        )

        try:
            cleaned = self._clean_json(raw_output)
            data = json.loads(cleaned)

            issues = []
            for item in data.get("possible_issues", []):
                # Enforce cautious wording on title and description
                title = item.get("title", "Possible Legal Issue")
                if not any(w in title.lower() for w in ["possible", "potential", "alleged", "suspected", "matter of"]):
                    title = f"Possible {title}"

                issues.append(LegalIssue(
                    title=title,
                    possible_category=item.get("possible_category", intake_result.detected_category),
                    description=item.get("description", ""),
                    potentially_relevant_law=item.get("potentially_relevant_law", []),
                    search_keywords=item.get("search_keywords", []),
                ))

            search_queries = data.get("search_queries", [])
            if not search_queries:
                search_queries = [intake_result.clarified_facts]

            return LegalReasoningResult(
                possible_issues=issues,
                search_queries=search_queries,
                reasoning_summary=data.get("reasoning_summary", "Preliminary assessment completed."),
            )

        except Exception as e:
            logger.warning(f"Could not parse Legal Reasoner output ({e}). Using rule-based fallback.")
            return self._heuristic_fallback(intake_result)

    def _clean_json(self, text: str) -> str:
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        return text

    def _heuristic_fallback(self, intake_result: IntakeResult) -> LegalReasoningResult:
        """Rule-based fallback for legal issues and search queries."""
        category = intake_result.detected_category
        facts = intake_result.clarified_facts.lower()

        issues = []
        queries = []

        if category == "cyber_fraud" or "customs" in facts or "upi" in facts:
            issues.append(LegalIssue(
                title="Possible Cheating by Personation using Computer Resource",
                possible_category="cyber_fraud",
                description=(
                    "The described facts suggest potential impersonation of authority figures to induce money transfers, "
                    "a situation commonly analyzed under legal provisions governing cheating by personation."
                ),
                potentially_relevant_law=[
                    "Section 66D Information Technology Act, 2000",
                    "Section 318 Bharatiya Nyaya Sanhita (BNS) / Section 420 IPC"
                ],
                search_keywords=["impersonation", "customs", "Section 66D", "UPI fraud", "cheating"],
            ))
            queries.extend([
                "customs impersonation digital arrest UPI money transfer Section 66D IT Act",
                "cheating personation computer resource Section 318 BNS 420 IPC"
            ])
        elif category == "theft_burglary":
            issues.append(LegalIssue(
                title="Possible Theft of Property",
                possible_category="theft_burglary",
                description=(
                    "The unauthorized taking of movable property may potentially fall under statutory provisions for theft."
                ),
                potentially_relevant_law=["Section 303 BNS / Section 379 IPC"],
                search_keywords=["theft", "stolen", "vehicle", "Section 379 IPC", "Section 303 BNS"],
            ))
            queries.append("theft of movable property vehicle recovery Section 303 BNS 379 IPC")
        elif category == "crimes_against_women":
            issues.append(LegalIssue(
                title="Possible Cruelty or Domestic Abuse Against Woman",
                possible_category="crimes_against_women",
                description=(
                    "The circumstances described may potentially involve allegations of matrimonial cruelty, "
                    "harassment, or domestic violence requiring legal examination under statutory protection frameworks."
                ),
                potentially_relevant_law=[
                    "Section 498A Indian Penal Code (IPC) / Section 85 BNS",
                    "Section 3 Protection of Women from Domestic Violence Act, 2005"
                ],
                search_keywords=["498A", "cruelty", "domestic violence", "protection order", "dowry harassment"],
            ))
            queries.extend([
                "husband in-laws cruelty harassment dowry Section 498A IPC BNS 85",
                "domestic violence protection order maintenance Section 3 DV Act 2005"
            ])
        elif category == "matrimonial_disputes":
            issues.append(LegalIssue(
                title="Possible Matrimonial Dispute, Maintenance, or Mutual Separation",
                possible_category="matrimonial_disputes",
                description=(
                    "The facts indicate potential matrimonial dissolution, maintenance claims, or mutual consent separation "
                    "which may be governed by personal marriage laws and statutory maintenance provisions."
                ),
                potentially_relevant_law=[
                    "Section 125 Code of Criminal Procedure (CrPC) / Section 144 BNSS",
                    "Section 13B Hindu Marriage Act, 1955"
                ],
                search_keywords=["mutual consent divorce", "Section 13B", "maintenance", "Section 125 CrPC", "alimony"],
            ))
            queries.extend([
                "mutual consent divorce dissolution of marriage separation Section 13B Hindu Marriage Act",
                "maintenance interim maintenance wife support Section 125 CrPC Section 144 BNSS"
            ])
        elif category == "cheating_forgery":
            issues.append(LegalIssue(
                title="Possible Cheating and Dishonest Inducement of Property",
                possible_category="cheating_forgery",
                description=(
                    "The allegations suggest potential deception or dishonest inducement to deliver property or money, "
                    "which may fall under criminal statutes governing cheating and forgery."
                ),
                potentially_relevant_law=[
                    "Section 318 Bharatiya Nyaya Sanhita (BNS) / Section 420 IPC"
                ],
                search_keywords=["cheating", "fraudulent inducement", "Section 318 BNS", "Section 420 IPC", "forgery"],
            ))
            queries.extend([
                "cheating fraudulent inducement delivery of property Section 318 BNS 420 IPC",
                "forgery forged document fake agreement job fraud Section 468 IPC"
            ])
        elif category == "crimes_against_senior_citizens":
            issues.append(LegalIssue(
                title="Possible Neglect or Property Deprivation of Senior Citizen",
                possible_category="crimes_against_senior_citizens",
                description=(
                    "The described circumstances suggest possible abandonment, neglect, or deprivation of property rights "
                    "affecting an elderly person, which may warrant remedy under welfare and maintenance legislation."
                ),
                potentially_relevant_law=[
                    "Section 23 Maintenance and Welfare of Parents and Senior Citizens Act, 2007"
                ],
                search_keywords=["senior citizens act", "maintenance tribunal", "gift deed void", "elder neglect"],
            ))
            queries.append("senior citizen maintenance tribunal gift deed void property transfer Section 23 Act 2007")
        else:
            issues.append(LegalIssue(
                title="Possible Legal Offence Under Review",
                possible_category=category,
                description="The reported circumstances indicate possible legal concerns requiring formal review.",
                potentially_relevant_law=[],
                search_keywords=[category],
            ))
            queries.append(intake_result.clarified_facts)

        return LegalReasoningResult(
            possible_issues=issues,
            search_queries=queries,
            reasoning_summary="Rule-based legal reasoning fallback applied.",
        )
