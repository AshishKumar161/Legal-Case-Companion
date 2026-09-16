"""
Intake Module for LCC AI/Model Backend.
Responsible for:
1. Analyzing the raw citizen/lawyer query and multi-turn conversation history.
2. Extracting clear, structured facts (timeline, medium, amounts, actors).
3. Detecting missing critical information (e.g. golden-hour 1930 reporting, bank transaction IDs, FIR status).
4. Generating concise clarification questions when vital facts are missing.
"""

from __future__ import annotations
import json
import re
import logging
from typing import List, Dict, Any, Optional

from .schemas import IntakeResult, ConversationTurn
from .llama_model import LLaMAModel
from .prompts import INTAKE_SYSTEM_PROMPT

logger = logging.getLogger("lcc.intake")


class IntakeAgent:
    """
    Intake Agent converts conversational queries into clear, grounded fact representations.
    Supports multi-turn dialog context passed from the caller.
    """

    def __init__(self, llama_model: LLaMAModel):
        self.llm = llama_model

    def process(
        self,
        query: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> IntakeResult:
        """
        Processes a query in the context of optional prior conversation history.
        """
        # Format history if present
        context_block = ""
        if conversation_history:
            history_lines = []
            for turn in conversation_history:
                role = turn.get("role", "user").capitalize()
                content = turn.get("content", "")
                history_lines.append(f"{role}: {content}")
            context_block = "PRIOR CONVERSATION HISTORY:\n" + "\n".join(history_lines) + "\n\n"

        prompt = f"""{context_block}CURRENT USER QUERY:
"{query}"

Analyze the situation and return a JSON object strictly conforming to this format:
{{
  "clarified_facts": "A clear, neutral 2-4 sentence summary of the concrete facts described.",
  "extracted_entities": {{
    "incident_type": "brief label e.g. impersonation phone fraud / physical theft",
    "financial_loss": "amount mentioned or 'unknown/none'",
    "contact_medium": "phone / upi / whatsapp / in-person / online",
    "timeline": "e.g. today / recently / date if mentioned",
    "parties_involved": "who contacted whom and under what pretense"
  }},
  "detected_category": "criminal | civil | family_matrimonial | property_land | consumer | cheque_bounce | labour_employment | cybercrime | motor_accident | constitutional_administrative | other",
  "missing_information": [
    "List 1-3 crucial factual details that are not yet known (e.g. whether money was already sent, whether an FIR was registered)"
  ],
  "clarification_questions": [
    "1-2 concise, polite clarification questions if essential information is missing, else empty"
  ],
  "needs_clarification": false,
  "is_conversational": "boolean, true if the query is a simple greeting, general chat, or a question about your capabilities (e.g., 'who are you?', 'can you remember things?') NOT requiring legal analysis. False if it describes a situation or asks for legal help."
}}
"""

        raw_output = self.llm.generate(
            prompt=prompt,
            system_prompt=INTAKE_SYSTEM_PROMPT,
            temperature=0.1,
            json_mode=True,
        )

        try:
            # Parse JSON response
            cleaned = self._clean_json(raw_output)
            data = json.loads(cleaned)
            return IntakeResult(
                raw_query=query,
                clarified_facts=data.get("clarified_facts", query),
                extracted_entities=data.get("extracted_entities", {}),
                detected_category=data.get("detected_category", "uncategorized"),
                missing_information=data.get("missing_information", []),
                clarification_questions=data.get("clarification_questions", []),
                needs_clarification=bool(data.get("needs_clarification", False)),
                is_conversational=bool(data.get("is_conversational", False)),
            )
        except Exception as e:
            logger.warning(f"Could not parse Intake JSON output ({e}). Falling back to heuristic extraction.")
            return self._heuristic_fallback(query, conversation_history)

    def _clean_json(self, text: str) -> str:
        """Strip markdown json code blocks if present."""
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        return text

    def _heuristic_fallback(
        self,
        query: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> IntakeResult:
        """Rule-based fallback when LLM output is not valid JSON."""
        query_lower = query.lower()

        def _matches(keywords: List[str]) -> bool:
            for kw in keywords:
                if " " in kw or "-" in kw:
                    if kw in query_lower:
                        return True
                else:
                    if re.search(rf"\b{re.escape(kw)}\b", query_lower):
                        return True
            return False

        category = "other"
        if _matches([
            "digital arrest", "customs officer", "upi fraud", "online fraud", "hacked account",
            "cyberstalking", "identity theft", "otp", "phishing", "hacked", "hacking", "malware",
            "scam", "scammed", "fraudulent", "cybercrime", "sim", "kyc", "spoofed", "spoofing",
            "unauthorized transaction", "bank account", "unauthorized debit", "money deducted",
            "netbanking", "66d", "credit card fraud", "debit card fraud"
        ]):
            category = "cyber_fraud"
        elif _matches([
            "fake appointment", "job fraud", "forged document", "fake agreement", "cheated",
            "forgery", "counterfeit", "impersonation", "duped", "swindled", "cheating", "forged",
            "420 ipc", "420"
        ]):
            category = "cheating_forgery"
        elif _matches([
            "stolen vehicle", "bike theft", "car theft", "burglary", "theft", "stolen",
            "robbery", "pickpocket", "snatched", "looted", "robbed", "stole", "steal",
            "379 ipc", "379"
        ]):
            category = "theft_burglary"
        elif _matches([
            "domestic violence", "beating", "outraging modesty", "assault", "abused", "abuse",
            "cruelty", "cruel", "dowry", "molested", "stalking", "harassed", "threatened", "threats",
            "498a", "498-a"
        ]):
            category = "crimes_against_women"
        elif _matches([
            "divorce", "maintenance", "mutual consent", "separation", "alimony", "custody",
            "annulment", "desertion", "estranged", "estrangement", "remarriage", "infidelity"
        ]):
            category = "matrimonial_disputes"
        elif _matches([
            "senior citizen", "senior citizens act", "parents maintenance", "eviction of son", "gift deed", "elder abuse",
            "elder neglect", "section 23", "elderly", "neglect", "neglected", "abandoned", "abandonment", "pension"
        ]):
            category = "crimes_against_senior_citizens"
        elif _matches(["land", "ownership", "possession", "inheritance", "partition", "encroachment", "registry"]):
            category = "property_land"
        elif _matches(["defective product", "refund", "warranty", "online shopping", "poor service", "consumer"]):
            category = "consumer"
        elif _matches(["cheque bounce", "dishonoured cheque", "bounced cheque", "section 138"]):
            category = "cheque_bounce"
        elif _matches(["salary", "termination", "gratuity", "harassment", "pf", "employee", "labour"]):
            category = "labour_employment"
        elif _matches(["accident", "crash", "hit and run", "injury compensation", "insurance", "mact", "vehicle accident"]):
            category = "motor_accident"
        elif _matches(["fundamental rights", "government order", "writ", "public authority", "administrative decision", "constitution"]):
            category = "constitutional_administrative"
        elif _matches(["agreement", "recovery", "damages", "breach", "civil", "legal notice"]):
            category = "civil"
        elif _matches(["murder", "fir", "arrest"]):
            category = "criminal"

        missing = []
        questions = []
        if "transfer" in query_lower and not any(char.isdigit() for char in query):
            missing.append("Specific amount transferred or transaction reference numbers")
            questions.append("Could you specify the approximate amount transferred and via which payment method (e.g. UPI, bank transfer)?")

        is_conv = False
        conv_triggers = ["hi", "hello", "hey", "how are you", "good morning", "good evening", "greetings", "who are you", "what can you do", "remember", "help", "thanks", "thank you", "ok", "okay"]
        if any(trigger in query_lower.strip() for trigger in conv_triggers) and len(query.split()) < 15:
            is_conv = True

        return IntakeResult(
            raw_query=query,
            clarified_facts=query.strip(),
            extracted_entities={"channel": "digital/phone" if "call" in query_lower else "general"},
            detected_category=category,
            missing_information=missing,
            clarification_questions=questions,
            needs_clarification=len(questions) > 0 and len(query.split()) < 8,
            is_conversational=is_conv,
        )
