"""
Data schemas for the LCC AI/Model Backend.
Defines clean Pydantic models for every stage of the agentic pipeline:
intake, legal reasoning, retrieval, reranking, answer generation,
verification, and final structured response.
"""

from __future__ import annotations
from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Crime Categories & Classification
# ---------------------------------------------------------------------------

class LegalCategory(str, Enum):
    """The 10 legal domains based on the preliminary guide."""
    CRIMINAL = "criminal"
    CIVIL = "civil"
    FAMILY_MATRIMONIAL = "family_matrimonial"
    PROPERTY_LAND = "property_land"
    CONSUMER = "consumer"
    CHEQUE_BOUNCE = "cheque_bounce"
    LABOUR_EMPLOYMENT = "labour_employment"
    CYBERCRIME = "cybercrime"
    MOTOR_ACCIDENT = "motor_accident"
    CONSTITUTIONAL_ADMINISTRATIVE = "constitutional_administrative"
    OTHER = "other"
    UNCATEGORIZED = "uncategorized"


class DisposalType(str, Enum):
    CONVICTED = "convicted"
    ACQUITTED = "acquitted"
    SETTLED = "settled"
    WITHDRAWN = "withdrawn"
    PENDING = "pending"
    OTHER = "other"


# ---------------------------------------------------------------------------
# Case & Statute Raw Data Structures
# ---------------------------------------------------------------------------

class StatuteSection(BaseModel):
    act: str = Field(..., description="Act name e.g. BNS, IPC, IT Act")
    section: str = Field(..., description="Section number e.g. 318, 66D, 420")
    label: str = Field(..., description="Plain-language description of section")


class PriorRegimeSection(BaseModel):
    act: str = Field("IPC", description="Prior regime act name")
    section: str = Field(..., description="Pre-BNS equivalent section")
    note: Optional[str] = Field(None, description="Context note on transition")


class CaseOutcome(BaseModel):
    disposal_type: str = Field(..., description="convicted, acquitted, settled, etc.")
    sentence_or_relief: str = Field(..., description="Sentence or relief granted")


class CaseSource(BaseModel):
    portal: str = Field("manual_entry", description="Source portal or method")
    source_url: Optional[str] = Field(None, description="URL if available")
    retrieved_on: Optional[str] = Field(None, description="Date retrieved")


class LegalCaseRecord(BaseModel):
    """Schema matching case_schema_example.json for District Court cases."""
    case_id: str
    court_name: str
    state: str
    district: str
    court_level: str = "district"
    filing_date: Optional[str] = None
    judgment_date: Optional[str] = None
    year: int
    case_type: str = "criminal"
    crime_category: str  # Note: Can be changed to legal_category, keeping crime_category for backwards DB compatibility if needed
    statute_sections: List[StatuteSection] = Field(default_factory=list)
    prior_regime_sections: List[PriorRegimeSection] = Field(default_factory=list)
    fact_summary: str
    outcome: CaseOutcome
    keywords: List[str] = Field(default_factory=list)
    source: Optional[CaseSource] = None
    embedding_text: Optional[str] = None
    full_text_available: bool = False
    full_text_local_path: Optional[str] = None


class StatuteRecord(BaseModel):
    """Schema for statutory knowledge chunks (e.g. BNS, IPC, IT Act)."""
    statute_id: str
    act: str
    section: str
    title: str
    text: str
    explanation: str
    keywords: List[str] = Field(default_factory=list)
    crime_category: str  # Note: Can be changed to legal_category, keeping crime_category for backwards DB compatibility if needed
    embedding_text: Optional[str] = None


# ---------------------------------------------------------------------------
# Pipeline Stage Schemas
# ---------------------------------------------------------------------------

class ConversationTurn(BaseModel):
    role: str = Field(..., description="'user' or 'assistant'")
    content: str


class IntakeResult(BaseModel):
    """Output of the Intake Agent stage."""
    raw_query: str
    clarified_facts: str
    extracted_entities: Dict[str, Any] = Field(
        default_factory=dict,
        description="Key entities like financial_loss, contact_method, timeline, accused_info"
    )
    detected_category: str = Field(
        default="uncategorized",
        description="Preliminary topic detected"
    )
    missing_information: List[str] = Field(
        default_factory=list,
        description="Crucial details not yet mentioned by user"
    )
    clarification_questions: List[str] = Field(
        default_factory=list,
        description="Concise questions if essential details are absent"
    )
    needs_clarification: bool = False
    is_conversational: bool = Field(
        default=False,
        description="True if the query is a simple greeting or general chat not requiring legal analysis"
    )


class LegalIssue(BaseModel):
    """Output of the Legal Reasoner stage for a single identified issue."""
    title: str = Field(..., description="e.g. Possible Cheating by Personation")
    possible_category: str
    description: str = Field(..., description="Neutral explanation using non-definitive phrasing")
    potentially_relevant_law: List[str] = Field(default_factory=list)
    search_keywords: List[str] = Field(default_factory=list)


class LegalReasoningResult(BaseModel):
    """Aggregate result from the Legal Reasoner."""
    possible_issues: List[LegalIssue] = Field(default_factory=list)
    search_queries: List[str] = Field(default_factory=list)
    reasoning_summary: str


class RetrievedSource(BaseModel):
    """Uniform representation of an evidence chunk retrieved from the vector store."""
    source_id: str = Field(..., description="Unique ID e.g. case:DC-HP-2024-000123 or stat:IT-66D")
    source_type: str = Field(..., description="'case' or 'statute'")
    title: str = Field(..., description="Descriptive title")
    citation: str = Field(..., description="Formal legal citation or case title")
    text: str = Field(..., description="Evidentiary text or summary")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    relevance_score: float = Field(0.0, description="Dense/sparse retrieval score")


class RerankedCandidate(BaseModel):
    """A retrieved source after cross-encoder / relevance rescoring."""
    source: RetrievedSource
    rerank_score: float = Field(..., description="Cross-encoder relevance score (0.0 to 1.0)")
    ranking: int


class GeneratedAnswer(BaseModel):
    """Output of the LLaMA answer generator before independent verification."""
    plain_summary: str
    legal_issue_explanations: List[str] = Field(default_factory=list)
    relevant_laws_identified: List[str] = Field(default_factory=list)
    possible_next_steps: List[str] = Field(default_factory=list)
    documents_or_information: List[str] = Field(default_factory=list)
    similar_cases_mentioned: List[Dict[str, Any]] = Field(default_factory=list)
    raw_answer_text: str
    cited_source_ids: List[str] = Field(default_factory=list)


class VerificationResult(BaseModel):
    """Independent evaluation produced by the Critic / Verifier agent."""
    verified: bool = Field(..., description="True if claims are adequately grounded")
    grounding_score: float = Field(..., description="0.0 - 1.0 based on evidence support")
    citation_validity_score: float = Field(..., description="Ratio of citations existing in reranked set")
    verified_claims: List[str] = Field(default_factory=list)
    unsupported_claims: List[str] = Field(default_factory=list)
    hallucination_detected: bool = False
    verification_notes: str


class SafetyCheckResult(BaseModel):
    """Output of safety analysis."""
    is_safe: bool = True
    is_emergency: bool = False
    requires_immediate_advocate: bool = False
    violation_category: Optional[str] = None
    safety_message: Optional[str] = None


# ---------------------------------------------------------------------------
# Final Structured Response
# ---------------------------------------------------------------------------

class SimilarCaseInfo(BaseModel):
    case_id: str
    court_name: str
    year: int
    crime_category: str
    fact_similarity: str
    disposal_type: str
    sentence_or_relief: Optional[str] = None
    outcome_disclaimer: str = (
        "Note: Past court outcomes reflect specific evidentiary records and judicial "
        "findings; they do not guarantee or predict identical results for other disputes."
    )


class LegalAssistantResponse(BaseModel):
    """
    The final structured response delivered by LegalAssistant.ask().
    Matches the exact schema required:
    {
      "answer": "...",
      "legal_issue": [],
      "relevant_law": [],
      "possible_next_steps": [],
      "documents_or_information": [],
      "similar_cases": [],
      "sources": [],
      "confidence": 0.0,
      "verified": false,
      "needs_professional_help": false,
      "escalated": false
    }
    """
    answer: str = Field(..., description="Main comprehensive plain-language response")
    legal_issue: List[str] = Field(
        default_factory=list,
        description="Identified possible legal issues using non-definitive phrasing"
    )
    relevant_law: List[str] = Field(
        default_factory=list,
        description="Potentially applicable statutes, sections, and legal rules"
    )
    possible_next_steps: List[str] = Field(
        default_factory=list,
        description="Practical procedural steps (e.g. reporting to 1930, bank ombudsman)"
    )
    documents_or_information: List[str] = Field(
        default_factory=list,
        description="Key evidence or documentation to preserve"
    )
    similar_cases: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Comparable district court case precedents with outcome disclaimers"
    )
    sources: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Source IDs, citations, and titles of retrieved evidence"
    )
    confidence: float = Field(
        0.0,
        description="Calibrated confidence score (0.0 - 1.0) based on verification"
    )
    verified: bool = Field(
        False,
        description="Whether the answer passed independent evidence grounding checks"
    )
    needs_professional_help: bool = Field(
        False,
        description="Indicates whether case complexity or deadlines require an advocate"
    )
    escalated: bool = Field(
        False,
        description="True if routed to human advocate due to low confidence or safety"
    )
    clarification_needed: bool = Field(
        False,
        description="True if critical facts were missing and clarifications were requested"
    )
    clarification_questions: List[str] = Field(
        default_factory=list,
        description="Questions asked to clarify missing facts"
    )
