import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.exceptions import AppException, ResourceNotFoundError
from app.core.identifiers import generate_uuid7
from app.models.audit import AuditEvent
from app.models.compliance import ComplianceItemStatus, ComplianceRegistryItem
from app.models.user import User


class ComplianceService:
    """Manages the formal compliance registry separating technical, contractual, policy, and legal readiness (Part F)."""

    def __init__(self, db: Session):
        self.db = db

    def register_compliance_item(
        self,
        compliance_item_id: str,
        subject: str,
        requirement_question: str,
        technical_control: str,
        evidence: str,
        owner: str,
        technical_readiness: bool = False,
        contractual_readiness: bool = False,
        policy_readiness: bool = False,
        legal_approval: bool = False,
        actor: User | None = None,
    ) -> ComplianceRegistryItem:
        norm_id = compliance_item_id.strip().upper()
        now = datetime.now(UTC)

        existing = (
            self.db.query(ComplianceRegistryItem)
            .filter(ComplianceRegistryItem.compliance_item_id == norm_id)
            .first()
        )
        if existing:
            existing.subject = subject
            existing.requirement_question = requirement_question
            existing.technical_control = technical_control
            existing.evidence = evidence
            existing.owner = owner
            existing.technical_readiness = technical_readiness
            existing.contractual_readiness = contractual_readiness
            existing.policy_readiness = policy_readiness
            existing.legal_approval = legal_approval
            existing.updated_at = now
            item = existing
        else:
            item = ComplianceRegistryItem(
                id=generate_uuid7(),
                compliance_item_id=norm_id,
                subject=subject,
                requirement_question=requirement_question,
                technical_control=technical_control,
                evidence=evidence,
                owner=owner,
                status=ComplianceItemStatus.OPEN,
                technical_readiness=technical_readiness,
                contractual_readiness=contractual_readiness,
                policy_readiness=policy_readiness,
                legal_approval=legal_approval,
                metadata_={},
                created_at=now,
                updated_at=now,
            )
            self.db.add(item)

        audit = AuditEvent(
            id=generate_uuid7(),
            actor_user_id=actor.id if actor else None,
            event_type="COMPLIANCE_ITEM_REGISTERED",
            entity_type="COMPLIANCE_REGISTRY_ITEM",
            entity_id=item.id,
            action="CREATE" if not existing else "UPDATE",
            timestamp=now,
            metadata_={"compliance_item_id": item.compliance_item_id, "subject": item.subject},
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(item)
        return item

    def record_legal_review(
        self,
        compliance_item_id: str,
        legal_reviewer: str,
        decision: str,
        status: ComplianceItemStatus,
        legal_approval: bool,
        actor: User,
        follow_up: str | None = None,
    ) -> ComplianceRegistryItem:
        item = (
            self.db.query(ComplianceRegistryItem)
            .filter(ComplianceRegistryItem.compliance_item_id == compliance_item_id.strip().upper())
            .first()
        )
        if not item:
            raise ResourceNotFoundError(f"Compliance item '{compliance_item_id}' not found.")

        now = datetime.now(UTC)
        item.legal_reviewer = legal_reviewer
        item.decision = decision
        item.status = status
        item.legal_approval = legal_approval
        item.reviewed_at = now
        item.follow_up = follow_up
        item.updated_at = now

        audit = AuditEvent(
            id=generate_uuid7(),
            actor_user_id=actor.id,
            event_type="COMPLIANCE_ITEM_LEGAL_REVIEWED",
            entity_type="COMPLIANCE_REGISTRY_ITEM",
            entity_id=item.id,
            action="UPDATE",
            timestamp=now,
            metadata_={
                "compliance_item_id": item.compliance_item_id,
                "status": status.value,
                "legal_approval": legal_approval,
                "reviewer": legal_reviewer,
            },
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(item)
        return item

    def get_compliance_scorecard(self) -> dict[str, Any]:
        """Calculates dimensional readiness: technical, contractual, policy, and legal."""
        items = self.db.query(ComplianceRegistryItem).all()
        total = len(items)

        tech_ready = sum(1 for i in items if i.technical_readiness)
        contract_ready = sum(1 for i in items if i.contractual_readiness)
        policy_ready = sum(1 for i in items if i.policy_readiness)
        legal_approved = sum(1 for i in items if i.legal_approval)

        return {
            "total_items": total,
            "technical_readiness_pct": round((tech_ready / total) * 100.0, 2) if total else 0.0,
            "contractual_readiness_pct": round((contract_ready / total) * 100.0, 2) if total else 0.0,
            "policy_readiness_pct": round((policy_ready / total) * 100.0, 2) if total else 0.0,
            "legal_approval_pct": round((legal_approved / total) * 100.0, 2) if total else 0.0,
            "counsel_signoff_status": "READY_FOR_COUNSEL_SIGNOFF" if tech_ready == total and legal_approved < total else ("APPROVED" if legal_approved == total else "OPEN"),
        }
