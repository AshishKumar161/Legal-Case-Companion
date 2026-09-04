import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.exceptions import AppException, ResourceNotFoundError
from app.core.identifiers import generate_uuid7
from app.models.audit import AuditEvent
from app.models.support import (
    SupportCase,
    SupportCaseSeverity,
    SupportCaseStatus,
)
from app.models.user import User


class SupportService:
    """Manages customer support cases under strict zero-trust operational boundaries."""

    def __init__(self, db: Session):
        self.db = db

    def _generate_case_id(self) -> str:
        today_str = datetime.now(UTC).strftime("%Y%m%d")
        count = (
            self.db.query(func.count(SupportCase.id))
            .filter(SupportCase.support_case_id.like(f"SUP-{today_str}-%"))
            .scalar()
            or 0
        )
        return f"SUP-{today_str}-{count + 1:04d}"

    def create_case(
        self,
        category: str,
        subject: str,
        description: str,
        user: User,
        user_scope: str = "CLIENT",
        workflow: str = "GENERAL",
        severity: SupportCaseSeverity = SupportCaseSeverity.SEV3_MEDIUM,
        metadata_: dict | None = None,
    ) -> SupportCase:
        now = datetime.now(UTC)
        case_code = self._generate_case_id()

        support_case = SupportCase(
            id=generate_uuid7(),
            support_case_id=case_code,
            user_id=user.id,
            category=category.strip().upper(),
            severity=severity,
            user_scope=user_scope.strip().upper(),
            workflow=workflow.strip().upper(),
            subject=subject.strip(),
            description=description.strip(),
            opened_at=now,
            status=SupportCaseStatus.OPEN,
            escalation_level=1,
            metadata_=metadata_ or {},
            created_at=now,
            updated_at=now,
        )
        self.db.add(support_case)

        audit = AuditEvent(
            id=generate_uuid7(),
            actor_user_id=user.id,
            event_type="SUPPORT_CASE_CREATED",
            entity_type="SUPPORT_CASE",
            entity_id=support_case.id,
            action="CREATE",
            timestamp=now,
            metadata_={
                "support_case_id": support_case.support_case_id,
                "category": support_case.category,
                "severity": support_case.severity.value,
            },
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(support_case)
        return support_case

    def resolve_case(
        self,
        identifier: str | uuid.UUID,
        resolution_code: str,
        resolution_notes: str,
        actor: User,
    ) -> SupportCase:
        support_case = self.get_case(identifier)
        now = datetime.now(UTC)

        support_case.status = SupportCaseStatus.RESOLVED
        support_case.resolved_at = now
        support_case.resolution_code = resolution_code.strip()
        support_case.resolution_notes = resolution_notes.strip()
        support_case.updated_at = now

        if not support_case.first_response_at:
            support_case.first_response_at = now

        audit = AuditEvent(
            id=generate_uuid7(),
            actor_user_id=actor.id,
            event_type="SUPPORT_CASE_RESOLVED",
            entity_type="SUPPORT_CASE",
            entity_id=support_case.id,
            action="UPDATE",
            timestamp=now,
            metadata_={
                "support_case_id": support_case.support_case_id,
                "resolution_code": support_case.resolution_code,
                "actor_email": actor.email,
            },
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(support_case)
        return support_case

    def escalate_case(
        self,
        identifier: str | uuid.UUID,
        target_level: int,
        actor: User,
        notes: str | None = None,
    ) -> SupportCase:
        support_case = self.get_case(identifier)
        now = datetime.now(UTC)

        if target_level <= support_case.escalation_level:
            raise AppException(
                status_code=400,
                code="INVALID_ESCALATION",
                message=f"Target level {target_level} must be greater than current level {support_case.escalation_level}.",
            )

        support_case.escalation_level = target_level
        support_case.status = SupportCaseStatus.IN_PROGRESS
        support_case.updated_at = now

        audit = AuditEvent(
            id=generate_uuid7(),
            actor_user_id=actor.id,
            event_type="SUPPORT_CASE_ESCALATED",
            entity_type="SUPPORT_CASE",
            entity_id=support_case.id,
            action="UPDATE",
            timestamp=now,
            metadata_={
                "support_case_id": support_case.support_case_id,
                "new_level": target_level,
                "notes": notes,
            },
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(support_case)
        return support_case

    def link_incident(
        self,
        identifier: str | uuid.UUID,
        incident_id: uuid.UUID,
        actor: User,
    ) -> SupportCase:
        support_case = self.get_case(identifier)
        support_case.linked_incident_id = incident_id
        support_case.updated_at = datetime.now(UTC)
        self.db.commit()
        self.db.refresh(support_case)
        return support_case

    def get_case(self, identifier: str | uuid.UUID) -> SupportCase:
        query = self.db.query(SupportCase)
        if isinstance(identifier, uuid.UUID):
            support_case = query.filter(SupportCase.id == identifier).first()
        else:
            try:
                parsed_uuid = uuid.UUID(str(identifier))
                support_case = query.filter(
                    (SupportCase.id == parsed_uuid) | (SupportCase.support_case_id == str(identifier))
                ).first()
            except ValueError:
                support_case = query.filter(SupportCase.support_case_id == str(identifier)).first()

        if not support_case:
            raise ResourceNotFoundError(f"Support case '{identifier}' not found.")
        return support_case

    def list_cases(
        self,
        user_id: uuid.UUID | None = None,
        status: SupportCaseStatus | None = None,
        category: str | None = None,
        severity: SupportCaseSeverity | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[SupportCase]:
        query = self.db.query(SupportCase)
        if user_id:
            query = query.filter(SupportCase.user_id == user_id)
        if status:
            query = query.filter(SupportCase.status == status)
        if category:
            query = query.filter(SupportCase.category == category)
        if severity:
            query = query.filter(SupportCase.severity == severity)
        return query.order_by(SupportCase.opened_at.desc()).offset(skip).limit(limit).all()

    def get_support_analytics(self) -> dict[str, Any]:
        """Calculates SLA compliance, resolution times, and friction hotspots without accessing evidence."""
        total_cases = self.db.query(func.count(SupportCase.id)).scalar() or 0
        resolved_cases = self.db.query(SupportCase).filter(SupportCase.status == SupportCaseStatus.RESOLVED).all()

        total_res_time_seconds = 0.0
        for rc in resolved_cases:
            if rc.resolved_at and rc.opened_at:
                total_res_time_seconds += (rc.resolved_at - rc.opened_at).total_seconds()
        avg_res_hours = round(total_res_time_seconds / (len(resolved_cases) * 3600), 2) if resolved_cases else 0.0

        # Breakdown by category
        cat_counts: dict[str, int] = {}
        workflow_counts: dict[str, int] = {}
        all_cases = self.db.query(SupportCase).all()
        for c in all_cases:
            cat_counts[c.category] = cat_counts.get(c.category, 0) + 1
            workflow_counts[c.workflow] = workflow_counts.get(c.workflow, 0) + 1

        return {
            "total_cases": total_cases,
            "resolved_cases_count": len(resolved_cases),
            "average_resolution_hours": avg_res_hours,
            "friction_hotspots_by_workflow": workflow_counts,
            "category_distribution": cat_counts,
            "sample_confidence": "HIGH" if total_cases >= 30 else "INSUFFICIENT_SAMPLE_SIZE",
        }
