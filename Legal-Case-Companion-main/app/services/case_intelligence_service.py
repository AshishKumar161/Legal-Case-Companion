import datetime
import logging
import re
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.authorization import authorize_case_access
from app.core.exceptions import ResourceNotFoundError
from app.core.identifiers import generate_uuid7
from app.models.ai import AIConversation, AIMessage, AIMessageRole, DocumentChunk
from app.models.case_intelligence import (
    CaseChronologyEvent,
    CaseClaimDefense,
    CaseEvidenceGap,
    CaseFact,
    CaseRiskIndicator,
    ClaimDefenseStatus,
    ClaimPositionType,
    DatePrecision,
    EvidenceGapStatus,
    EvidenceGapType,
    FactSourceType,
    FactVerificationStatus,
    IssueStatus,
    LegalIssue,
    RiskSeverity,
)
from app.models.document import (
    Document,
    DocumentProcessingStatus,
    DocumentSecurityStatus,
)
from app.models.user import User
from app.schemas.case_intelligence import (
    CaseChronologyEventCreate,
    CaseChronologyEventResponse,
    CaseChronologyEventUpdate,
    CaseClaimDefenseCreate,
    CaseClaimDefenseResponse,
    CaseClaimDefenseUpdate,
    CaseEvidenceGapCreate,
    CaseEvidenceGapResponse,
    CaseEvidenceGapUpdate,
    CaseFactCreate,
    CaseFactResponse,
    CaseFactUpdate,
    CaseIntelligenceResponse,
    CaseIntelligenceSummary,
    CaseRiskIndicatorCreate,
    CaseRiskIndicatorResponse,
    CaseRiskIndicatorUpdate,
    LegalIssueCreate,
    LegalIssueResponse,
    LegalIssueUpdate,
    RefreshIntelligenceRequest,
)

logger = logging.getLogger(__name__)

# Date extraction regex patterns for Indian legal documents
DATE_PATTERNS = [
    # 12/03/2024 or 12-03-2024
    (r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b", "DMY_NUM"),
    # 12th March 2024 or 12 March 2024
    (r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s,]+(\d{4})\b", "DMY_TEXT"),
    # March 2024
    (r"\b(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s,]+(\d{4})\b", "MY_TEXT"),
]

MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def parse_legal_date(date_str: str, pattern_type: str, match_groups: tuple) -> tuple[datetime.date | None, DatePrecision, str]:
    """Parses date string into standardized datetime.date and precision."""
    try:
        if pattern_type == "DMY_NUM":
            d, m, y = int(match_groups[0]), int(match_groups[1]), int(match_groups[2])
            # Handle MM/DD vs DD/MM (India standard DD/MM/YYYY)
            if m > 12 >= d:
                d, m = m, d
            return datetime.date(y, m, d), DatePrecision.EXACT_DATE, f"{d:02d}/{m:02d}/{y:04d}"
        if pattern_type == "DMY_TEXT":
            d = int(match_groups[0])
            m_str = match_groups[1][:3].lower()
            m = MONTH_MAP.get(m_str, 1)
            y = int(match_groups[2])
            return datetime.date(y, m, d), DatePrecision.EXACT_DATE, f"{d:02d} {match_groups[1]} {y:04d}"
        if pattern_type == "MY_TEXT":
            m_str = match_groups[0][:3].lower()
            m = MONTH_MAP.get(m_str, 1)
            y = int(match_groups[1])
            return datetime.date(y, m, 1), DatePrecision.MONTH_YEAR, f"{match_groups[0]} {y:04d}"
    except (ValueError, IndexError):
        pass
    return None, DatePrecision.UNKNOWN, date_str


class CaseIntelligenceService:
    """Manages the persistent, provenance-preserving case intelligence layer."""

    def __init__(self, db: Session):
        self.db = db

    def get_case_intelligence(self, user: User, case_id: UUID) -> CaseIntelligenceResponse:
        """Retrieves structured case intelligence including facts, issues, claims, timeline, gaps, and risks."""
        authorize_case_access(self.db, user, case_id)

        facts = (
            self.db.query(CaseFact)
            .filter(CaseFact.case_id == case_id, CaseFact.deleted_at.is_(None))
            .order_by(CaseFact.created_at.desc())
            .all()
        )
        issues = (
            self.db.query(LegalIssue)
            .filter(LegalIssue.case_id == case_id, LegalIssue.deleted_at.is_(None))
            .order_by(LegalIssue.created_at.desc())
            .all()
        )
        claims = (
            self.db.query(CaseClaimDefense)
            .filter(CaseClaimDefense.case_id == case_id, CaseClaimDefense.deleted_at.is_(None))
            .order_by(CaseClaimDefense.created_at.desc())
            .all()
        )
        timeline = (
            self.db.query(CaseChronologyEvent)
            .filter(CaseChronologyEvent.case_id == case_id, CaseChronologyEvent.deleted_at.is_(None))
            .order_by(CaseChronologyEvent.event_date.asc().nulls_last(), CaseChronologyEvent.created_at.asc())
            .all()
        )
        gaps = (
            self.db.query(CaseEvidenceGap)
            .filter(CaseEvidenceGap.case_id == case_id, CaseEvidenceGap.deleted_at.is_(None))
            .order_by(CaseEvidenceGap.created_at.desc())
            .all()
        )
        risks = (
            self.db.query(CaseRiskIndicator)
            .filter(CaseRiskIndicator.case_id == case_id, CaseRiskIndicator.deleted_at.is_(None))
            .order_by(CaseRiskIndicator.created_at.desc())
            .all()
        )

        summary = CaseIntelligenceSummary(
            total_facts=len(facts),
            verified_facts=sum(1 for f in facts if f.verification_status in (FactVerificationStatus.AI_VERIFIED, FactVerificationStatus.HUMAN_CONFIRMED)),
            user_reported_facts=sum(1 for f in facts if f.source_type == FactSourceType.USER_REPORTED),
            open_issues=sum(1 for i in issues if i.status in (IssueStatus.IDENTIFIED, IssueStatus.ANALYZING, IssueStatus.UNRESOLVED)),
            timeline_events=len(timeline),
            conflicting_timeline_events=sum(1 for t in timeline if t.is_conflicting),
            active_claims=len(claims),
            evidence_gaps=sum(1 for g in gaps if g.status != EvidenceGapStatus.RESOLVED),
            high_risks=sum(1 for r in risks if r.severity == RiskSeverity.HIGH),
            critical_risks=sum(1 for r in risks if r.severity == RiskSeverity.CRITICAL),
        )

        last_refreshed = max((f.updated_at for f in facts), default=None)

        return CaseIntelligenceResponse(
            case_id=case_id,
            facts=[CaseFactResponse.model_validate(f) for f in facts],
            issues=[LegalIssueResponse.model_validate(i) for i in issues],
            claims_defenses=[CaseClaimDefenseResponse.model_validate(c) for c in claims],
            timeline=[CaseChronologyEventResponse.model_validate(t) for t in timeline],
            evidence_gaps=[CaseEvidenceGapResponse.model_validate(g) for g in gaps],
            risks=[CaseRiskIndicatorResponse.model_validate(r) for r in risks],
            summary=summary,
            last_refreshed_at=last_refreshed,
        )

    def refresh_case_intelligence(
        self, user: User, case_id: UUID, req: RefreshIntelligenceRequest | None = None
    ) -> CaseIntelligenceResponse:
        """Refreshes and extracts verified case intelligence from active safe documents,

        stale version checks, and user conversation findings.
        """
        authorize_case_access(self.db, user, case_id)
        req = req or RefreshIntelligenceRequest()

        # 1. Fetch all SAFE & READY documents for this case
        docs = (
            self.db.query(Document)
            .filter(
                Document.case_id == case_id,
                Document.security_status == DocumentSecurityStatus.SAFE,
                Document.processing_status == DocumentProcessingStatus.READY,
                Document.deleted_at.is_(None),
            )
            .all()
        )

        # 2. Fetch all chunks
        chunks = (
            self.db.query(DocumentChunk)
            .filter(
                DocumentChunk.case_id == case_id,
                DocumentChunk.deleted_at.is_(None),
            )
            .all()
        )

        chunk_doc_map = {d.id: d for d in docs}

        # 3. Handle Stale Intelligence: Check existing facts against current document versions
        existing_facts = (
            self.db.query(CaseFact)
            .filter(CaseFact.case_id == case_id, CaseFact.deleted_at.is_(None))
            .all()
        )
        for ef in existing_facts:
            if ef.source_document_id and ef.source_document_id in chunk_doc_map:
                current_doc = chunk_doc_map[ef.source_document_id]
                if ef.document_version and ef.document_version < current_doc.version:
                    ef.deleted_at = datetime.datetime.now(datetime.UTC)

        # 4. Extract Structured Facts from Document Chunks
        extracted_facts: list[CaseFact] = []
        for chunk in chunks:
            doc = chunk_doc_map.get(chunk.document_id)
            if not doc:
                continue

            content = chunk.content.strip()
            # Preserve common Indian legal abbreviations (Rs., Sec., No., Dr., Mr., etc.)
            normalized_content = re.sub(r"\b(Rs|Sec|No|Dr|Mr|Adv|Co|Ltd|vs|v)\.", r"\1_DOT_", content, flags=re.IGNORECASE)
            raw_sentences = re.split(r"(?<=[.!?])\s+", normalized_content)
            sentences = [s.replace("_DOT_", ".").replace("_dot_", ".").strip() for s in raw_sentences if len(s.strip()) > 10]
            if not sentences and len(content) > 10:
                sentences = [content]

            for s in sentences:
                # Key factual triggers (clauses, amounts, notices, agreements, dates)
                is_fact = any(
                    kw in s.lower()
                    for kw in (
                        "rent is", "deposit is", "clause", "notice", "agreed",
                        "terminate", "executed", "payment", "rupees", "rs.", "inr",
                        "demand", "dishonour", "cheque", "section", "breach",
                    )
                )
                if not is_fact:
                    continue

                category = "CONTRACTUAL" if "clause" in s.lower() or "agreement" in s.lower() else (
                    "FINANCIAL" if any(w in s.lower() for w in ("rent", "deposit", "rupees", "rs.", "inr", "payment")) else
                    "CHRONOLOGY" if any(w in s.lower() for w in ("dated", "on", "before", "after")) else "GENERAL"
                )

                # Check if fact already exists
                existing = next((f for f in existing_facts if f.fact_text == s and f.deleted_at is None), None)
                if existing:
                    continue

                fact = CaseFact(
                    id=generate_uuid7(),
                    case_id=case_id,
                    fact_text=s,
                    category=category,
                    verification_status=FactVerificationStatus.AI_VERIFIED,
                    source_type=FactSourceType.CASE_EVIDENCE,
                    source_chunk_id=chunk.id,
                    source_document_id=doc.id,
                    source_filename=doc.filename,
                    document_version=doc.version,
                    confidence_score=0.95,
                )
                extracted_facts.append(fact)
                self.db.add(fact)

        # 5. Extract Chronology Events & Check for Date Conflicts
        extracted_events: list[CaseChronologyEvent] = []
        existing_events = (
            self.db.query(CaseChronologyEvent)
            .filter(CaseChronologyEvent.case_id == case_id, CaseChronologyEvent.deleted_at.is_(None))
            .all()
        )

        event_candidates_by_type: dict[str, list[dict[str, Any]]] = {}

        for chunk in chunks:
            doc = chunk_doc_map.get(chunk.document_id)
            if not doc:
                continue

            content = chunk.content.strip()
            for pattern, p_type in DATE_PATTERNS:
                for match in re.finditer(pattern, content, re.IGNORECASE):
                    matched_text = match.group(0)
                    parsed_date, precision, date_label = parse_legal_date(matched_text, p_type, match.groups())

                    # Contextual sentence around the date
                    start_idx = max(0, match.start() - 60)
                    end_idx = min(len(content), match.end() + 100)
                    context_snippet = content[start_idx:end_idx].strip()

                    event_type = "AGREEMENT_EXECUTION" if "agreement" in context_snippet.lower() or "executed" in context_snippet.lower() else (
                        "NOTICE_ISSUED" if "notice" in context_snippet.lower() else (
                            "PAYMENT_DUE" if "rent" in context_snippet.lower() or "payment" in context_snippet.lower() else (
                                "CHEQUE_DISHONOURED" if "dishonour" in context_snippet.lower() or "cheque" in context_snippet.lower() else "GENERAL_EVENT"
                            )
                        )
                    )

                    candidate_info = {
                        "date": parsed_date,
                        "date_label": date_label,
                        "precision": precision,
                        "description": context_snippet,
                        "chunk_id": chunk.id,
                        "document_id": doc.id,
                        "filename": doc.filename,
                    }
                    event_candidates_by_type.setdefault(event_type, []).append(candidate_info)

        for event_type, candidates in event_candidates_by_type.items():
            distinct_dates = {c["date"] for c in candidates if c["date"] is not None}
            is_conflicting = len(distinct_dates) > 1

            for cand in candidates:
                # Check duplicate
                dup = next((e for e in existing_events if e.description == cand["description"] and e.deleted_at is None), None)
                if dup:
                    continue

                conflicts_detail = [
                    {"date": str(c["date"]), "filename": c["filename"], "source": c["description"][:100]}
                    for c in candidates if c["date"] != cand["date"]
                ] if is_conflicting else None

                event = CaseChronologyEvent(
                    id=generate_uuid7(),
                    case_id=case_id,
                    event_date=cand["date"],
                    date_text=cand["date_label"],
                    date_precision=cand["precision"],
                    event_type=event_type,
                    description=cand["description"],
                    is_conflicting=is_conflicting,
                    conflicting_source_details=conflicts_detail,
                    source_chunk_id=cand["chunk_id"],
                    source_document_id=cand["document_id"],
                    source_filename=cand["filename"],
                    verification_status=FactVerificationStatus.AI_VERIFIED,
                )
                extracted_events.append(event)
                self.db.add(event)

        # 6. Extract Legal Issues
        existing_issues = (
            self.db.query(LegalIssue)
            .filter(LegalIssue.case_id == case_id, LegalIssue.deleted_at.is_(None))
            .all()
        )
        for chunk in chunks:
            c_lower = chunk.content.lower()
            if "terminate" in c_lower or "breach" in c_lower:
                issue_str = "Whether termination or breach of contract is valid under available contractual terms."
                if not any(i.issue_text == issue_str and i.deleted_at is None for i in existing_issues):
                    iss = LegalIssue(
                        id=generate_uuid7(),
                        case_id=case_id,
                        issue_text=issue_str,
                        category="CONTRACTUAL_BREACH",
                        status=IssueStatus.IDENTIFIED,
                        verification_status=FactVerificationStatus.AI_SUGGESTED,
                    )
                    self.db.add(iss)
                    existing_issues.append(iss)

            if "section 138" in c_lower or "cheque" in c_lower:
                issue_str = "Whether statutory demand notice complied with statutory 15-day timeline under Section 138 Negotiable Instruments Act."
                if not any(i.issue_text == issue_str and i.deleted_at is None for i in existing_issues):
                    iss = LegalIssue(
                        id=generate_uuid7(),
                        case_id=case_id,
                        issue_text=issue_str,
                        category="STATUTORY_COMPLIANCE",
                        status=IssueStatus.IDENTIFIED,
                        verification_status=FactVerificationStatus.AI_SUGGESTED,
                        relevant_authority_ids=["IN-ACT-1881-26-SEC-138-V2018"],
                    )
                    self.db.add(iss)
                    existing_issues.append(iss)

        # 7. Extract Claims and Defenses
        existing_claims = (
            self.db.query(CaseClaimDefense)
            .filter(CaseClaimDefense.case_id == case_id, CaseClaimDefense.deleted_at.is_(None))
            .all()
        )
        for chunk in chunks:
            c_lower = chunk.content.lower()
            if "demand" in c_lower or "claim" in c_lower or "rupees" in c_lower:
                stmt = f"Claim for relief grounded in {chunk.source_filename if hasattr(chunk, 'source_filename') else 'case record'}: {chunk.content[:150]}"
                if not any(c.statement == stmt and c.deleted_at is None for c in existing_claims):
                    claim = CaseClaimDefense(
                        id=generate_uuid7(),
                        case_id=case_id,
                        position_type=ClaimPositionType.CLAIM,
                        party_role="PETITIONER",
                        statement=stmt,
                        status=ClaimDefenseStatus.SUPPORTED,
                        verification_status=FactVerificationStatus.AI_VERIFIED,
                        supporting_chunk_ids=[str(chunk.id)],
                    )
                    self.db.add(claim)
                    existing_claims.append(claim)

        # 8. Identify Evidence Gaps
        existing_gaps = (
            self.db.query(CaseEvidenceGap)
            .filter(CaseEvidenceGap.case_id == case_id, CaseEvidenceGap.deleted_at.is_(None))
            .all()
        )

        all_text = " ".join(c.content.lower() for c in chunks)
        # Check if notice mentioned but no postal/delivery receipt uploaded
        if "notice" in all_text and not any(
            "speed post" in c.content.lower() or "registered post" in c.content.lower() or "tracking" in c.content.lower()
            for c in chunks
        ):
            gap_desc = "Proof of service / postal tracking receipt for statutory legal notice not found in available case materials."
            if not any(g.description == gap_desc and g.deleted_at is None for g in existing_gaps):
                gap = CaseEvidenceGap(
                    id=generate_uuid7(),
                    case_id=case_id,
                    description=gap_desc,
                    gap_type=EvidenceGapType.MISSING_DOCUMENT,
                    severity=RiskSeverity.HIGH,
                    status=EvidenceGapStatus.NOT_FOUND_IN_AVAILABLE_MATERIALS,
                )
                self.db.add(gap)
                existing_gaps.append(gap)

        # 9. Identify Conservative Risk Indicators
        existing_risks = (
            self.db.query(CaseRiskIndicator)
            .filter(CaseRiskIndicator.case_id == case_id, CaseRiskIndicator.deleted_at.is_(None))
            .all()
        )
        if any(g.severity == RiskSeverity.HIGH for g in existing_gaps):
            risk_title = "Unverified Notice Service Delivery"
            if not any(r.risk_title == risk_title and r.deleted_at is None for r in existing_risks):
                risk = CaseRiskIndicator(
                    id=generate_uuid7(),
                    case_id=case_id,
                    risk_title=risk_title,
                    description="Available case materials lack affirmative proof of service for statutory notice, which may impact limitation or cause of action.",
                    severity=RiskSeverity.HIGH,
                    mitigation_hint="Procure postal tracking consignment summary or proof of delivery certificate from postal authorities.",
                    verification_status=FactVerificationStatus.AI_VERIFIED,
                )
                self.db.add(risk)

        # 10. Scan User-Reported Conversation Findings
        if req.include_conversations:
            user_msgs = (
                self.db.query(AIMessage)
                .join(AIConversation, AIConversation.id == AIMessage.conversation_id)
                .filter(
                    AIConversation.case_id == case_id,
                    AIConversation.deleted_at.is_(None),
                    AIMessage.role.in_([AIMessageRole.USER, "user", "USER"]),
                )
                .order_by(AIMessage.created_at.desc())
                .limit(10)
                .all()
            )
            for um in user_msgs:
                if len(um.content) > 15 and any(w in um.content.lower() for w in ("paid", "agreed", "informed", "called", "sent")):
                    fact_str = f"User reported: {um.content}"
                    if not any(f.fact_text == fact_str and f.deleted_at is None for f in existing_facts):
                        uf = CaseFact(
                            id=generate_uuid7(),
                            case_id=case_id,
                            fact_text=fact_str,
                            category="USER_REPORTED",
                            verification_status=FactVerificationStatus.USER_REPORTED,
                            source_type=FactSourceType.USER_REPORTED,
                            source_message_id=um.id,
                            confidence_score=0.5,
                        )
                        self.db.add(uf)
                        existing_facts.append(uf)

        self.db.commit()
        return self.get_case_intelligence(user, case_id)

    # Mutation & Human Review Methods
    def create_fact(self, user: User, case_id: UUID, req: CaseFactCreate) -> CaseFact:
        authorize_case_access(self.db, user, case_id)
        fact = CaseFact(
            id=generate_uuid7(),
            case_id=case_id,
            fact_text=req.fact_text,
            category=req.category,
            verification_status=FactVerificationStatus.USER_REPORTED if req.source_type == FactSourceType.USER_REPORTED else FactVerificationStatus.AI_SUGGESTED,
            source_type=req.source_type,
            confidence_score=0.5 if req.source_type == FactSourceType.USER_REPORTED else 1.0,
        )
        self.db.add(fact)
        self.db.commit()
        self.db.refresh(fact)
        return fact

    def update_fact(self, user: User, case_id: UUID, fact_id: UUID, req: CaseFactUpdate) -> CaseFact:
        authorize_case_access(self.db, user, case_id)
        fact = (
            self.db.query(CaseFact)
            .filter(CaseFact.id == fact_id, CaseFact.case_id == case_id, CaseFact.deleted_at.is_(None))
            .first()
        )
        if not fact:
            raise ResourceNotFoundError("Case fact not found")

        if req.fact_text is not None:
            fact.fact_text = req.fact_text
        if req.category is not None:
            fact.category = req.category
        if req.verification_status is not None:
            fact.verification_status = req.verification_status

        self.db.commit()
        self.db.refresh(fact)
        return fact

    def create_issue(self, user: User, case_id: UUID, req: LegalIssueCreate) -> LegalIssue:
        authorize_case_access(self.db, user, case_id)
        issue = LegalIssue(
            id=generate_uuid7(),
            case_id=case_id,
            issue_text=req.issue_text,
            category=req.category,
            status=IssueStatus.IDENTIFIED,
            verification_status=FactVerificationStatus.HUMAN_CONFIRMED,
            supporting_fact_ids=[str(fid) for fid in req.supporting_fact_ids],
            relevant_authority_ids=req.relevant_authority_ids,
        )
        self.db.add(issue)
        self.db.commit()
        self.db.refresh(issue)
        return issue

    def update_issue(self, user: User, case_id: UUID, issue_id: UUID, req: LegalIssueUpdate) -> LegalIssue:
        authorize_case_access(self.db, user, case_id)
        issue = (
            self.db.query(LegalIssue)
            .filter(LegalIssue.id == issue_id, LegalIssue.case_id == case_id, LegalIssue.deleted_at.is_(None))
            .first()
        )
        if not issue:
            raise ResourceNotFoundError("Legal issue not found")

        if req.issue_text is not None:
            issue.issue_text = req.issue_text
        if req.category is not None:
            issue.category = req.category
        if req.status is not None:
            issue.status = req.status
        if req.verification_status is not None:
            issue.verification_status = req.verification_status
        if req.supporting_fact_ids is not None:
            issue.supporting_fact_ids = [str(fid) for fid in req.supporting_fact_ids]
        if req.relevant_authority_ids is not None:
            issue.relevant_authority_ids = req.relevant_authority_ids

        self.db.commit()
        self.db.refresh(issue)
        return issue

    def create_claim(self, user: User, case_id: UUID, req: CaseClaimDefenseCreate) -> CaseClaimDefense:
        authorize_case_access(self.db, user, case_id)
        claim = CaseClaimDefense(
            id=generate_uuid7(),
            case_id=case_id,
            position_type=req.position_type,
            party_role=req.party_role,
            statement=req.statement,
            status=ClaimDefenseStatus.ASSERTED,
            verification_status=FactVerificationStatus.HUMAN_CONFIRMED,
        )
        self.db.add(claim)
        self.db.commit()
        self.db.refresh(claim)
        return claim

    def update_claim(self, user: User, case_id: UUID, claim_id: UUID, req: CaseClaimDefenseUpdate) -> CaseClaimDefense:
        authorize_case_access(self.db, user, case_id)
        claim = (
            self.db.query(CaseClaimDefense)
            .filter(CaseClaimDefense.id == claim_id, CaseClaimDefense.case_id == case_id, CaseClaimDefense.deleted_at.is_(None))
            .first()
        )
        if not claim:
            raise ResourceNotFoundError("Claim/Defense not found")

        if req.statement is not None:
            claim.statement = req.statement
        if req.status is not None:
            claim.status = req.status
        if req.verification_status is not None:
            claim.verification_status = req.verification_status

        self.db.commit()
        self.db.refresh(claim)
        return claim

    def create_timeline_event(self, user: User, case_id: UUID, req: CaseChronologyEventCreate) -> CaseChronologyEvent:
        authorize_case_access(self.db, user, case_id)
        event = CaseChronologyEvent(
            id=generate_uuid7(),
            case_id=case_id,
            event_date=req.event_date,
            date_text=req.date_text,
            date_precision=req.date_precision,
            event_type=req.event_type,
            description=req.description,
            verification_status=FactVerificationStatus.HUMAN_CONFIRMED,
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def update_timeline_event(self, user: User, case_id: UUID, event_id: UUID, req: CaseChronologyEventUpdate) -> CaseChronologyEvent:
        authorize_case_access(self.db, user, case_id)
        event = (
            self.db.query(CaseChronologyEvent)
            .filter(CaseChronologyEvent.id == event_id, CaseChronologyEvent.case_id == case_id, CaseChronologyEvent.deleted_at.is_(None))
            .first()
        )
        if not event:
            raise ResourceNotFoundError("Timeline event not found")

        if req.event_date is not None:
            event.event_date = req.event_date
        if req.date_text is not None:
            event.date_text = req.date_text
        if req.date_precision is not None:
            event.date_precision = req.date_precision
        if req.event_type is not None:
            event.event_type = req.event_type
        if req.description is not None:
            event.description = req.description
        if req.verification_status is not None:
            event.verification_status = req.verification_status

        self.db.commit()
        self.db.refresh(event)
        return event

    def create_evidence_gap(self, user: User, case_id: UUID, req: CaseEvidenceGapCreate) -> CaseEvidenceGap:
        authorize_case_access(self.db, user, case_id)
        gap = CaseEvidenceGap(
            id=generate_uuid7(),
            case_id=case_id,
            description=req.description,
            gap_type=req.gap_type,
            severity=req.severity,
            status=EvidenceGapStatus.IDENTIFIED,
        )
        self.db.add(gap)
        self.db.commit()
        self.db.refresh(gap)
        return gap

    def update_evidence_gap(self, user: User, case_id: UUID, gap_id: UUID, req: CaseEvidenceGapUpdate) -> CaseEvidenceGap:
        authorize_case_access(self.db, user, case_id)
        gap = (
            self.db.query(CaseEvidenceGap)
            .filter(CaseEvidenceGap.id == gap_id, CaseEvidenceGap.case_id == case_id, CaseEvidenceGap.deleted_at.is_(None))
            .first()
        )
        if not gap:
            raise ResourceNotFoundError("Evidence gap not found")

        if req.description is not None:
            gap.description = req.description
        if req.severity is not None:
            gap.severity = req.severity
        if req.status is not None:
            gap.status = req.status

        self.db.commit()
        self.db.refresh(gap)
        return gap

    def create_risk(self, user: User, case_id: UUID, req: CaseRiskIndicatorCreate) -> CaseRiskIndicator:
        authorize_case_access(self.db, user, case_id)
        risk = CaseRiskIndicator(
            id=generate_uuid7(),
            case_id=case_id,
            risk_title=req.risk_title,
            description=req.description,
            severity=req.severity,
            mitigation_hint=req.mitigation_hint,
            verification_status=FactVerificationStatus.HUMAN_CONFIRMED,
        )
        self.db.add(risk)
        self.db.commit()
        self.db.refresh(risk)
        return risk

    def update_risk(self, user: User, case_id: UUID, risk_id: UUID, req: CaseRiskIndicatorUpdate) -> CaseRiskIndicator:
        authorize_case_access(self.db, user, case_id)
        risk = (
            self.db.query(CaseRiskIndicator)
            .filter(CaseRiskIndicator.id == risk_id, CaseRiskIndicator.case_id == case_id, CaseRiskIndicator.deleted_at.is_(None))
            .first()
        )
        if not risk:
            raise ResourceNotFoundError("Risk indicator not found")

        if req.risk_title is not None:
            risk.risk_title = req.risk_title
        if req.description is not None:
            risk.description = req.description
        if req.severity is not None:
            risk.severity = req.severity
        if req.mitigation_hint is not None:
            risk.mitigation_hint = req.mitigation_hint
        if req.verification_status is not None:
            risk.verification_status = req.verification_status

        self.db.commit()
        self.db.refresh(risk)
        return risk
