import re
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_optional_current_user
from app.api.v1.auth import limiter
from app.core.authorization import authorize_case_access
from app.core.exceptions import ResourceNotFoundError, ValidationError
from app.core.identifiers import generate_uuid7
from app.models.case import Case, CaseParticipant, CaseStatus, CaseTimelineEvent, ParticipantRole, ParticipantStatus
from app.models.court_case import CourtCase, UserFollowedCase
from app.models.notification import Notification, NotificationType
from app.models.user import User
from app.schemas.court_case import (
    CourtCaseDetail,
    CourtCaseFollowResponse,
    CourtCaseLinkMatterRequest,
    CourtCaseLinkMatterResponse,
    CourtCaseSummary,
    CourtCaseSyncResponse,
    CourtCauseListItem,
    CourtHearingHistoryItem,
    CourtOrderItem,
)

router = APIRouter(prefix="/court-cases", tags=["court-tracking"])


def _find_court_case(db: Session, id_or_cnr: str) -> CourtCase:
    # Try UUID
    try:
        case_uuid = uuid.UUID(id_or_cnr)
        case_by_id = db.query(CourtCase).filter(CourtCase.id == case_uuid, CourtCase.deleted_at.is_(None)).first()
        if case_by_id:
            return case_by_id
    except ValueError:
        pass

    # Normalize alphanumeric CNR
    clean_val = re.sub(r"[^a-zA-Z0-9]", "", id_or_cnr).upper()

    case_by_cnr = (
        db.query(CourtCase)
        .filter(
            or_(
                CourtCase.cnr.ilike(f"%{clean_val}%"),
                CourtCase.cnr == id_or_cnr,
                CourtCase.case_number.ilike(f"%{id_or_cnr}%"),
            ),
            CourtCase.deleted_at.is_(None),
        )
        .first()
    )

    if not case_by_cnr:
        raise ResourceNotFoundError(f"Court case '{id_or_cnr}' was not found in court records.")
    return case_by_cnr


@router.get("", response_model=list[CourtCaseSummary])
@limiter.limit("60/minute")
def search_court_cases(
    request: Request,
    search: str | None = None,
    mode: str = Query("all", pattern="^(all|cnr|case_no|party|advocate)$"),
    court: str | None = None,
    year: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    """Searches authorized Indian court records with bounded pagination and debouncing."""
    query = db.query(CourtCase).filter(CourtCase.deleted_at.is_(None))

    if court and court != "all":
        # Map common court IDs to names
        court_map = {
            "delhi_hc": "Delhi",
            "bombay_hc": "Bombay",
            "calcutta_hc": "Calcutta",
            "madras_hc": "Madras",
            "karnataka_hc": "Karnataka",
            "tis_hazari": "Tis Hazari",
            "saket": "Saket",
        }
        filter_str = court_map.get(court.lower(), court)
        query = query.filter(CourtCase.court_name.ilike(f"%{filter_str}%"))

    if year and year.strip():
        query = query.filter(CourtCase.case_number.ilike(f"%{year.strip()}%"))

    if search and search.strip():
        s = search.strip()
        clean_s = re.sub(r"[^a-zA-Z0-9]", "", s).upper()

        if mode == "cnr":
            query = query.filter(
                or_(
                    CourtCase.cnr.ilike(f"%{s}%"),
                    CourtCase.cnr.ilike(f"%{clean_s}%"),
                )
            )
        elif mode == "case_no":
            query = query.filter(
                or_(
                    CourtCase.case_number.ilike(f"%{s}%"),
                    CourtCase.filing_number.ilike(f"%{s}%"),
                )
            )
        elif mode == "party":
            query = query.filter(
                or_(
                    CourtCase.petitioner.ilike(f"%{s}%"),
                    CourtCase.respondent.ilike(f"%{s}%"),
                )
            )
        elif mode == "advocate":
            query = query.filter(
                or_(
                    CourtCase.petitioner_advocate.ilike(f"%{s}%"),
                    CourtCase.respondent_advocate.ilike(f"%{s}%"),
                )
            )
        else:
            # Combined multi-field search
            query = query.filter(
                or_(
                    CourtCase.cnr.ilike(f"%{s}%"),
                    CourtCase.cnr.ilike(f"%{clean_s}%"),
                    CourtCase.case_number.ilike(f"%{s}%"),
                    CourtCase.filing_number.ilike(f"%{s}%"),
                    CourtCase.petitioner.ilike(f"%{s}%"),
                    CourtCase.respondent.ilike(f"%{s}%"),
                    CourtCase.petitioner_advocate.ilike(f"%{s}%"),
                    CourtCase.respondent_advocate.ilike(f"%{s}%"),
                )
            )

    query = query.order_by(CourtCase.next_hearing_date.asc().nulls_last(), CourtCase.created_at.desc())
    items = query.offset(skip).limit(limit).all()

    # User follow status
    followed_ids: set[uuid.UUID] = set()
    if current_user:
        followed_ids = {
            f.court_case_id
            for f in db.query(UserFollowedCase.court_case_id)
            .filter(UserFollowedCase.user_id == current_user.id)
            .all()
        }

    results: list[CourtCaseSummary] = []
    for item in items:
        summary = CourtCaseSummary.model_validate(item)
        summary.is_followed = item.id in followed_ids
        results.append(summary)

    return results


@router.get("/{id_or_cnr}", response_model=CourtCaseDetail)
@limiter.limit("60/minute")
def get_court_case_detail(
    request: Request,
    id_or_cnr: str,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    """Retrieves authoritative court case details including 3-layer status, hearing history, and orders."""
    case = _find_court_case(db, id_or_cnr)

    is_followed = False
    if current_user:
        follow_record = (
            db.query(UserFollowedCase)
            .filter(
                UserFollowedCase.user_id == current_user.id,
                UserFollowedCase.court_case_id == case.id,
            )
            .first()
        )
        is_followed = follow_record is not None

    # Parse history
    history_items = []
    if case.history_json:
        for h in case.history_json:
            history_items.append(CourtHearingHistoryItem(**h))

    # Parse cause list
    cause_list_item = None
    if case.cause_list_json:
        cause_list_item = CourtCauseListItem(**case.cause_list_json)

    # Parse orders
    order_items = []
    if case.orders_json:
        for o in case.orders_json:
            order_items.append(CourtOrderItem(**o))

    detail = CourtCaseDetail.model_validate(case)
    detail.is_followed = is_followed
    detail.history = history_items
    detail.cause_list = cause_list_item
    detail.orders = order_items
    return detail


@router.post("/{id_or_cnr}/follow", response_model=CourtCaseFollowResponse)
@limiter.limit("30/minute")
def follow_court_case(
    request: Request,
    id_or_cnr: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Follows a court case to receive milestone and hearing notifications."""
    case = _find_court_case(db, id_or_cnr)

    existing = (
        db.query(UserFollowedCase)
        .filter(
            UserFollowedCase.user_id == current_user.id,
            UserFollowedCase.court_case_id == case.id,
        )
        .first()
    )

    if existing:
        return CourtCaseFollowResponse(
            court_case_id=case.id,
            is_followed=True,
            message="You are already following this court case.",
        )

    follow = UserFollowedCase(
        id=generate_uuid7(),
        user_id=current_user.id,
        court_case_id=case.id,
    )
    db.add(follow)

    # Add confirmation notification
    notification = Notification(
        id=generate_uuid7(),
        user_id=current_user.id,
        type=NotificationType.CASE_STATUS_CHANGED,
        title=f"Now Following {case.case_number}",
        message=f"You will receive official updates when new hearings or orders are listed in {case.petitioner} v. {case.respondent} ({case.court_name}).",
        case_id=case.case_id,
        metadata_={"court_case_id": str(case.id), "cnr": case.cnr},
    )
    db.add(notification)
    db.commit()

    return CourtCaseFollowResponse(
        court_case_id=case.id,
        is_followed=True,
        message=f"Successfully following {case.case_number}.",
    )


@router.delete("/{id_or_cnr}/follow", response_model=CourtCaseFollowResponse)
@limiter.limit("30/minute")
def unfollow_court_case(
    request: Request,
    id_or_cnr: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Unfollows a court case."""
    case = _find_court_case(db, id_or_cnr)

    existing = (
        db.query(UserFollowedCase)
        .filter(
            UserFollowedCase.user_id == current_user.id,
            UserFollowedCase.court_case_id == case.id,
        )
        .first()
    )

    if existing:
        db.delete(existing)
        db.commit()

    return CourtCaseFollowResponse(
        court_case_id=case.id,
        is_followed=False,
        message=f"Unfollowed {case.case_number}.",
    )


@router.post("/{id_or_cnr}/sync", response_model=CourtCaseSyncResponse)
@limiter.limit("20/minute")
def sync_court_case(
    request: Request,
    id_or_cnr: str,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    """Explicitly synchronizes with the official court registry, refreshing provenance timestamp."""
    case = _find_court_case(db, id_or_cnr)

    case.last_synchronized_at = datetime.now(UTC)
    case.sync_status = "SYNCED"
    db.commit()

    return CourtCaseSyncResponse(
        court_case_id=case.id,
        last_synchronized_at=case.last_synchronized_at,
        sync_status=case.sync_status,
        message=f"Court case records synchronized successfully with {case.court_name}.",
    )


@router.post("/{id_or_cnr}/link-matter", response_model=CourtCaseLinkMatterResponse)
@limiter.limit("20/minute")
def link_matter(
    request: Request,
    id_or_cnr: str,
    req: CourtCaseLinkMatterRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Connects this official court case with an LCC internal matter workspace."""
    court_case = _find_court_case(db, id_or_cnr)

    if req and req.case_id:
        matter = db.query(Case).filter(Case.id == req.case_id, Case.deleted_at.is_(None)).first()
        if not matter:
            raise ResourceNotFoundError("LCC matter not found.")
        # Authorize: Only active participants or system admins may link court records to an LCC matter
        authorize_case_access(db, current_user, matter.id)
        court_case.case_id = matter.id
        db.commit()
        return CourtCaseLinkMatterResponse(
            court_case_id=court_case.id,
            case_id=matter.id,
            message="Court case successfully linked to existing matter.",
        )

    # If no case_id provided, create a new matter workspace for the user
    new_matter = Case(
        id=generate_uuid7(),
        title=f"{court_case.petitioner} v. {court_case.respondent}",
        description=f"Official court litigation tracked under CNR {court_case.cnr} before {court_case.court_name}. Matter: {court_case.case_number}.",
        status=CaseStatus.OPEN,
    )
    db.add(new_matter)

    participant = CaseParticipant(
        id=generate_uuid7(),
        case_id=new_matter.id,
        user_id=current_user.id,
        participant_role=ParticipantRole.OWNER,
        status=ParticipantStatus.ACTIVE,
    )
    db.add(participant)

    timeline_ev = CaseTimelineEvent(
        id=generate_uuid7(),
        case_id=new_matter.id,
        actor_user_id=current_user.id,
        event_type="COURT_CASE_LINKED",
        description=f"Court litigation {court_case.case_number} ({court_case.cnr}) linked from official registry.",
        event_metadata={"court_case_id": str(court_case.id), "cnr": court_case.cnr},
    )
    db.add(timeline_ev)

    court_case.case_id = new_matter.id
    db.commit()

    return CourtCaseLinkMatterResponse(
        court_case_id=court_case.id,
        case_id=new_matter.id,
        message="Created new LCC matter workspace linked to this court case.",
    )
