from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.identifiers import generate_uuid7
from app.models.analytics import ProductEvent, ProductEventType
from app.models.case import Case
from app.models.document import Document
from app.models.evaluation import AIEvaluation
from app.models.feedback import PilotFeedback
from app.models.task import CaseTask, TaskStatus
from app.models.user import User, UserRole
from app.schemas.analytics import (
    AIEvaluationSummary,
    FunnelResponse,
    FunnelStepResponse,
    ProductEventCreate,
    ProductHealthSummary,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Enforces that product analytics are strictly isolated from regular users."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required"
        )
    return current_user


@router.post("/events", status_code=status.HTTP_201_CREATED, summary="Log privacy-safe product lifecycle event")
def log_product_event(
    payload: ProductEventCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Ingests non-confidential lifecycle milestone events to measure activation and workflow velocity.
    Never collects raw case facts, evidence content, or client PII.
    """
    if payload.case_id:
        from app.core.authorization import authorize_case_access

        authorize_case_access(db, current_user, payload.case_id)

    evt = ProductEvent(
        id=generate_uuid7(),
        event_type=payload.event_type,
        user_id=current_user.id,
        case_id=payload.case_id,
        resource_id=payload.resource_id,
        timestamp=datetime.now(UTC),
        metadata_=payload.metadata_,
    )
    db.add(evt)
    db.commit()
    return {"status": "RECORDED", "event_id": str(evt.id)}


@router.get("/product-health", response_model=ProductHealthSummary, summary="Admin aggregated pilot product health")
def get_product_health(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """
    Calculates unified pilot product health across activation, funnel completion,
    AI evaluation scores, and prioritized feedback queue.
    """
    total_users = db.query(func.count(User.id)).scalar() or 0
    active_matters = db.query(func.count(Case.id)).filter(Case.deleted_at.is_(None)).scalar() or 0
    docs_uploaded = db.query(func.count(Document.id)).filter(Document.deleted_at.is_(None)).scalar() or 0
    copilot_queries = (
        db.query(func.count(ProductEvent.id))
        .filter(ProductEvent.event_type == ProductEventType.COPILOT_QUERIED)
        .scalar()
        or 0
    )
    actions_completed = (
        db.query(func.count(CaseTask.id))
        .filter(CaseTask.status == TaskStatus.COMPLETED, CaseTask.deleted_at.is_(None))
        .scalar()
        or 0
    )

    # Multi-step Funnel
    funnel_registered = (
        db.query(func.count(func.distinct(ProductEvent.user_id)))
        .filter(ProductEvent.event_type == ProductEventType.USER_REGISTERED)
        .scalar()
        or total_users
    )
    funnel_matters = (
        db.query(func.count(func.distinct(ProductEvent.user_id)))
        .filter(ProductEvent.event_type == ProductEventType.CASE_CREATED)
        .scalar()
        or active_matters
    )
    funnel_docs = (
        db.query(func.count(func.distinct(ProductEvent.user_id)))
        .filter(ProductEvent.event_type == ProductEventType.DOCUMENT_UPLOADED)
        .scalar()
        or 0
    )
    funnel_copilot = (
        db.query(func.count(func.distinct(ProductEvent.user_id)))
        .filter(ProductEvent.event_type == ProductEventType.COPILOT_QUERIED)
        .scalar()
        or 0
    )
    funnel_actions = (
        db.query(func.count(func.distinct(ProductEvent.user_id)))
        .filter(ProductEvent.event_type == ProductEventType.TASK_COMPLETED)
        .scalar()
        or 0
    )

    funnel = [
        FunnelStepResponse(
            step="Registration", count=funnel_registered, conversion_rate=1.0
        ),
        FunnelStepResponse(
            step="Matter Intake",
            count=funnel_matters,
            conversion_rate=(funnel_matters / funnel_registered) if funnel_registered else 0.0,
        ),
        FunnelStepResponse(
            step="Evidence Upload",
            count=funnel_docs,
            conversion_rate=(funnel_docs / funnel_matters) if funnel_matters else 0.0,
        ),
        FunnelStepResponse(
            step="Copilot Interaction",
            count=funnel_copilot,
            conversion_rate=(funnel_copilot / funnel_docs) if funnel_docs else 0.0,
        ),
        FunnelStepResponse(
            step="Action Completed",
            count=funnel_actions,
            conversion_rate=(funnel_actions / funnel_copilot) if funnel_copilot else 0.0,
        ),
    ]

    # AI Health
    eval_total = db.query(func.count(AIEvaluation.id)).scalar() or 0
    avg_grounding = db.query(func.avg(AIEvaluation.grounding_score)).scalar() or 0.0
    avg_citation = db.query(func.avg(AIEvaluation.citation_score)).scalar() or 0.0
    failures = (
        db.query(func.count(AIEvaluation.id))
        .filter(AIEvaluation.failure_category.isnot(None))
        .scalar()
        or 0
    )
    ai_summary = AIEvaluationSummary(
        total_evaluations=eval_total,
        avg_grounding_score=float(avg_grounding),
        avg_citation_score=float(avg_citation),
        failure_rate=float(failures / eval_total) if eval_total else 0.0,
    )

    # Feedback Queue
    unresolved_p0_p1 = (
        db.query(func.count(PilotFeedback.id))
        .filter(
            PilotFeedback.status.in_(["NEW", "TRIAGED", "IN_PROGRESS"]),
            PilotFeedback.priority.in_(["P0", "P1"]),
            PilotFeedback.deleted_at.is_(None),
        )
        .scalar()
        or 0
    )
    unresolved_total = (
        db.query(func.count(PilotFeedback.id))
        .filter(
            PilotFeedback.status.in_(["NEW", "TRIAGED", "IN_PROGRESS"]),
            PilotFeedback.deleted_at.is_(None),
        )
        .scalar()
        or 0
    )

    return ProductHealthSummary(
        total_users=total_users,
        active_matters=active_matters,
        total_documents_uploaded=docs_uploaded,
        copilot_queries_count=copilot_queries,
        actions_completed_count=actions_completed,
        funnel=funnel,
        ai_health=ai_summary,
        unresolved_feedback_p0_p1=unresolved_p0_p1,
        unresolved_feedback_total=unresolved_total,
    )


@router.get("/funnel", response_model=FunnelResponse)
def get_conversion_funnel(
    db: Session = Depends(get_db), admin: User = Depends(require_admin)
):
    """
    Generates the primary product funnel.
    Executes aggregated counts safely in PostgreSQL without leaking PII.
    """
    registered = (
        db.query(func.count(func.distinct(ProductEvent.user_id)))
        .filter(ProductEvent.event_type == ProductEventType.USER_REGISTERED)
        .scalar()
        or 0
    )

    cases = (
        db.query(func.count(func.distinct(ProductEvent.user_id)))
        .filter(ProductEvent.event_type == ProductEventType.CASE_CREATED)
        .scalar()
        or 0
    )

    consultations = (
        db.query(func.count(func.distinct(ProductEvent.user_id)))
        .filter(ProductEvent.event_type == ProductEventType.CONSULTATION_REQUESTED)
        .scalar()
        or 0
    )

    funnel = [
        FunnelStepResponse(step="Registration", count=registered, conversion_rate=1.0),
        FunnelStepResponse(
            step="Case Creation",
            count=cases,
            conversion_rate=(cases / registered) if registered else 0.0,
        ),
        FunnelStepResponse(
            step="Consultation Requested",
            count=consultations,
            conversion_rate=(consultations / cases) if cases else 0.0,
        ),
    ]

    return FunnelResponse(total_users=registered, funnel=funnel)


@router.get("/ai-health", response_model=AIEvaluationSummary)
def get_ai_health(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Returns aggregated AI Evaluation metrics (Grounding, Citation, Failure Rate)."""
    total = db.query(func.count(AIEvaluation.id)).scalar() or 0
    if total == 0:
        return AIEvaluationSummary(
            total_evaluations=0,
            avg_grounding_score=0.0,
            avg_citation_score=0.0,
            failure_rate=0.0,
        )

    avg_grounding = db.query(func.avg(AIEvaluation.grounding_score)).scalar() or 0.0
    avg_citation = db.query(func.avg(AIEvaluation.citation_score)).scalar() or 0.0

    failures = (
        db.query(func.count(AIEvaluation.id))
        .filter(AIEvaluation.failure_category.isnot(None))
        .scalar()
        or 0
    )

    return AIEvaluationSummary(
        total_evaluations=total,
        avg_grounding_score=float(avg_grounding),
        avg_citation_score=float(avg_citation),
        failure_rate=float(failures / total),
    )
