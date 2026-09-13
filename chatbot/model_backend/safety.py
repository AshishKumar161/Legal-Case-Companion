"""
Safety & Escalation Guardrails Module for LCC AI/Model Backend.
Responsible for:
1. Detecting harmful or unlawful queries (e.g. how to evade police, destroy evidence, commit fraud).
2. Detecting emergency situations (active violence, ongoing arrest, suicide/harm threats).
3. Detecting high-risk scenarios requiring immediate advocate intervention.
4. Generating safe, canned legal disclaimer responses for unsafe or ungrounded queries.
"""

from __future__ import annotations
import re
import logging
from typing import Tuple, Optional

from .schemas import SafetyCheckResult, LegalAssistantResponse
from .prompts import LEGAL_DISCLAIMER, UNIVERSAL_CHATBOT_OPENING

logger = logging.getLogger("lcc.safety")

# Keywords indicating intent to commit offenses or evade enforcement
UNLAWFUL_INTENT_PATTERNS = [
    r"how to (hack|launder|counterfeit|forge|scam|steal|defraud|smuggle|embezzle|bribe)",
    r"how (can|do) i evade (police|arrest|customs|court|taxes|law)",
    r"how to (destroy|hide|tamper with) evidence",
    r"how to create fake (aadhaar|pan|passport|stamp paper|documents|currency|certificate)",
    r"bypass (kyc|bank security|anti-money laundering|firewall|otp)",
    r"threaten (a witness|the complainant|my spouse|the victim|the judge)",
    r"hire a hitman",
    r"buy (illegal drugs|weapons|guns) online",
]

# Keywords indicating immediate emergencies
EMERGENCY_PATTERNS = [
    r"(police are|cops are) (at my door|raiding|arresting me right now|outside)",
    r"(threatened to kill|physical violence|beating me|assaulting me right now|domestic violence right now)",
    r"(suicide|kill myself|end my life|dont want to live|jump off)",
    r"(kidnapped|abducted|held hostage|locked me in)",
    r"(bleeding|need an ambulance|heart attack)",
]

# High-risk legal situations demanding professional representation
HIGH_RISK_PATTERNS = [
    r"hearing tomorrow morning",
    r"bail hearing in \d+ hours",
    r"non-bailable warrant",
    r"NBW issued",
    r"charge sheet filed and need to cross-examine",
    r"anticipatory bail urgent",
    r"police calling me to station today",
    r"property auction tomorrow",
]


class SafetyGuard:
    """
    Safety guardrail evaluator.
    Evaluates queries before pipeline processing and controls escalation.
    """

    def check_query_safety(self, query: str) -> SafetyCheckResult:
        """
        Screen the user query for safety violations, emergencies, or high-risk conditions.
        """
        query_lower = query.lower()

        # 1. Check for emergencies
        for pat in EMERGENCY_PATTERNS:
            if re.search(pat, query_lower):
                logger.warning(f"Emergency pattern triggered: '{pat}'")
                return SafetyCheckResult(
                    is_safe=False,
                    is_emergency=True,
                    requires_immediate_advocate=True,
                    violation_category="emergency",
                    safety_message=(
                        "EMERGENCY ASSISTANCE REQUIRED: If you or someone else is in immediate physical danger, "
                        "under active threat, or in an ongoing police action, please immediately contact emergency services:\n"
                        "- Emergency Police Assistance: Dial 112 (or 100)\n"
                        "- Women's Helpline: Dial 1091 / 181\n"
                        "- Cyber Crime Immediate Helpline: Dial 1930\n"
                        "This AI system cannot provide real-time emergency or physical intervention."
                    ),
                )

        # 2. Check for unlawful intent / evasion
        for pat in UNLAWFUL_INTENT_PATTERNS:
            if re.search(pat, query_lower):
                logger.warning(f"Unlawful intent pattern triggered: '{pat}'")
                return SafetyCheckResult(
                    is_safe=False,
                    is_emergency=False,
                    requires_immediate_advocate=False,
                    violation_category="unlawful_intent",
                    safety_message=(
                        "SAFETY POLICY NOTICE: This assistant cannot provide guidance, assistance, or strategies "
                        "on committing crimes, evading law enforcement, falsifying documents, or destroying evidence. "
                        "All citizens are encouraged to act within the framework of the law."
                    ),
                )

        # 3. Check for high-risk legal deadlines requiring immediate advocate
        requires_advocate = False
        for pat in HIGH_RISK_PATTERNS:
            if re.search(pat, query_lower):
                requires_advocate = True
                break

        return SafetyCheckResult(
            is_safe=True,
            is_emergency=False,
            requires_immediate_advocate=requires_advocate,
            violation_category=None,
            safety_message=None,
        )

    def create_safety_fallback_response(
        self,
        safety_result: SafetyCheckResult,
    ) -> LegalAssistantResponse:
        """
        Generates a structured LegalAssistantResponse for unsafe or emergency queries.
        """
        msg = safety_result.safety_message or "Query could not be processed due to safety guidelines."
        return LegalAssistantResponse(
            answer=f"{msg}\n\n---\n{LEGAL_DISCLAIMER}",
            legal_issue=[],
            relevant_law=[],
            possible_next_steps=[
                "Dial 112 for immediate police assistance if under active threat.",
                "Dial 1930 for urgent cyber fraud financial freezes.",
                "Contact a practicing advocate for formal legal representation in active proceedings."
            ],
            documents_or_information=[],
            similar_cases=[],
            sources=[],
            confidence=0.0,
            verified=False,
            needs_professional_help=True,
            escalated=True,
            clarification_needed=False,
        )

    def create_insufficient_evidence_response(
        self,
        query: str,
        reason: str = "The available legal corpus does not contain enough verified evidence to answer reliably.",
    ) -> LegalAssistantResponse:
        """
        Returns a safe response when the corpus lacks verified evidence.
        Prevents hallucinating legal answers when retrieval fails.
        """
        msg = (
            f"Unable to provide a verified legal information response for your query.\n\n"
            f"**Reason**: {reason}\n\n"
            "To prevent the generation of unverified or inaccurate legal information, this system does not guess "
            "when verified statutory sections or case precedents are absent from its indexed corpus.\n\n"
            "**Recommended Action**: Please consult a qualified advocate or legal aid clinic to review the specifics "
            "of your situation.\n\n"
            f"---\n{LEGAL_DISCLAIMER}"
        )

        return LegalAssistantResponse(
            answer=msg,
            legal_issue=["Unverified / Insufficient Evidence"],
            relevant_law=[],
            possible_next_steps=[
                "Consult a licensed advocate specializing in the relevant jurisdiction.",
                "Visit your local District Legal Services Authority (DLSA) for free legal consultation if eligible.",
                "Gather all primary documents, agreements, and notices for in-person review."
            ],
            documents_or_information=[
                "Relevant contracts, legal notices, or correspondence received",
                "Personal identification and timeline of events"
            ],
            similar_cases=[],
            sources=[],
            confidence=0.25,
            verified=False,
            needs_professional_help=True,
            escalated=True,
            clarification_needed=False,
        )

    def is_greeting_only(self, query: str) -> bool:
        """
        Check if the query is only a greeting with no legal content.
        """
        import string
        cleaned = query.lower().translate(str.maketrans('', '', string.punctuation)).strip()
        greetings = {"hi", "hello", "hey", "hii", "heyy", "hlo", "good morning", "good afternoon", "good evening", "namaste", "hii there", "hey there"}
        
        if cleaned in greetings:
            return True
            
        words = cleaned.split()
        if 0 < len(words) < 4:
            single_word_greetings = {"hi", "hello", "hey", "hii", "heyy", "hlo", "namaste"}
            if all(w in single_word_greetings for w in words):
                return True
                
        return False

    def create_greeting_response(self) -> LegalAssistantResponse:
        """
        Returns a short, warm reply for greetings.
        """
        return LegalAssistantResponse(
            answer=UNIVERSAL_CHATBOT_OPENING,
            legal_issue=[],
            relevant_law=[],
            possible_next_steps=[],
            documents_or_information=[],
            similar_cases=[],
            sources=[],
            confidence=1.0,
            verified=True,
            needs_professional_help=False,
            escalated=False,
            clarification_needed=False,
        )
